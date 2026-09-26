import json
from pathlib import Path
import shutil
from uuid import uuid4

import pytest

from backend.core.exceptions import ConfigurationError, ModelCapabilityError, ReferenceSafetyError
from backend.core.paths import paths
from backend.generation.video_engine.comfyui_connector import ComfyOutput
from backend.generation.video_engine.gpu_worker import GPUWorker
from backend.image_studio.config import load_image_studio_config
from backend.image_studio.prompting import PRESETS, apply_preset, build_prompt
from backend.image_studio.schemas import CameraAngle, ImageModelConfig, ImageStudioConfig, ImageStudioSettings, InjectionTarget, options_catalog
from backend.image_studio.service import ImageStudioService
from backend.image_studio.storage import ImageStudioStorage
from backend.image_studio.workflow import ImageWorkflowManager


def png(width: int = 32, height: int = 32) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"


class ReadyCapabilities:
    def __init__(self, root: Path, model: ImageModelConfig):
        self.root = root
        self._model = model

    def report(self):
        return {"comfyui": "READY", "models": [{"model_id": self._model.model_id}], "custom_nodes": []}

    def model(self, model_id):
        assert model_id in {None, self._model.model_id}
        return self._model

    def workflow_root(self):
        return self.root


class NoGenerationCapabilities:
    def __init__(self, root: Path):
        self.root = root

    def report(self):
        return {
            "comfyui": "READY",
            "generation_available": False,
            "models": [],
            "missing_requirements": [{
                "code": "NO_LOCAL_IMAGE_MODEL",
                "message": "No local image model is available.",
            }],
        }

    def workflow_root(self):
        return self.root


class FakeComfyUI:
    def __init__(self):
        self.workflows = []

    def upload_reference(self, source):
        assert source.exists()
        return source.name

    def queue_workflow(self, workflow):
        self.workflows.append(workflow)
        return f"PROMPT_{len(self.workflows)}"

    def wait_for_outputs(self, prompt_id, *, output_node_ids, accepted_extensions, progress, cancelled):
        assert output_node_ids == ["9"] and ".png" in accepted_extensions and not cancelled()
        progress(75, "Rendering in ComfyUI")
        return [ComfyOutput(filename="output.png", subfolder="", output_type="output", node_id="9")]

    def download_output(self, output):
        return png()


