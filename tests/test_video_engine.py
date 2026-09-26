import json
import shutil
from uuid import uuid4

import pytest

from backend.core.exceptions import ConfigurationError, ModelCapabilityError
from backend.core.paths import paths
from backend.generation.video_engine.asset_manager import VideoAssetManager
from backend.generation.video_engine.character_memory import CharacterMemory
from backend.generation.video_engine.comfyui_connector import ComfyOutput, ComfyUIResponseError
from backend.generation.video_engine.config import VideoEngineConfig, VideoModelConfig, load_video_config
from backend.generation.video_engine.gpu_worker import GPUWorker
from backend.generation.video_engine.schemas import BatchGenerationRequest, ContentCalendarItem, VideoGenerationRequest
from backend.generation.video_engine.video_generator import VideoGenerator
from backend.generation.video_engine.workflow_manager import WorkflowManager


def png(width: int = 32, height: int = 32) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"


class ReadyCapabilities:
    def __init__(self, model):
        self.model = model

    def select(self, request):
        assert request.model_id in {None, self.model.model_id}
        return self.model

    def report(self):
        return {"comfyui": "READY", "generation_available": True, "models": [{"model_id": self.model.model_id}]}


class FakeComfyUI:
    def __init__(self):
        self.workflow = None

    def upload_reference(self, source):
        assert source.exists()
        return "emy/reference.png"

    def queue_workflow(self, workflow):
        self.workflow = workflow
        return "PROMPT_TEST"

    def wait_for_outputs(self, prompt_id, *, output_node_ids, accepted_extensions, progress, cancelled):
        assert prompt_id == "PROMPT_TEST" and output_node_ids == ["30"] and ".mp4" in accepted_extensions and not cancelled()
        progress(75, "Rendering in ComfyUI")
        return [ComfyOutput(filename="render.mp4", subfolder="EMY", output_type="output", node_id="30")]

    def download_output(self, output):
        assert output.filename == "render.mp4"
        return b"\x00\x00\x00\x18ftypisomsynthetic-mp4-content"


def ready_config(root):
    workflow = {
        "1": {"class_type": "ModelNode", "inputs": {"model_name": "verified-model.safetensors"}},
        "6": {"class_type": "PromptNode", "inputs": {"text": ""}},
        "7": {"class_type": "PromptNode", "inputs": {"text": ""}},
        "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
        "20": {"class_type": "VideoNode", "inputs": {"positive": ["6", 0], "negative": ["7", 0], "image": ["10", 0], "width": 576, "height": 1024, "length": 80, "seed": -1}},
        "30": {"class_type": "SaveVideo", "inputs": {"images": ["20", 0], "frame_rate": 16}},
    }
    (root / "verified.json").write_text(json.dumps(workflow), encoding="utf-8")
    model = VideoModelConfig(
        model_id="verified_test_video", display_name="Verified test video", workflow_file="verified.json",
        verified=True, model_files=["verified-model.safetensors"], output_node_ids=["30"],
        injections={
            "positive_prompt": {"node_id": "6", "input": "text"},
            "negative_prompt": {"node_id": "7", "input": "text"},
            "reference_image": {"node_id": "10", "input": "image"},
            "width": {"node_id": "20", "input": "width"},
            "height": {"node_id": "20", "input": "height"},
            "num_frames": {"node_id": "20", "input": "length"},
            "fps": {"node_id": "30", "input": "frame_rate"},
            "seed": {"node_id": "20", "input": "seed"},
        },
    )
    shipped = load_video_config()
    return VideoEngineConfig(default_model=model.model_id, models=[model], recipes=shipped.recipes), model


@pytest.fixture
def video_runtime():
    root = paths.project_root / ".tmp" / f"video-engine-{uuid4().hex}"
    root.mkdir(parents=True)
    config, model = ready_config(root)
    fake = FakeComfyUI()
    worker = GPUWorker(1)
    engine = VideoGenerator(
        config=config, characters=CharacterMemory(root / "characters"),
        assets=VideoAssetManager(root / "state", root / "assets"), workflows=WorkflowManager(root),
        worker=worker, connector_factory=lambda: fake, capabilities=ReadyCapabilities(model),
    )
    yield engine, fake
    worker.shutdown()
    shutil.rmtree(root, ignore_errors=True)


def add_character(engine):
    return engine.characters.create(
        name="EMY Test Character", image=png(), mime_type="image/png", filename="reference.png",
        identity_data={"hair": "dark waves", "face": "approved reference"},
        style_profile={"render": "photoreal"}, recurring_attributes=["red wardrobe"],
        negative_constraints=["blue wardrobe"],
    )


def test_character_prompt_workflow_comfy_render_and_asset_persistence(video_runtime):
    engine, fake = video_runtime
    character = add_character(engine)
    request = VideoGenerationRequest(
        character_id=character.character_id, creative_idea="serum advertisement",
        video_duration=5, aspect_ratio="9:16", model_id="verified_test_video", seed=42, execute=False,
    )
    created = engine.create(request)
    assert created.status == "QUEUED"
    assert "face identity" in created.prompt_package["positive_prompt"]
    assert "blue wardrobe" in created.prompt_package["negative_prompt"]
    engine.run(created.job_id)
    completed = engine.assets.get_job(created.job_id)
    assert completed.status == "COMPLETED" and completed.progress == 100
    assert completed.final_video["version"] == 1
    assert completed.final_video["metadata"]["reference_checksum"] == character.reference_checksum
    assert engine.assets.asset_path(completed.final_video["asset_id"])[0].read_bytes().startswith(b"\x00\x00\x00\x18ftyp")
    assert fake.workflow["6"]["inputs"]["text"].startswith("Create a polished cinematic")
    assert fake.workflow["10"]["inputs"]["image"] == "emy/reference.png"
    assert fake.workflow["20"]["inputs"]["length"] == 80
    assert fake.workflow["20"]["inputs"]["seed"] == 42
    engine.assets.mark_saved(completed.final_video["asset_id"])
    assert engine.assets.get_job(created.job_id).final_video["saved"] is True


