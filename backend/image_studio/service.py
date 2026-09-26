"""Durable local orchestration for configured ComfyUI image workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from random import SystemRandom
from threading import RLock
from typing import Callable

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError, GenerationError, ModelCapabilityError, ProviderUnavailableError
from backend.generation.video_engine.comfyui_connector import ComfyUIConnector, ComfyUIResponseError
from backend.generation.video_engine.gpu_worker import GPUWorker
from backend.image_studio.capabilities import ImageStudioCapabilities
from backend.image_studio.config import load_image_studio_config
from backend.image_studio.prompting import apply_preset, build_prompt
from backend.image_studio.schemas import ImageModelConfig, ImageStudioConfig, ImageStudioJob, ImageStudioSettings
from backend.image_studio.storage import ImageStudioStorage
from backend.image_studio.workflow import ImageWorkflowManager


ConnectorFactory = Callable[[], ComfyUIConnector]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class ImageStudioService:
    def __init__(self, *, config: ImageStudioConfig | None = None, storage: ImageStudioStorage | None = None, capabilities: ImageStudioCapabilities | None = None, worker: GPUWorker | None = None, connector_factory: ConnectorFactory | None = None) -> None:
        self.config = config or load_image_studio_config()
        self.storage = storage or ImageStudioStorage()
        self.capabilities = capabilities or ImageStudioCapabilities(self.config)
        self.worker = worker or GPUWorker(self.config.worker_concurrency)
        self.workflows = ImageWorkflowManager(self.capabilities.workflow_root())
        settings = get_settings()
        self.connector_factory = connector_factory or (lambda: ComfyUIConnector(
            settings.comfyui_base_url, poll_interval_seconds=self.config.poll_interval_seconds,
            timeout_seconds=self.config.generation_timeout_seconds,
            request_timeout_seconds=self.config.upload_timeout_seconds,
        ))
        self._lock = RLock()

    def create(self, *, character_filename: str | None, character_mime: str | None, character_content: bytes, product_filename: str | None, product_mime: str | None, product_content: bytes, settings: ImageStudioSettings, execute: bool = True) -> ImageStudioJob:
        settings = apply_preset(settings)
        readiness = self.capabilities.report()
        generation_available = readiness.get("generation_available", bool(readiness.get("models")))
        if not generation_available:
            reasons = readiness.get("missing_requirements", [])
            detail = "; ".join(
                str(item.get("message") or item.get("code"))
                for item in reasons[:3]
                if isinstance(item, dict)
            )
            raise ModelCapabilityError(
                f"IMAGE_GENERATION_UNAVAILABLE: {detail or 'No verified local ComfyUI image workflow is available.'}"
            )
        character_info = self.storage.inspect_upload(filename=character_filename, content_type=character_mime, content=character_content, max_size=self.config.max_reference_size_bytes, max_dimension=self.config.max_image_dimension)
        product_info = self.storage.inspect_upload(filename=product_filename, content_type=product_mime, content=product_content, max_size=self.config.max_reference_size_bytes, max_dimension=self.config.max_image_dimension)
        job_id = self.storage.new_job_id()
        character = self.storage.save_reference(job_id=job_id, kind="character", original_filename=character_filename or "character", content=character_content, mime_type=character_info[0], width=character_info[2], height=character_info[3])
        product = self.storage.save_reference(job_id=job_id, kind="product", original_filename=product_filename or "product", content=product_content, mime_type=product_info[0], width=product_info[2], height=product_info[3])
        prompt, negative_prompt = build_prompt(settings)
        job = self.storage.create_job(settings=settings, prompt=prompt, negative_prompt=negative_prompt, character_image=character, product_image=product, job_id=job_id, execute=execute)
        if execute:
            self.worker.submit(job.job_id, lambda: self.run(job.job_id))
        return job

    def run(self, job_id: str) -> None:
        job = self.storage.get_job(job_id)
        if job.status in {"COMPLETED", "CANCELLED"}:
            return
        connector: ComfyUIConnector | None = None
        try:
            report = self.capabilities.report()
            if report["comfyui"] != "READY":
                raise ProviderUnavailableError("COMFYUI_API_UNAVAILABLE: ComfyUI is not reachable at the configured base URL")
            settings = ImageStudioSettings.model_validate(job.settings)
            model = self.capabilities.model(settings.model_id)
            workflow = self.workflows.load_and_validate(model)
            job.model = {"model_id": model.model_id, "display_name": model.display_name, "workflow_file": model.workflow_file}
            job.workflow = workflow
            job.started_at = job.started_at or datetime.now(UTC)
            connector = self.connector_factory()
            self._progress(job, "UPLOADING", 5, "Uploading validated reference images to ComfyUI")
            uploaded_character = connector.upload_reference(self.storage.reference_path(job.character_image))
            uploaded_product = connector.upload_reference(self.storage.reference_path(job.product_image))
            self._progress(job, "BUILDING_WORKFLOW", 20, "Building and validating configured image workflow")
            requested = int(settings.number_of_images)
            base_seed = settings.seed
            supports_seed = "seed" in model.injections
            for index in range(requested):
                if self.worker.is_cancelled(job.job_id):
                    raise ComfyUIResponseError(
                        "Image generation was cancelled", stage="generation", code="GENERATION_CANCELLED"
                    )
                seed = (base_seed + index) if base_seed is not None and supports_seed else None
                compiled = self.workflows.inject(workflow, model=model, settings=settings, prompt=job.prompt, negative_prompt=job.negative_prompt, character_reference=uploaded_character, product_reference=uploaded_product, seed=seed)
                self._progress(job, "SUBMITTED", 25 + int(index * 55 / requested), f"Submitting image {index + 1} of {requested} to ComfyUI")
                prompt_id = connector.queue_workflow(compiled)
                job.comfyui_prompt_ids.append(prompt_id)
                self.storage.save_job(job)
                self._progress(job, "GENERATING", 30 + int(index * 55 / requested), f"Generating image {index + 1} of {requested}")
                outputs = connector.wait_for_outputs(prompt_id, output_node_ids=model.output_node_ids, accepted_extensions=IMAGE_EXTENSIONS, progress=lambda value, stage: self._progress(job, "GENERATING", min(88, value), stage), cancelled=lambda: self.worker.is_cancelled(job.job_id))
                self._progress(job, "PROCESSING", 90, "Validating and storing generated image assets")
                for output in outputs:
                    if len(job.output_images) >= requested:
                        break
                    content = connector.download_output(output)
                    asset = self.storage.save_output(job=job, content=content, filename=output.filename, metadata={
                        "model": job.model, "prompt": job.prompt, "negative_prompt": job.negative_prompt,
                        "settings": job.settings, "seed": seed, "comfyui_prompt_id": prompt_id,
                        "comfyui_output_node": output.node_id, "character_checksum": job.character_image.checksum,
                        "product_checksum": job.product_image.checksum,
                    })
                    job.output_images.append(asset)
                    self.storage.save_job(job)
            if not job.output_images:
                raise ComfyUIResponseError(
                    "ComfyUI did not return an image output", stage="output", code="COMFYUI_OUTPUT_MISSING"
                )
            if len(job.output_images) < requested:
                self._progress(job, "PARTIAL", 100, "Only part of the requested image set was generated")
            else:
                self._progress(job, "COMPLETED", 100, "Image generation completed")
            job.completed_at = datetime.now(UTC)
            self.storage.save_job(job)
        except Exception as exc:
            self._fail(job, exc)
        finally:
            close = getattr(connector, "close", None)
            if callable(close):
                close()

    def cancel(self, job_id: str) -> ImageStudioJob:
        job = self.storage.get_job(job_id)
        if job.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return job
        self.worker.cancel(job_id)
        job.status = "CANCELLED"
        job.stage = "Cancellation requested"
        job.completed_at = datetime.now(UTC)
        self.storage.save_job(job)
        return job

    def recover_pending(self) -> int:
        recovered = 0
        active = {"QUEUED", "UPLOADING", "BUILDING_WORKFLOW", "SUBMITTED", "GENERATING", "PROCESSING"}
        for job in self.storage.list_jobs(limit=1000):
            if job.status not in active or not job.execute:
                continue
            if job.status != "QUEUED":
                job.status = "QUEUED"
                job.stage = "Recovered after backend restart"
                self.storage.save_job(job)
            self.worker.submit(job.job_id, lambda job_id=job.job_id: self.run(job_id))
            recovered += 1
        return recovered

    def regenerate(self, job_id: str, *, same_seed: bool = False) -> ImageStudioJob:
        source = self.storage.get_job(job_id)
        settings = ImageStudioSettings.model_validate(source.settings)
        settings.seed = source.seed if same_seed else SystemRandom().randint(0, 2_147_483_647)
        return self.create(
            character_filename=source.character_image.filename, character_mime=source.character_image.mime_type,
            character_content=self.storage.reference_path(source.character_image).read_bytes(),
            product_filename=source.product_image.filename, product_mime=source.product_image.mime_type,
            product_content=self.storage.reference_path(source.product_image).read_bytes(), settings=settings,
        )

    def _progress(self, job: ImageStudioJob, status: str, progress: int, stage: str) -> None:
        with self._lock:
            current = self.storage.get_job(job.job_id)
            if current.status == "CANCELLED":
                return
            job.status = status
            job.progress = max(job.progress, max(0, min(100, progress)))
            job.stage = stage
            self.storage.save_job(job)

    def _fail(self, job: ImageStudioJob, exc: Exception) -> None:
        if isinstance(exc, ComfyUIResponseError):
            details = exc.details()
        elif isinstance(exc, ModelCapabilityError):
            details = {"code": "MISSING_CUSTOM_NODE" if str(exc).startswith("MISSING_CUSTOM_NODE") else "MODEL_NOT_AVAILABLE", "message": str(exc)}
        elif isinstance(exc, ConfigurationError):
            details = {"code": "INVALID_WORKFLOW", "message": str(exc)}
        elif isinstance(exc, ProviderUnavailableError):
            message = str(exc)
            details = {
                "code": "COMFYUI_API_UNAVAILABLE" if message.startswith("COMFYUI_API_UNAVAILABLE") else "GENERATION_FAILED",
                "message": message,
            }
        elif isinstance(exc, GenerationError):
            details = {"code": getattr(exc, "code", "GENERATION_FAILED"), "message": str(exc)}
        else:
            details = {"code": "GENERATION_FAILED", "message": str(exc)}
        details["job_id"] = job.job_id
        if job.comfyui_prompt_ids:
            details["prompt_id"] = job.comfyui_prompt_ids[-1]
        cancelled = self.worker.is_cancelled(job.job_id) or details.get("code") == "GENERATION_CANCELLED"
        job.status = "CANCELLED" if cancelled else ("PARTIAL" if job.output_images else "FAILED")
        job.progress = 100
        if job.status == "CANCELLED":
            job.stage = "Cancelled"
        else:
            job.stage = "Generation finished with partial output" if job.output_images else "Image generation failed"
        job.error = details
        job.completed_at = datetime.now(UTC)
        self.storage.save_job(job)
