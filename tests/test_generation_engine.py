from pathlib import Path
import json

import pytest

from backend.core.enums import (
    EvidenceType, GeneratedAssetStatus, GenerationJobStatus, GenerationType,
    ProviderPreference, RecipeCreatedBy, RecipeStatus, RecipeType, ReferenceRole,
)
from backend.core.exceptions import (
    GenerationNotReadyError, InvalidGeneratedAssetError, ModelCapabilityError,
    PromptConflictError, ReferenceSafetyError,
)
from backend.core.paths import paths
from backend.db.models.generation import GenerationAttempt, GenerationEvent, ProvenanceRecord, Storyboard
from backend.db.session import session_scope
from backend.generation.model_registry import ModelCapabilityRegistry, ModelSelectorService
from backend.generation.orchestrator import GenerationOrchestrator
from backend.generation.pipelines import AudioGenerationService, VideoAssemblyService
from backend.generation.prompting import PromptCompiler
from backend.generation.providers import MockGenerationProvider, ProviderRegistry
from backend.repositories.recipe_repository import RecipeRepository
from backend.repositories.rule_repository import RuleRepository
from backend.schemas.generation import (
    GenerationRequest, OutputSpecification, ReferenceAssetSpec, RequiredCapabilities,
)
from backend.schemas.rules import GenerationContractBuildRequest
from backend.services.generation_contract_service import GenerationContractService
from sqlalchemy import func, select


def make_contract(session, *, accessibility=None):
    recipes = RecipeRepository(session)
    recipe = recipes.create(
        recipe_uid="RECIPE_GENERATION_TEST", name="Synthetic generation recipe",
        recipe_type=RecipeType.EXPERIMENTAL, status=RecipeStatus.EXPERIMENTAL,
        content_type="video", target_platform="instagram", target_duration_ms=6000,
        target_category="beauty", language="en", current_version=1, recipe_engine_version="1.0.0",
    )
    recipes.add_version(
        recipe, version=1,
        payload={
            "objective": "Create a fictional product demonstration",
            "visual": {"background": "navy"},
            "scene": {"segments": [
                {"segment_id": "SEG_1", "purpose": "hook", "duration": 3.0, "background": "navy", "lighting": "soft"},
                {"segment_id": "SEG_2", "purpose": "product", "duration": 3.0, "background": "navy", "lighting": "soft"},
            ]},
            "copy": {"tone": "clear"}, "audio": {"energy": "medium"},
        },
        constraints={}, confidence=1.0, evidence_type=EvidenceType.OBSERVED,
        evidence={}, provenance={"fixture": "synthetic"}, change_summary="initial",
        created_by=RecipeCreatedBy.SYSTEM, pattern_ids=[], content_ids=[],
    )
    response = GenerationContractService(session).build(GenerationContractBuildRequest(
        recipe_id=recipe.id,
        context={
            "task_id": "TEST-TASK", "character_id": "EMY_TEST", "character_version": 4,
            "character": {"id": "EMY_TEST", "version": 4, "hair": {"color": "dark brown"},
                          "wardrobe": "red dress", "voice": {"profile_id": "VOICE_TEST", "rights_status": "CLEARED"}},
            "brand_id": "MASA_TEST", "brand_version": 2,
            "brand": {"id": "MASA_TEST", "version": 2, "palette": ["navy", "white"], "tone": "clear"},
            "product": {"id": "TEST-SKU-001", "version": 1, "name": "TEST PRODUCT A",
                        "label": "TEST PRODUCT A", "approved_claims": ["water resistant"]},
        },
    ))
    contract = RuleRepository(session).get_contract(response.contract_uid)
    version = next(item for item in contract.versions if item.version == response.version)
    if accessibility:
        version.payload["accessibility_requirements"] = accessibility
    return contract, version


def request_for(contract, generation_type, **kwargs):
    return GenerationRequest(
        generation_contract_id=contract.contract_uid,
        generation_contract_version=contract.current_version,
        generation_type=generation_type, seed=42,
        output_specification=kwargs.pop("output_specification", OutputSpecification()),
        **kwargs,
    )


