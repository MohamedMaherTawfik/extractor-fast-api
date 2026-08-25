"""Coordinator for contract-bound generation, persistence, QA, retry, and approval."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.enums import (
    GeneratedAssetStatus, GenerationJobStatus, GenerationRetryType, GenerationType,
    ProviderAvailability, QACategory, QAResultStatus, ReproducibilityLevel, ReviewStatus,
)
from backend.core.exceptions import (
    GenerationError, GenerationNotReadyError, MaxRetriesExceededError, NotFoundError,
    ProviderUnavailableError,
)
from backend.generation.model_registry import ModelCapabilityRegistry, ModelSelectorService
from backend.generation.pipelines import (
    AudioGenerationService, CopyGenerationService, DeferredC2PAProvenanceAdapter,
    GenerationRetryService, ImageGenerationService, LocalGenerationQueue,
    StoryboardGenerationService, VideoGenerationService,
)
from backend.generation.prompting import PromptCompiler, stable_prompt_hash
from backend.generation.providers import ProviderPromptAdapter, ProviderRegistry
from backend.generation.qa import GenerationQAPipeline
from backend.generation.storage import AssetStorageService
from backend.repositories.generation_repository import GenerationRepository
from backend.repositories.rule_repository import RuleRepository
from backend.schemas.generation import (
    GeneratedAssetResponse, GenerationJobResponse, GenerationPreviewResponse,
    GenerationRequest, ModelCapabilities, PromptPackageData, RequiredCapabilities,
)
from backend.services.generation_config import load_generation_config


class GenerationOrchestrator:
    def __init__(self, session: Session, *, providers: ProviderRegistry | None = None, queue=None) -> None:
        self.session = session
        self.repository = GenerationRepository(session)
        self.rules = RuleRepository(session)
        self.config = load_generation_config()
        self.models = ModelCapabilityRegistry(session, providers)
        self.selector = ModelSelectorService(self.models)
        self.providers = self.models.providers
        self.compiler = PromptCompiler()
        self.adapter = ProviderPromptAdapter()
        self.storage = AssetStorageService(self.repository)
        self.qa = GenerationQAPipeline(self.repository)
        self.retry = GenerationRetryService()
        self.queue = queue or LocalGenerationQueue()
        self.copy = CopyGenerationService()
        self.image = ImageGenerationService()
        self.storyboard = StoryboardGenerationService()
        self.video = VideoGenerationService(self.storyboard)
        self.audio = AudioGenerationService()
        self.provenance_adapter = DeferredC2PAProvenanceAdapter()

    def preview_job(self, request: GenerationRequest) -> GenerationPreviewResponse:
        contract, version = self._contract(request)
        compiled = self.compiler.compile(version, request)
        required = self._required(request)
        selection = self.selector.select(required, preference=request.provider_preference, requested_model=request.model_id)
        return GenerationPreviewResponse(
            contract_uid=contract.contract_uid, contract_version=version.version,
            selected_provider=selection.primary.provider_code, selected_model=selection.primary.model_id,
            fallback_models=[f"{item.provider_code}:{item.model_id}:{item.model_version}" for item in selection.fallbacks],
            prompt_summary={"task": compiled.data.task, "modality": compiled.data.modality, "generation_type": request.generation_type.value, "sections": [item.id for item in compiled.data.sections]},
            prompt_hash=compiled.prompt_hash,
            constraints={"positive": compiled.data.positive_constraints, "negative": compiled.data.negative_constraints, "forbidden_changes": compiled.data.forbidden_changes},
            references=request.references, estimated_jobs=max(1, int(request.options.get("variants", 1))),
            estimated_cost=0.0, warnings=["Mock providers are configured; no production model is called."],
        )

    def create_job(self, request: GenerationRequest):
        if request.dry_run:
            return self.preview_job(request)
        contract, version = self._contract(request)
        compiled = self.compiler.compile(version, request)
        selection = self.selector.select(self._required(request), preference=request.provider_preference, requested_model=request.model_id)
        key = self._idempotency_key(contract.id, version.version, compiled.prompt_hash, selection.primary, request)
        if self.config.generation_cache_enabled and not request.fresh_variation:
            cached = self.repository.find_cached(key)
            if cached is not None:
                return cached
        capabilities = ModelCapabilities.model_validate(selection.primary.capabilities)
        job = self.repository.create_job(
            job_uid=f"GEN_{uuid4().hex}", task_id=request.task_id,
            generation_contract_id=contract.id, generation_contract_version=version.version,
            recipe_id=contract.recipe_id, recipe_version=version.recipe_version,
            content_type=str(version.payload.get("content_type") or "other"), modality=compiled.data.modality,
            generation_type=request.generation_type, provider=selection.primary.provider_code,
            model_id=selection.primary.model_id, model_version=selection.primary.model_version,
            status=GenerationJobStatus.QUEUED, priority=request.priority, attempt_count=0,
            max_attempts=request.max_attempts or self.config.default_max_attempts, seed=request.seed,
            request_payload=request.model_dump(mode="json"), prompt_hash=compiled.prompt_hash,
            idempotency_key=key, max_cost=request.max_cost, max_duration_seconds=request.max_duration_seconds,
            used_fallback=False,
            reproducibility_level=ReproducibilityLevel.FULL if request.seed is not None and capabilities.supports_seed else ReproducibilityLevel.BEST_EFFORT,
        )
        self.compiler.persist(self.repository, job, compiled)
        for reference in request.references:
            self.repository.add_reference(
                job, reference_asset_id=reference.asset_id, reference_version=reference.reference_version,
                reference_role=reference.reference_role, rights_status=reference.rights_status,
                approved=reference.approved, checksum=reference.checksum,
                metadata_payload=reference.model_dump(mode="json", exclude={"asset_id", "reference_version", "reference_role", "rights_status", "approved", "checksum"}),
            )
        self._event(job, "JOB_CREATED", {"contract_version": version.version})
        self.queue.submit(job.job_uid)
        if request.execute:
            return self.run_job(job.job_uid)
        return job

    def run_job(self, identifier: int | str):
        job = self._job(identifier)
        if job.status is GenerationJobStatus.CANCELLED:
            return job
        if job.status not in {GenerationJobStatus.QUEUED, GenerationJobStatus.RETRY_PENDING, GenerationJobStatus.FAILED, GenerationJobStatus.QA_FAILED}:
            return job
        request = GenerationRequest.model_validate(job.request_payload)
        contract, contract_version = self._contract(request)
        job.status = GenerationJobStatus.VALIDATING
        job.started_at = job.started_at or datetime.now(UTC)
        self._event(job, "CONTRACT_VALIDATED", {"status": contract_version.status})
        package_record = self.repository.prompt_for_job(job.id)
        prompt_version = next(item for item in package_record.versions if item.version == package_record.current_version)
        package = PromptPackageData.model_validate(prompt_version.payload)
        selection = self.selector.select(self._required(request), preference=request.provider_preference, requested_model=request.model_id)
        candidates = [selection.primary, *selection.fallbacks]
        if job.model_id:
            candidates.sort(key=lambda item: 0 if item.model_id == job.model_id and item.provider_code == job.provider else 1)
        job.status = GenerationJobStatus.PLANNING
        self._event(job, "MODEL_SELECTED", {"provider": candidates[0].provider_code, "model": candidates[0].model_id})
        self._event(job, "PROMPT_COMPILED", {"prompt_hash": prompt_version.prompt_hash})
        fallbacks = candidates[1:]
        model = candidates[0]
        last_error: Exception | None = None
        while job.attempt_count < job.max_attempts:
            job.attempt_count += 1
            attempt_number = job.attempt_count
            retry_type = GenerationRetryType.SAME_MODEL_RETRY if attempt_number == 1 else (GenerationRetryType.FALLBACK_MODEL if job.used_fallback else GenerationRetryType.SAME_MODEL_RETRY)
            attempt = self.repository.add_attempt(
                job, attempt_number=attempt_number, provider=model.provider_code,
                model_id=model.model_id, model_version=model.model_version, retry_type=retry_type,
                reason="initial" if attempt_number == 1 else str(getattr(last_error, "code", "retry")),
                failed_checks=[], changes_applied={"fallback": job.used_fallback},
                prompt_hash=prompt_version.prompt_hash, status="running", started_at=datetime.now(UTC),
            )
            try:
                if self.providers.health(model.provider_code) is ProviderAvailability.UNAVAILABLE:
                    raise ProviderUnavailableError("Provider health is unavailable")
                provider = self.providers.get(model.provider_code)
                adapter_request = self.adapter.translate(package, model.capabilities)
                adapter_request.update({
                    "model_id": model.model_id, "model_version": model.model_version,
                    "seed": job.seed, "generation_type": job.generation_type.value,
                    "mock_output_metadata": request.options.get("mock_output_metadata", {}),
                })
                job.status = GenerationJobStatus.GENERATING
                self._event(job, "PROVIDER_SUBMITTED", {"attempt": attempt_number, "provider": model.provider_code})
                result = self._execute(provider, adapter_request, package, job.generation_type)
                result = provider.normalize_response(result, model_id=model.model_id, model_version=model.model_version)
                attempt.status = "completed"
                attempt.completed_at = datetime.now(UTC)
                attempt.response_reference = result.raw_response_reference
                self._event(job, "PROVIDER_COMPLETED", {"attempt": attempt_number})
                assets = self._store_results(job, contract, contract_version, prompt_version, package, model, result)
                outcome = self._quality_gate(job, contract_version, package, assets)
                self._record_cost(job, attempt, result)
                if outcome == "passed":
                    job.status = GenerationJobStatus.COMPLETED_WITH_FALLBACK if job.used_fallback else GenerationJobStatus.COMPLETED
                    job.completed_at = datetime.now(UTC)
                    self._event(job, "APPROVED", {"assets": [asset.asset_uid for asset, _ in assets]})
                    return job
                job.status = GenerationJobStatus.HUMAN_REVIEW if outcome == "human_review" else GenerationJobStatus.QA_FAILED
                job.failed_at = datetime.now(UTC)
                return job
            except GenerationError as exc:
                last_error = exc
                attempt.status = "failed"
                attempt.error_code = exc.code
                attempt.error_message = str(exc)[:2000]
                attempt.completed_at = datetime.now(UTC)
                plan = self.retry.plan(attempt=attempt_number, max_attempts=job.max_attempts, primary=model, fallbacks=fallbacks, error_code=exc.code)
                if plan is None: break
                job.status = GenerationJobStatus.RETRY_PENDING
                self._event(job, "RETRY_STARTED", {"attempt": attempt_number + 1, "reason": exc.code, "retry_type": plan["retry_type"].value})
                model = plan["model"]
                if plan["retry_type"] is GenerationRetryType.FALLBACK_MODEL:
                    job.used_fallback = True
                    job.provider, job.model_id, job.model_version = model.provider_code, model.model_id, model.model_version
        job.status = GenerationJobStatus.FAILED
        job.failed_at = datetime.now(UTC)
        job.error_code = MaxRetriesExceededError.code
        job.error_message = str(last_error or "Maximum attempts exceeded")[:2000]
        self._event(job, "FAILED", {"code": job.error_code})
        return job

    def cancel_job(self, identifier, *, cancelled_by: str, reason: str):
        job = self._job(identifier)
        if job.status in {GenerationJobStatus.COMPLETED, GenerationJobStatus.COMPLETED_WITH_FALLBACK, GenerationJobStatus.APPROVED, GenerationJobStatus.CANCELLED}:
            return job
        self.queue.cancel(job.job_uid)
        for attempt in reversed(job.attempts):
            if attempt.status == "running" and attempt.response_reference:
                self.providers.get(attempt.provider).cancel_job(attempt.response_reference)
                break
        job.status = GenerationJobStatus.CANCELLED
        job.cancelled_by = cancelled_by
        job.cancel_reason = reason
        self._event(job, "CANCELLED", {"cancelled_by": cancelled_by, "reason": reason})
        return job

    def retry_job(self, identifier):
        job = self._job(identifier)
        if job.attempt_count >= job.max_attempts:
            raise MaxRetriesExceededError("Maximum retry count has been reached")
        job.status = GenerationJobStatus.RETRY_PENDING
        return self.run_job(job.id)

    def get_status(self, identifier): return self._job(identifier)
    def list_jobs(self, **filters): return self.repository.list_jobs(**filters)

    def finalize_asset(self, identifier):
        asset = self.repository.get_asset(identifier)
        if asset is None: raise NotFoundError(f"Generated asset {identifier} was not found")
        current = next(item for item in asset.versions if item.version == asset.current_version)
        if current.qa_status != "passed":
            raise GenerationNotReadyError("Asset cannot be approved until required QA gates pass")
        asset.status = GeneratedAssetStatus.APPROVED
        self._event(asset.job, "APPROVED", {"asset_uid": asset.asset_uid, "version": current.version})
        return asset

    def _contract(self, request):
        contract = self.rules.get_contract(request.generation_contract_id)
        if contract is None: raise NotFoundError(f"Generation contract {request.generation_contract_id} was not found")
        number = request.generation_contract_version or contract.current_version
        version = next((item for item in contract.versions if item.version == number), None)
        if version is None: raise NotFoundError(f"Generation contract version {number} was not found")
        if version.status != "ready":
            raise GenerationNotReadyError(f"GENERATION_NOT_READY: contract status is {version.status}")
        return contract, version

    @staticmethod
    def _required(request):
        return RequiredCapabilities(
            generation_type=request.generation_type,
            aspect_ratio=request.output_specification.aspect_ratio,
            resolution=request.output_specification.resolution,
            duration_seconds=request.output_specification.duration_seconds,
            needs_seed=request.seed is not None, needs_references=bool(request.references),
            needs_mask_editing=request.generation_type is GenerationType.IMAGE_EDIT,
            needs_image_to_video=bool(request.options.get("image_to_video")),
            needs_audio_conditioning=bool(request.options.get("audio_conditioning")),
        )

    def _execute(self, provider, request, package, generation_type):
        if generation_type in {GenerationType.TEXT, GenerationType.COPY, GenerationType.SCRIPT, GenerationType.CAPTIONS, GenerationType.TRANSCRIPT, GenerationType.AUDIO_DESCRIPTION_DRAFT, GenerationType.MUSIC_BRIEF, GenerationType.MULTIMODAL_PACKAGE}: return self.copy.generate(provider, request)
        if generation_type is GenerationType.STORYBOARD: return self.storyboard.generate(provider, request)
        if generation_type in {GenerationType.IMAGE, GenerationType.IMAGE_VARIATION, GenerationType.IMAGE_EDIT}: return self.image.generate(provider, request)
        if generation_type in {GenerationType.VIDEO, GenerationType.VIDEO_SHOT, GenerationType.VIDEO_SEQUENCE}: return self.video.generate(provider, request, package)
        return self.audio.generate(provider, request, package)

    def _store_results(self, job, contract, contract_version, prompt_version, package, model, result):
        provenance = {
            "generation_contract_id": contract.id, "generation_contract_version": contract_version.version,
            "recipe_id": contract.recipe_id, "recipe_version": contract_version.recipe_version,
            "rule_registry_version": contract_version.rule_registry_version,
            "prompt_package_version_id": prompt_version.id, "prompt_hash": prompt_version.prompt_hash,
            "provider": model.provider_code, "model_id": model.model_id, "model_version": model.model_version,
            "seed": job.seed, "reference_asset_ids": [item.asset_id for item in package.reference_assets],
            "character_version": (package.character or {}).get("version"), "brand_version": (package.brand or {}).get("version"),
            "product_version": (package.product or {}).get("version"), "transformations": [],
        }
        stored = []
        for output in result.text_outputs:
            metadata = {**result.metadata, **output}
            asset, version = self.storage.store_text(job, payload=output, provider=model.provider_code,
                model_id=model.model_id, model_version=model.model_version, prompt_hash=prompt_version.prompt_hash,
                seed=job.seed, provenance=provenance, asset_type=job.generation_type.value)
            version.metadata_payload = metadata
            self._provenance(asset, version, provenance, contract, contract_version, prompt_version, model)
            stored.append((asset, version))
        for output in result.media_assets:
            metadata = {**result.metadata, **(output.get("metadata") or {})}
            asset, version = self.storage.store_new(job, content=output.get("content"), mime_type=output.get("mime_type"),
                extension=output.get("extension"), metadata=metadata, provider=model.provider_code,
                model_id=model.model_id, model_version=model.model_version, prompt_hash=prompt_version.prompt_hash,
                seed=job.seed, provenance=provenance, asset_type=job.generation_type.value)
            self._provenance(asset, version, provenance, contract, contract_version, prompt_version, model)
            stored.append((asset, version))
        if not stored:
            raise ProviderUnavailableError("Provider completed without normalized outputs")
        self._event(job, "ASSET_STORED", {"assets": [item[0].asset_uid for item in stored]})
        if result.metadata.get("storyboard"):
            board = self.repository.create_storyboard(storyboard_uid=f"STORY_{uuid4().hex}", job_id=job.id, version=1, metadata_payload={"source": "generation"})
            for index, shot in enumerate(result.metadata["storyboard"]):
                self.repository.add_storyboard_shot(board, shot_id=shot["shot_id"], sequence_index=index, segment_id=shot.get("segment_id"), payload=shot)
                self.repository.add_continuity(job_id=job.id, shot_id=shot["shot_id"], previous_shot_id=shot.get("dependency", {}).get("previous_shot"), state=shot.get("dependency", {}))
        return stored

    def _quality_gate(self, job, contract_version, package, stored):
        self._event(job, "QA_STARTED", {"assets": len(stored)})
        outcomes = []
        failed_checks = []
        for asset, version in stored:
            run, checks = self.qa.run(job, version, package, contract_version.payload)
            outcomes.append(run.status)
            failures = [item for item in checks if item.result is QAResultStatus.FAIL]
            failed_checks.extend(item.check_id for item in failures)
            if run.status == "passed": asset.status = GeneratedAssetStatus.APPROVED
            elif run.status == "human_review": asset.status = GeneratedAssetStatus.HUMAN_REVIEW
            else: asset.status = GeneratedAssetStatus.QA_FAILED
        if "failed" in outcomes:
            self._event(job, "QA_FAILED", {"checks": failed_checks})
            self._human_review(job, contract_version, failed_checks)
            return "failed"
        if "human_review" in outcomes:
            self._event(job, "HUMAN_REVIEW", {"reason": "required QA observation unavailable"})
            self._human_review(job, contract_version, ["UNKNOWN_REQUIRED_QA"])
            return "human_review"
        return "passed"

    def _human_review(self, job, contract_version, checks):
        self.rules.create_review(
            review_uid=f"REVIEW_{uuid4().hex}", evaluation_id=contract_version.evaluation_id,
            rule_id=None, reason=f"Generation QA requires review: {', '.join(checks)}",
            severity="high", context_snapshot={"generation_job_id": job.id, "job_uid": job.job_uid, "failed_checks": checks},
            status=ReviewStatus.PENDING,
        )

    def _provenance(self, asset, version, provenance, contract, contract_version, prompt_version, model):
        c2pa = self.provenance_adapter.attach(version, provenance)
        self.repository.add_provenance(
            provenance_uid=f"PROV_{uuid4().hex}", asset_version_id=version.id,
            contract_id=contract.id, contract_version=contract_version.version,
            recipe_id=contract.recipe_id, recipe_version=contract_version.recipe_version,
            prompt_package_version_id=prompt_version.id, provider=model.provider_code,
            model_id=model.model_id, model_version=model.model_version, seed=version.seed,
            reference_asset_ids=provenance["reference_asset_ids"],
            character_version=str(provenance.get("character_version")) if provenance.get("character_version") is not None else None,
            brand_version=str(provenance.get("brand_version")) if provenance.get("brand_version") is not None else None,
            product_version=str(provenance.get("product_version")) if provenance.get("product_version") is not None else None,
            transformations=provenance["transformations"], c2pa_status=c2pa,
        )

    def _record_cost(self, job, attempt, result):
        cost = float(result.cost_metadata.get("provider_cost", 0.0))
        if job.max_cost is not None and cost > job.max_cost:
            raise ProviderUnavailableError("Generation cost exceeded request budget")
        self.repository.add_cost(
            job_id=job.id, attempt_id=attempt.id, provider_cost=cost,
            currency=str(result.cost_metadata.get("currency", "USD")),
            input_units=float(result.cost_metadata.get("input_units", 0.0)), output_units=float(result.cost_metadata.get("output_units", 0.0)),
            gpu_seconds=float(result.cost_metadata.get("gpu_seconds", 0.0)), generation_seconds=float(result.timing.get("generation_seconds", 0.0)),
            estimated_cost=bool(result.cost_metadata.get("estimated", False)),
        )

    @staticmethod
    def _idempotency_key(contract_id, contract_version, prompt_hash, model, request):
        payload = {"contract": [contract_id, contract_version], "prompt": prompt_hash,
                   "provider": model.provider_code, "model": [model.model_id, model.model_version],
                   "seed": request.seed, "references": [(item.asset_id, item.reference_version, item.checksum) for item in request.references],
                   "output": request.output_specification.model_dump(mode="json")}
        return stable_prompt_hash(payload)

    def _event(self, job, event_type, payload=None):
        return self.repository.add_event(job, event_uid=f"GEVT_{uuid4().hex}", event_type=event_type,
            actor_type="system", actor_id="generation_engine", payload_reference=None, payload=payload)

    def _job(self, identifier):
        job = self.repository.get_job(identifier)
        if job is None: raise NotFoundError(f"Generation job {identifier} was not found")
        return job
