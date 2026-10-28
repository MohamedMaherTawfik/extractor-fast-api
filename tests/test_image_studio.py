import json
from pathlib import Path
import shutil
from uuid import uuid4

import pytest

from backend.core.exceptions import ConfigurationError, ModelCapabilityError, ReferenceSafetyError
from backend.core.paths import paths
from backend.generation.video_engine.comfyui_connector import ComfyOutput
from backend.generation.video_engine.gpu_worker import GPUWorker
from backend.image_studio.capabilities import ImageStudioCapabilities
from backend.image_studio.config import load_image_studio_config
from backend.image_studio.prompting import PRESETS, apply_preset, build_prompt
from backend.image_studio.schemas import CameraAngle, ImageDimensions, ImageModelConfig, ImageStudioConfig, ImageStudioSettings, InjectionTarget, ModelFileRequirement, options_catalog
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
        "5": {"class_type": "SamplerNode", "inputs": {"seed": 0, "width": 1024, "height": 1024}},
        "9": {"class_type": "OutputNode", "inputs": {"images": ["4", 0]}},
    }
    (root / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")
    model = ImageModelConfig(
        model_id="verified_test_model", display_name="Verified test model", workflow_file="workflow.json",
        model_files=[ModelFileRequirement(path="checkpoints/checkpoint.safetensors", workflow_value="checkpoint.safetensors")],
        dimensions={"4:5": ImageDimensions(width=512, height=640)}, output_node_ids=["9"],
        injections={
            "positive_prompt": InjectionTarget(node_id="1", input="text"),
            "negative_prompt": InjectionTarget(node_id="2", input="text"),
            "character_reference": InjectionTarget(node_id="3", input="image"),
            "product_reference": InjectionTarget(node_id="4", input="image"),
            "width": InjectionTarget(node_id="5", input="width"),
            "height": InjectionTarget(node_id="5", input="height"),
            "seed": InjectionTarget(node_id="5", input="seed"),
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


def test_default_config_loads_the_sd15_gtx1070_dimension_profile():
    load_image_studio_config.cache_clear()
    config = load_image_studio_config()
    profile = config.dimension_profiles["sd15_gtx1070"]
    assert (profile["1:1"].width, profile["1:1"].height) == (512, 512)
    assert (profile["4:5"].width, profile["4:5"].height) == (512, 640)
    assert (profile["3:4"].width, profile["3:4"].height) == (576, 768)
    assert (profile["9:16"].width, profile["9:16"].height) == (432, 768)
    assert (profile["16:9"].width, profile["16:9"].height) == (768, 432)


def test_reference_upload_validates_real_content_extension_mime_and_dimensions(tmp_path):
    storage = ImageStudioStorage(tmp_path / "state", tmp_path / "assets", tmp_path / "references")
    assert storage.inspect_upload(filename="character.png", content_type="image/png", content=png(), max_size=10000, max_dimension=1000)[:2] == ("image/png", ".png")
    with pytest.raises(ReferenceSafetyError, match="REFERENCE_UPLOAD_FAILED"):
        storage.inspect_upload(filename="character.jpg", content_type="image/jpeg", content=png(), max_size=10000, max_dimension=1000)
    with pytest.raises(ReferenceSafetyError, match="dimensions"):
        storage.inspect_upload(filename="product.png", content_type="image/png", content=png(20, 20), max_size=10000, max_dimension=1000)


def test_workflow_validation_rejects_missing_required_input(tmp_path):
    model = ImageModelConfig(model_id="test", display_name="Test", workflow_file="broken.json", model_files=[ModelFileRequirement(path="checkpoints/model", workflow_value="model")], output_node_ids=["9"], injections={
        "positive_prompt": InjectionTarget(node_id="1", input="text"), "negative_prompt": InjectionTarget(node_id="1", input="negative"),
        "character_reference": InjectionTarget(node_id="1", input="character"), "product_reference": InjectionTarget(node_id="1", input="product"),
    })
    (tmp_path / "broken.json").write_text(json.dumps({"1": {"class_type": "Known", "inputs": {"text": ""}}, "9": {"class_type": "Output", "inputs": {}}}), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="INVALID_WORKFLOW"):
        ImageWorkflowManager(tmp_path).load_and_validate(model)


def test_workflow_validation_uses_live_node_metadata_for_class_links_and_models(tmp_path):
    model = ImageModelConfig(model_id="test", display_name="Test", workflow_file="invalid.json", model_files=[ModelFileRequirement(path="checkpoints/model", workflow_value="model")], output_node_ids=["2"], injections={
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
    assert complete.seed == 13
    assert [workflow["5"]["inputs"]["seed"] for workflow in fake.workflows] == [13, 14]
    retry = engine.regenerate(job.job_id, same_seed=True)
    assert retry.seed == 13 and retry.status == "QUEUED"


def test_seedless_generation_persists_random_base_seed_and_uses_sequential_seeds(image_runtime):
    engine, fake = image_runtime
    job = engine.create(
        character_filename="character.png", character_mime="image/png", character_content=png(),
        product_filename="product.png", product_mime="image/png", product_content=png(),
        settings=ImageStudioSettings(model_id="verified_test_model", number_of_images=4), execute=False,
    )

    engine.run(job.job_id)

    complete = engine.storage.get_job(job.job_id)
    assert complete.seed is not None
    assert 0 <= complete.seed <= 2_147_483_647
    assert complete.settings["seed"] == complete.seed
    assert [workflow["5"]["inputs"]["seed"] for workflow in fake.workflows] == [
        complete.seed,
        complete.seed + 1,
        complete.seed + 2,
        complete.seed + 3,
    ]


def test_same_seed_regeneration_reuses_persisted_random_base_seed(image_runtime):
    engine, _ = image_runtime
    source = engine.create(
        character_filename="character.png", character_mime="image/png", character_content=png(),
        product_filename="product.png", product_mime="image/png", product_content=png(),
        settings=ImageStudioSettings(model_id="verified_test_model"), execute=False,
    )
    engine.run(source.job_id)
    persisted = engine.storage.get_job(source.job_id).seed

    retry = engine.regenerate(source.job_id, same_seed=True)

    assert persisted is not None
    assert retry.seed == persisted
    assert retry.settings["seed"] == persisted


def test_model_specific_sd15_dimensions_are_injected_and_unconfigured_ratios_fail(tmp_path):
    workflow = {
        "0": {"class_type": "ModelNode", "inputs": {"model_name": "checkpoint.safetensors"}},
        "1": {"class_type": "Inputs", "inputs": {"text": "", "negative": "", "character": "", "product": "", "width": 0, "height": 0}},
        "9": {"class_type": "Output", "inputs": {"images": ["1", 0]}},
    }
    (tmp_path / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")
    model = ImageModelConfig(
        model_id="sd15", display_name="SD1.5", workflow_file="workflow.json",
        model_files=[ModelFileRequirement(path="checkpoints/checkpoint.safetensors", workflow_value="checkpoint.safetensors")],
        dimension_profile="sd15_gtx1070", output_node_ids=["9"],
        injections={
            "positive_prompt": InjectionTarget(node_id="1", input="text"),
            "negative_prompt": InjectionTarget(node_id="1", input="negative"),
            "character_reference": InjectionTarget(node_id="1", input="character"),
            "product_reference": InjectionTarget(node_id="1", input="product"),
            "width": InjectionTarget(node_id="1", input="width"),
            "height": InjectionTarget(node_id="1", input="height"),
        },
    )
    config = ImageStudioConfig(
        dimension_profiles={
            "sd15_gtx1070": {
                "1:1": ImageDimensions(width=512, height=512),
                "4:5": ImageDimensions(width=512, height=640),
                "3:4": ImageDimensions(width=576, height=768),
                "9:16": ImageDimensions(width=432, height=768),
                "16:9": ImageDimensions(width=768, height=432),
            }
        },
        models=[model],
    )
    manager = ImageWorkflowManager(tmp_path)
    compiled = manager.inject(
        workflow, model=config.models[0], settings=ImageStudioSettings(aspect_ratio="9:16"),
        prompt="positive", negative_prompt="negative", character_reference="character.png",
        product_reference="product.png", seed=10,
    )
    assert compiled["1"]["inputs"]["width"] == 432
    assert compiled["1"]["inputs"]["height"] == 768
    with pytest.raises(ConfigurationError, match="not configured"):
        manager.inject(
            workflow, model=config.models[0], settings=ImageStudioSettings(aspect_ratio="Custom"),
            prompt="positive", negative_prompt="negative", character_reference="character.png",
            product_reference="product.png", seed=10,
        )


def test_model_file_path_and_workflow_loader_value_are_validated_independently(tmp_path):
    models_root = tmp_path / "models"
    workflow_root = tmp_path / "workflows"
    (models_root / "checkpoints").mkdir(parents=True)
    workflow_root.mkdir()
    (models_root / "checkpoints" / "checkpoint.safetensors").write_bytes(b"model")
    (workflow_root / "workflow.json").write_text(json.dumps({
        "0": {"class_type": "ModelNode", "inputs": {"model_name": "checkpoint.safetensors"}},
        "1": {"class_type": "Inputs", "inputs": {"text": "", "negative": "", "character": "", "product": ""}},
        "9": {"class_type": "Output", "inputs": {"images": ["1", 0]}},
    }), encoding="utf-8")
    model = ImageModelConfig(
        model_id="sd15", display_name="SD1.5", workflow_file="workflow.json",
        model_files=[ModelFileRequirement(
            path="checkpoints/checkpoint.safetensors",
            workflow_value="checkpoint.safetensors",
        )],
        output_node_ids=["9"], injections={
            "positive_prompt": InjectionTarget(node_id="1", input="text"),
            "negative_prompt": InjectionTarget(node_id="1", input="negative"),
            "character_reference": InjectionTarget(node_id="1", input="character"),
            "product_reference": InjectionTarget(node_id="1", input="product"),
        },
    )
    capabilities = ImageStudioCapabilities(ImageStudioConfig(
        comfyui_install_path=str(tmp_path), models_path=str(models_root),
        workflows_path=str(workflow_root), models=[model],
    ))

    assert capabilities._missing_for_model(model, None) == []

    model.model_files[0].workflow_value = "wrong-loader-value.safetensors"
    with pytest.raises(ConfigurationError, match="wrong-loader-value"):
        ImageWorkflowManager(workflow_root).load_and_validate(model)


def test_arbitrary_unet_choices_do_not_create_a_capability_false_positive(tmp_path):
    (tmp_path / "models").mkdir()
    (tmp_path / "custom_nodes").mkdir()
    (tmp_path / "workflow.json").write_text(json.dumps({
        "0": {"class_type": "ModelNode", "inputs": {"model_name": "missing.safetensors"}},
        "1": {"class_type": "Inputs", "inputs": {"text": "", "negative": "", "character": "", "product": ""}},
        "9": {"class_type": "Output", "inputs": {"images": ["1", 0]}},
    }), encoding="utf-8")
    model = ImageModelConfig(
        model_id="missing", display_name="Missing image model", workflow_file="workflow.json",
        model_files=[ModelFileRequirement(
            path="checkpoints/missing.safetensors",
            workflow_value="missing.safetensors",
        )],
        output_node_ids=["9"], injections={
            "positive_prompt": InjectionTarget(node_id="1", input="text"),
            "negative_prompt": InjectionTarget(node_id="1", input="negative"),
            "character_reference": InjectionTarget(node_id="1", input="character"),
            "product_reference": InjectionTarget(node_id="1", input="product"),
        },
    )
    config = ImageStudioConfig(
        comfyui_install_path=str(tmp_path), workflows_path=str(tmp_path), models=[model],
    )
    capabilities = ImageStudioCapabilities(config)
    capabilities._probe_api = lambda: ({
        "reachable": True, "api_available": True, "checks": {},
    }, {
        "UNETLoader": {"input": {"required": {"unet_name": [[
            "wan2.1_t2v_1.3B_fp16.safetensors",
            "qwen_image_vae.safetensors",
            "clip_l.safetensors",
        ]]}}},
        "ModelNode": {"input": {"required": {"model_name": [["missing.safetensors"]]}}, "output": ["MODEL"]},
        "Inputs": {"input": {"required": {
            "text": ["STRING"], "negative": ["STRING"],
            "character": ["STRING"], "product": ["STRING"],
        }}, "output": ["IMAGE"]},
        "Output": {"input": {"required": {"images": ["IMAGE"]}}, "output": [], "output_node": True},
    })

    report = capabilities.report()

    assert report["runtime_models"]["unets"]
    assert report["runtime_models"]["generation_model_files_detected"] is False
    assert report["generation_available"] is False
    assert "MODEL_FILE_NOT_FOUND" in {
        item["code"] for item in report["model_checks"][0]["missing_requirements"]
    }
    assert "NO_SUITABLE_IMAGE_MODEL" in {item["code"] for item in report["missing_requirements"]}


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
        model_files=[ModelFileRequirement(path="checkpoints/checkpoint.safetensors", workflow_value="checkpoint.safetensors")], output_node_ids=["9"],
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