def test_contract_loading_not_ready_rejection_and_dry_run_no_provider_call() -> None:
    with session_scope() as session:
        contract, version = make_contract(session)
        provider = MockGenerationProvider("mock_local")
        providers = ProviderRegistry()
        providers.register(provider)
        providers.register(MockGenerationProvider("mock_remote_fallback"))
        orchestrator = GenerationOrchestrator(session, providers=providers)
        preview = orchestrator.create_job(request_for(contract, GenerationType.IMAGE, dry_run=True))
        assert preview.selected_provider == "mock_local" and provider.call_count == 0
        version.status = "not_ready"
        with pytest.raises(GenerationNotReadyError):
            orchestrator.create_job(request_for(contract, GenerationType.IMAGE))
        assert provider.call_count == 0


def test_model_capability_selection_local_first_and_text_only_rejected_for_video() -> None:
    with session_scope() as session:
        registry = ModelCapabilityRegistry(session)
        selection = ModelSelectorService(registry).select(
            RequiredCapabilities(generation_type=GenerationType.IMAGE),
            preference=ProviderPreference.LOCAL_FIRST,
        )
        assert selection.primary.locality.value == "local"
        local = next(item for item in registry.repository.list_models() if item.model_id == "mock-multimodal")
        local.capabilities = {**local.capabilities, "outputs": ["text"]}
        with pytest.raises(ModelCapabilityError):
            ModelSelectorService(registry).select(
                RequiredCapabilities(generation_type=GenerationType.VIDEO),
                requested_model="mock-multimodal",
            )


def test_prompt_compiler_injects_versioned_context_and_blocks_conflicts_and_rights() -> None:
    with session_scope() as session:
        contract, version = make_contract(session)
        compiler = PromptCompiler()
        compiled = compiler.compile(version, request_for(contract, GenerationType.IMAGE))
        assert compiled.data.character["version"] == 4
        assert compiled.data.character["hair"]["color"] == "dark brown"
        assert compiled.data.brand["palette"] == ["navy", "white"]
        assert compiled.data.product["label"] == "TEST PRODUCT A"
        version.payload["positive_constraints"] = ["white background"]
        version.payload["negative_constraints"] = ["no white background"]
        with pytest.raises(PromptConflictError, match="PROMPT_CONFLICT"):
            compiler.compile(version, request_for(contract, GenerationType.IMAGE))
        version.payload["negative_constraints"] = []
        prohibited = ReferenceAssetSpec(
            asset_id="REF_BAD", reference_role=ReferenceRole.IDENTITY,
            rights_status="PROHIBITED", approved=False,
        )
        with pytest.raises(ReferenceSafetyError):
            compiler.compile(version, request_for(contract, GenerationType.IMAGE, references=[prohibited]))


@pytest.mark.parametrize("generation_type", [
    GenerationType.COPY, GenerationType.SCRIPT, GenerationType.STORYBOARD,
    GenerationType.IMAGE, GenerationType.VIDEO, GenerationType.AUDIO,
    GenerationType.CAPTIONS, GenerationType.TRANSCRIPT, GenerationType.AUDIO_DESCRIPTION_DRAFT,
])
def test_modality_pipelines_store_hashed_versioned_assets_with_provenance(generation_type) -> None:
    with session_scope() as session:
        contract, _ = make_contract(session)
        job = GenerationOrchestrator(session).create_job(request_for(contract, generation_type))
        assert job.status is GenerationJobStatus.COMPLETED
        assert job.assets and all(asset.status is GeneratedAssetStatus.APPROVED for asset in job.assets)
        current = job.assets[0].versions[0]
        assert len(current.checksum) == 64
        assert not Path(current.relative_path).is_absolute()
        assert paths.resolve_under(paths.project_root, current.relative_path).is_file()
        assert session.scalar(select(func.count()).select_from(ProvenanceRecord)) >= 1
        if generation_type in {GenerationType.STORYBOARD, GenerationType.VIDEO}:
            assert session.scalar(select(func.count()).select_from(Storyboard)) >= 1