def test_default_templates_are_not_routable_or_reported_ready(api_request):
    response = api_request("GET", "/video-studio/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["models"] == [] and payload["generation_available"] is False
    codes = {item["code"] for item in payload["missing_requirements"]}
    assert "NO_VIDEO_WORKFLOW_CONFIGURED" in codes and "NO_LOCAL_VIDEO_MODEL" in codes
    config = load_video_config()
    with pytest.raises(ModelCapabilityError, match="NO_LOCAL_VIDEO_MODEL"):
        # Disabled templates cannot pass the router even if ComfyUI becomes available.
        from backend.generation.video_engine.model_router import ModelRouter
        ModelRouter(config).select(VideoGenerationRequest(character_id="CHAR_test", creative_idea="safe rejection", execute=False))


def test_strict_video_workflow_validator_rejects_missing_node_bad_link_and_output_type(tmp_path):
    config, model = ready_config(tmp_path)
    invalid = {
        "1": {"class_type": "Model", "inputs": {"model_name": "verified-model.safetensors"}},
        "6": {"class_type": "Prompt", "inputs": {"text": "ok"}},
        "7": {"class_type": "Prompt", "inputs": {"text": "ok"}},
        "10": {"class_type": "Load", "inputs": {"image": "ref.png"}},
        "20": {"class_type": "Video", "inputs": {"positive": ["missing", 0], "negative": ["7", 0], "image": ["10", 1], "width": 1, "height": 1, "length": 1, "seed": 1}},
        "30": {"class_type": "Output", "inputs": {"value": ["20", 0], "frame_rate": 16}},
    }
    (tmp_path / "verified.json").write_text(json.dumps(invalid), encoding="utf-8")
    object_info = {
        "Model": {"input": {"required": {"model_name": [["verified-model.safetensors"]]}}, "output": ["MODEL"]},
        "Prompt": {"input": {"required": {"text": ["STRING"]}}, "output": ["STRING"]},
        "Load": {"input": {"required": {"image": ["STRING"]}}, "output": ["IMAGE"]},
        "Video": {"input": {"required": {"positive": ["STRING"], "negative": ["STRING"], "image": ["IMAGE"], "width": ["INT"], "height": ["INT"], "length": ["INT"], "seed": ["INT"]}}, "output": ["IMAGE"]},
        "Output": {"input": {"required": {"value": ["STRING"], "frame_rate": ["INT"]}}, "output": []},
    }
    with pytest.raises(ConfigurationError, match="INVALID_WORKFLOW") as raised:
        WorkflowManager(tmp_path).load_and_validate(model, object_info)
    assert "absent node missing" in str(raised.value)


def test_batch_generation_preserves_content_calendar_links(video_runtime):
    engine, _ = video_runtime
    character = add_character(engine)
    batch = engine.create_batch(BatchGenerationRequest(
        character_id=character.character_id, model_id="verified_test_video", execute=False,
        items=[ContentCalendarItem(idea="serum teaser", calendar_item_id="CAL-1"), ContentCalendarItem(idea="night routine", calendar_item_id="CAL-2")],
    ))
    jobs = engine.assets.list_jobs(batch_id=batch.batch_id)
    assert batch.total == 2 and len(jobs) == 2
    assert {item.request["calendar_item_id"] for item in jobs} == {"CAL-1", "CAL-2"}
    assert all(item.prompt_package["script"]["beats"] for item in jobs)


def test_upload_failure_is_persisted_separately_from_prompt_failure(video_runtime):
    engine, _ = video_runtime
    character = add_character(engine)
    job = engine.create(VideoGenerationRequest(character_id=character.character_id, creative_idea="upload failure", model_id="verified_test_video", execute=False))

    class UploadFailure:
        def upload_reference(self, source):
            raise ComfyUIResponseError("connection refused", stage="upload", code="COMFYUI_UPLOAD_FAILED", response_body={"reason": "refused"})

    engine.connector_factory = UploadFailure
    engine.run(job.job_id)
    failed = engine.assets.get_job(job.job_id)
    assert failed.status == "FAILED"
    assert failed.error["code"] == "COMFYUI_UPLOAD_FAILED"
    assert failed.error["stage"] == "upload"
    assert "prompt_id" not in failed.error


def test_character_reference_rejects_fake_or_mismatched_image_content(tmp_path):
    from backend.core.exceptions import ReferenceSafetyError

    memory = CharacterMemory(tmp_path / "characters")
    with pytest.raises(ReferenceSafetyError, match="valid PNG"):
        memory.create(name="Fake", image=b"not-an-image", mime_type="image/png", filename="fake.png")
    with pytest.raises(ReferenceSafetyError, match="MIME type"):
        memory.create(name="Mismatch", image=png(), mime_type="image/jpeg", filename="reference.jpg")