@pytest.fixture
def image_runtime():
    root = paths.project_root / ".tmp" / f"image-studio-{uuid4().hex}"
    root.mkdir(parents=True)
    workflow = {
        "0": {"class_type": "ModelNode", "inputs": {"model_name": "checkpoint.safetensors"}},
        "1": {"class_type": "PromptNode", "inputs": {"text": ""}},
        "2": {"class_type": "PromptNode", "inputs": {"text": ""}},
        "3": {"class_type": "ImageNode", "inputs": {"image": ""}},
        "4": {"class_type": "ImageNode", "inputs": {"image": ""}},
        "9": {"class_type": "OutputNode", "inputs": {"images": ["4", 0]}},
    }
    (root / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")
    model = ImageModelConfig(
        model_id="verified_test_model", display_name="Verified test model", workflow_file="workflow.json",
        model_files=["checkpoint.safetensors"], output_node_ids=["9"],
        injections={
            "positive_prompt": InjectionTarget(node_id="1", input="text"),
            "negative_prompt": InjectionTarget(node_id="2", input="text"),
            "character_reference": InjectionTarget(node_id="3", input="image"),
            "product_reference": InjectionTarget(node_id="4", input="image"),
        },
    )
    config = ImageStudioConfig(models=[model])
    fake = FakeComfyUI(); worker = GPUWorker(1)
    engine = ImageStudioService(
        config=config, storage=ImageStudioStorage(root / "state", root / "assets", root / "references"),
        capabilities=ReadyCapabilities(root, model), worker=worker, connector_factory=lambda: fake,
    )
    yield engine, fake
    worker.shutdown()
    shutil.rmtree(root, ignore_errors=True)


def test_prompt_builder_camera_mapping_negative_prompt_and_preset():
    settings = apply_preset(ImageStudioSettings(preset_id="E_COMMERCE"))
    assert settings.shot_type == PRESETS["E_COMMERCE"]["shot_type"]
    prompt, negative = build_prompt(ImageStudioSettings(camera_angle="Low Angle", creative_direction="keep the bottle centered"))
    assert "camera below eye level" in prompt and "keep the bottle centered" in prompt
    assert "identity drift" in negative and "wrong label" in negative


def test_every_schema_camera_angle_builds_a_prompt_without_a_mapping_key_error():
    for camera_angle in CameraAngle.__args__:
        settings = ImageStudioSettings(camera_angle=camera_angle)
        if camera_angle == "Custom":
            # Custom is still a valid literal fallback when no custom camera field exists.
            assert "Camera: Custom" in build_prompt(settings)[0]
        else:
            assert "Camera:" in build_prompt(settings)[0]


def test_every_image_studio_preset_matches_the_public_settings_schema():
    for preset_id in PRESETS:
        settings = apply_preset(ImageStudioSettings(preset_id=preset_id))
        assert settings.preset_id == preset_id
        ImageStudioSettings.model_validate(settings.model_dump())
    assert "Close-Up Angle" in options_catalog()["camera_angle"]


def test_reference_upload_validates_real_content_extension_mime_and_dimensions(tmp_path):
    storage = ImageStudioStorage(tmp_path / "state", tmp_path / "assets", tmp_path / "references")
    assert storage.inspect_upload(filename="character.png", content_type="image/png", content=png(), max_size=10000, max_dimension=1000)[:2] == ("image/png", ".png")
    with pytest.raises(ReferenceSafetyError, match="REFERENCE_UPLOAD_FAILED"):
        storage.inspect_upload(filename="character.jpg", content_type="image/jpeg", content=png(), max_size=10000, max_dimension=1000)
    with pytest.raises(ReferenceSafetyError, match="dimensions"):
        storage.inspect_upload(filename="product.png", content_type="image/png", content=png(20, 20), max_size=10000, max_dimension=1000)


def test_workflow_validation_rejects_missing_required_input(tmp_path):
    model = ImageModelConfig(model_id="test", display_name="Test", workflow_file="broken.json", model_files=["model"], output_node_ids=["9"], injections={
        "positive_prompt": InjectionTarget(node_id="1", input="text"), "negative_prompt": InjectionTarget(node_id="1", input="negative"),
        "character_reference": InjectionTarget(node_id="1", input="character"), "product_reference": InjectionTarget(node_id="1", input="product"),
    })
    (tmp_path / "broken.json").write_text(json.dumps({"1": {"class_type": "Known", "inputs": {"text": ""}}, "9": {"class_type": "Output", "inputs": {}}}), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="INVALID_WORKFLOW"):
        ImageWorkflowManager(tmp_path).load_and_validate(model)


def test_workflow_validation_uses_live_node_metadata_for_class_links_and_models(tmp_path):
    model = ImageModelConfig(model_id="test", display_name="Test", workflow_file="invalid.json", model_files=["model"], output_node_ids=["2"], injections={
        "positive_prompt": InjectionTarget(node_id="1", input="text"), "negative_prompt": InjectionTarget(node_id="1", input="negative"),
        "character_reference": InjectionTarget(node_id="1", input="character"), "product_reference": InjectionTarget(node_id="1", input="product"),
    })
    (tmp_path / "invalid.json").write_text(json.dumps({
        "0": {"class_type": "Model", "inputs": {"model_name": "model"}},
        "1": {"class_type": "Prompt", "inputs": {"text": "hello", "negative": "", "character": ["99", 0], "product": "image.png"}},
        "2": {"class_type": "Output", "inputs": {"images": ["1", 0]}},
    }), encoding="utf-8")
    object_info = {
        "Model": {"input": {"required": {"model_name": [["model"]]}}, "output": ["MODEL"]},
        "Prompt": {"input": {"required": {"text": ["STRING"], "negative": ["STRING"], "character": ["IMAGE"], "product": [["image.png"]]}}, "output": ["STRING"]},
        "Output": {"input": {"required": {"images": ["IMAGE"]}}, "output": []},
    }
    with pytest.raises(ConfigurationError, match="absent node 99"):
        ImageWorkflowManager(tmp_path).load_and_validate(model, object_info)


def test_successful_job_stores_prompt_references_outputs_and_regeneration(image_runtime):
    engine, fake = image_runtime
    job = engine.create(
        character_filename="character.png", character_mime="image/png", character_content=png(),
        product_filename="product.png", product_mime="image/png", product_content=png(),
        settings=ImageStudioSettings(model_id="verified_test_model", number_of_images=2, seed=13), execute=False,
    )
    engine.run(job.job_id)
    complete = engine.storage.get_job(job.job_id)
    assert complete.status == "COMPLETED" and len(complete.output_images) == 2
    assert "preserve identity" in complete.prompt and fake.workflows[0]["3"]["inputs"]["image"].startswith("character_")
    retry = engine.regenerate(job.job_id, same_seed=True)
    assert retry.seed == 13 and retry.status == "QUEUED"


def test_default_capabilities_report_no_unverified_model_or_workflow(api_request):
    response = api_request("GET", "/image-studio/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["models"] == [] and "NO_SUITABLE_IMAGE_MODEL" in {item["code"] for item in payload["missing_requirements"]}
    assert api_request("GET", "/image-studio/models").json() == []
    options = api_request("GET", "/image-studio/options")
    assert options.status_code == 200 and "CameraAngle" not in options.json()


def test_missing_model_configuration_blocks_job_before_saving_references():
    root = paths.project_root / ".tmp" / f"image-studio-{uuid4().hex}"
    config = ImageStudioConfig(models=[])
    engine = ImageStudioService(
        config=config,
        storage=ImageStudioStorage(root / "state", root / "assets", root / "references"),
        capabilities=NoGenerationCapabilities(root),
    )
    try:
        with pytest.raises(ModelCapabilityError, match="IMAGE_GENERATION_UNAVAILABLE"):
            engine.create(character_filename="character.png", character_mime="image/png", character_content=png(), product_filename="product.png", product_mime="image/png", product_content=png(), settings=ImageStudioSettings(), execute=False)
        assert engine.storage.list_jobs() == []
    finally:
        engine.worker.shutdown()
        shutil.rmtree(root, ignore_errors=True)


def test_image_cancel_marks_job_cancelled_without_generic_failure(image_runtime):
    engine, _ = image_runtime
    job = engine.create(
        character_filename="character.png", character_mime="image/png", character_content=png(),
        product_filename="product.png", product_mime="image/png", product_content=png(),
        settings=ImageStudioSettings(model_id="verified_test_model"), execute=False,
    )
    cancelled = engine.cancel(job.job_id)
    assert cancelled.status == "CANCELLED"
    assert engine.storage.get_job(job.job_id).status == "CANCELLED"


def test_image_recovery_only_resubmits_executable_active_jobs():
    root = paths.project_root / ".tmp" / f"image-recovery-{uuid4().hex}"
    root.mkdir(parents=True)
    workflow = {
        "0": {"class_type": "ModelNode", "inputs": {"model_name": "checkpoint.safetensors"}},
        "1": {"class_type": "PromptNode", "inputs": {"text": ""}},
        "2": {"class_type": "PromptNode", "inputs": {"text": ""}},
        "3": {"class_type": "ImageNode", "inputs": {"image": ""}},
        "4": {"class_type": "ImageNode", "inputs": {"image": ""}},
        "9": {"class_type": "OutputNode", "inputs": {"images": ["4", 0]}},
    }
    (root / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")
    model = ImageModelConfig(
        model_id="verified_test_model", display_name="Verified test model", workflow_file="workflow.json",
        model_files=["checkpoint.safetensors"], output_node_ids=["9"],
        injections={
            "positive_prompt": InjectionTarget(node_id="1", input="text"),
            "negative_prompt": InjectionTarget(node_id="2", input="text"),
            "character_reference": InjectionTarget(node_id="3", input="image"),
            "product_reference": InjectionTarget(node_id="4", input="image"),
        },
    )

    class RecordingWorker:
        def __init__(self): self.submitted = []
        def submit(self, job_id, task): self.submitted.append(job_id)
        def is_cancelled(self, job_id): return False
        def cancel(self, job_id): return True

    worker = RecordingWorker()
    storage = ImageStudioStorage(root / "state", root / "assets", root / "references")
    engine = ImageStudioService(
        config=ImageStudioConfig(models=[model]), storage=storage,
        capabilities=ReadyCapabilities(root, model), worker=worker, connector_factory=FakeComfyUI,
    )
    dry = engine.create(
        character_filename="character.png", character_mime="image/png", character_content=png(),
        product_filename="product.png", product_mime="image/png", product_content=png(),
        settings=ImageStudioSettings(model_id=model.model_id), execute=False,
    )
    live = engine.create(
        character_filename="character.png", character_mime="image/png", character_content=png(),
        product_filename="product.png", product_mime="image/png", product_content=png(),
        settings=ImageStudioSettings(model_id=model.model_id), execute=False,
    )
    live.execute = True
    live.status = "GENERATING"
    storage.save_job(live)

    assert engine.recover_pending() == 1
    assert worker.submitted == [live.job_id]
    assert storage.get_job(live.job_id).status == "QUEUED"
    assert storage.get_job(dry.job_id).status == "QUEUED"
    shutil.rmtree(root, ignore_errors=True)