@pytest.mark.parametrize(("generation_type", "metadata", "expected_check"), [
    (GenerationType.IMAGE, {"character_hair_color": "black"}, "CHARACTER_HAIR"),
    (GenerationType.IMAGE, {"product_label": "TEST PRODUCT B"}, "PRODUCT_INTEGRITY"),
    (GenerationType.COPY, {"claims": ["waterproof 24 hours"]}, "COPY_CLAIMS"),
    (GenerationType.AUDIO, {"clipped": True}, "AUDIO_VALIDITY"),
    (GenerationType.VIDEO, {"shot_states": [{"wardrobe": "red dress"}, {"wardrobe": "blue dress"}]}, "TEMPORAL_CONTINUITY"),
])
def test_generation_qa_failures_create_review(generation_type, metadata, expected_check) -> None:
    with session_scope() as session:
        contract, _ = make_contract(session)
        job = GenerationOrchestrator(session).create_job(request_for(
            contract, generation_type, options={"mock_output_metadata": metadata},
        ))
        assert job.status is GenerationJobStatus.QA_FAILED
        assert any(expected_check in event.payload.get("checks", []) for event in job.events if event.event_type == "QA_FAILED")


def test_required_captions_prevent_video_approval() -> None:
    with session_scope() as session:
        contract, _ = make_contract(session, accessibility=[{"message": "Captions required"}])
        job = GenerationOrchestrator(session).create_job(request_for(contract, GenerationType.VIDEO))
        assert job.status is GenerationJobStatus.QA_FAILED
        assert all(asset.status is GeneratedAssetStatus.QA_FAILED for asset in job.assets)


def test_provider_fallback_retry_events_cache_cancellation_and_asset_versioning() -> None:
    with session_scope() as session:
        contract, _ = make_contract(session)
        providers = ProviderRegistry()
        primary = MockGenerationProvider("mock_local", fail_times=1)
        fallback = MockGenerationProvider("mock_remote_fallback")
        providers.register(primary)
        providers.register(fallback)
        orchestrator = GenerationOrchestrator(session, providers=providers)
        request = request_for(contract, GenerationType.IMAGE)
        job = orchestrator.create_job(request)
        assert job.status is GenerationJobStatus.COMPLETED_WITH_FALLBACK
        assert job.used_fallback and job.attempt_count == 2
        assert any(event.event_type == "RETRY_STARTED" for event in job.events)
        cached = orchestrator.create_job(request)
        assert cached.job_uid == job.job_uid
        fresh = orchestrator.create_job(request.model_copy(update={"fresh_variation": True}))
        assert fresh.job_uid != job.job_uid

        queued = orchestrator.create_job(request.model_copy(update={"execute": False, "fresh_variation": True}))
        cancelled = orchestrator.cancel_job(queued.job_uid, cancelled_by="tester", reason="synthetic cancellation")
        assert cancelled.status is GenerationJobStatus.CANCELLED

        asset = job.assets[0]
        version_two = orchestrator.storage.add_version(
            asset, content=b"synthetic repaired image", mime_type="image/png", extension="png",
            metadata={"character_hair_color": "dark brown", "product_label": "TEST PRODUCT A", "background_color": "navy"},
            provider="mock_remote_fallback", model_id="mock-fallback", model_version="1.0.0",
            prompt_hash=job.prompt_hash, seed=job.seed, provenance=asset.versions[0].provenance,
            change_reason="repair hand only", repair_type="regional_inpainting",
        )
        assert version_two.version == 2 and asset.versions[0].version == 1
        exhausted_providers = ProviderRegistry()
        exhausted_providers.register(MockGenerationProvider("mock_local", fail_times=99))
        exhausted_providers.register(MockGenerationProvider("mock_remote_fallback", fail_times=99))
        exhausted = GenerationOrchestrator(session, providers=exhausted_providers).create_job(
            request.model_copy(update={"fresh_variation": True, "max_attempts": 2})
        )
        assert exhausted.status is GenerationJobStatus.FAILED
        assert exhausted.attempt_count == 2 and exhausted.error_code == "MAX_RETRIES_EXCEEDED"


def test_audio_rights_mix_plan_video_assembly_and_storage_security() -> None:
    mix = AudioGenerationService.audio_mix_plan(dialogue="DIALOGUE", music="MUSIC", sfx=[{"shot_id": "SHOT_1"}])
    assert mix["ducking_instructions"] and mix["sfx_stem"][0]["shot_id"] == "SHOT_1"
    assembly = VideoAssemblyService().build_plan([{"asset_uid": "SHOT_A", "duration": 2.0}])
    assert assembly["assembly_backend"] == "manifest_only" and assembly["shell_execution"] is False
    injected = VideoAssemblyService().build_plan([{"asset_uid": "SHOT; calc.exe && whoami", "duration": 1.0}])
    assert injected["shell_execution"] is False and injected["ordered_shots"][0]["asset_uid"].startswith("SHOT;")
    assert "subprocess" not in Path("backend/generation/pipelines.py").read_text(encoding="utf-8")
    assert "shell=True" not in Path("backend/generation/pipelines.py").read_text(encoding="utf-8")
    with session_scope() as session:
        contract, _ = make_contract(session)
        orchestrator = GenerationOrchestrator(session)
        with pytest.raises(InvalidGeneratedAssetError):
            orchestrator.storage.validate_reference_path("../escape.png", "image/png")
        with pytest.raises(InvalidGeneratedAssetError):
            orchestrator.storage._validate_content(b"x", "application/x-shellscript", "sh")
        with pytest.raises(InvalidGeneratedAssetError):
            orchestrator.storage._validate_content(b"x", "image/png", "exe")
        job = orchestrator.create_job(request_for(contract, GenerationType.IMAGE, execute=False))
        asset, version = orchestrator.storage.store_new(
            job, content=b"safe mock bytes", mime_type="image/png", extension="png",
            metadata={"untrusted_filename": "../../evil;calc.exe"},
            provider="mock_local", model_id="mock-multimodal", model_version="1.0.0",
            prompt_hash=job.prompt_hash, seed=job.seed, provenance={}, asset_type="image",
        )
        stored = paths.resolve_under(paths.project_root, version.relative_path)
        assert stored.is_relative_to(paths.generated_assets.resolve())
        assert "evil" not in stored.name and "calc" not in stored.name
        raw_path = orchestrator.storage.store_raw_response(job.job_uid, {
            "api_key": "DO_NOT_STORE", "nested": {"access_token": "DO_NOT_STORE"}, "status": "ok",
        })
        raw = json.loads(paths.resolve_under(paths.project_root, raw_path).read_text(encoding="utf-8"))
        assert raw == {"api_key": "[REDACTED]", "nested": {"access_token": "[REDACTED]"}, "status": "ok"}


def test_generation_api_preview_execute_models_assets_and_provenance(api_request) -> None:
    with session_scope() as session:
        contract, _ = make_contract(session)
        contract_uid = contract.contract_uid
    body = request_for(type("ContractRef", (), {"contract_uid": contract_uid, "current_version": 1})(), GenerationType.IMAGE).model_dump(mode="json")
    preview = api_request("POST", "/generation/preview", json={**body, "dry_run": True})
    assert preview.status_code == 200, preview.text
    generated = api_request("POST", "/generation/image", json=body)
    assert generated.status_code == 200, generated.text
    job = generated.json()
    assert job["status"] == "completed"
    asset_uid = job["assets"][0]["asset_uid"]
    assert api_request("GET", "/generation/providers").status_code == 200
    assert api_request("GET", "/generation/models").status_code == 200
    assert api_request("GET", f"/assets/{asset_uid}").status_code == 200
    provenance = api_request("GET", f"/assets/{asset_uid}/provenance")
    assert provenance.status_code == 200 and provenance.json()[0]["contract_version"] == 1
