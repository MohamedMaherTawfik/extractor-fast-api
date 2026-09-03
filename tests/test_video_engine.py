import shutil
from uuid import uuid4

import pytest

from backend.core.exceptions import ModelCapabilityError
from backend.core.paths import paths
from backend.generation.video_engine.asset_manager import VideoAssetManager
from backend.generation.video_engine.character_memory import CharacterMemory
from backend.generation.video_engine.comfyui_connector import ComfyOutput
from backend.generation.video_engine.config import load_video_config
from backend.generation.video_engine.gpu_worker import GPUWorker
from backend.generation.video_engine.model_router import ModelRouter
from backend.generation.video_engine.schemas import BatchGenerationRequest, ContentCalendarItem, VideoGenerationRequest
from backend.generation.video_engine.video_generator import VideoGenerator
from backend.generation.video_engine.workflow_manager import WorkflowManager


class FakeComfyUI:
    def __init__(self):
        self.workflow = None

    def upload_reference(self, source):
        assert source.exists()
        return "emy/reference.png"

    def queue_workflow(self, workflow):
        self.workflow = workflow
        return "PROMPT_TEST"

    def wait_for_outputs(self, prompt_id, *, output_node_ids, progress, cancelled):
        assert prompt_id == "PROMPT_TEST" and output_node_ids == ["30"] and not cancelled()
        progress(75, "Rendering in ComfyUI")
        return [ComfyOutput(filename="render.mp4", subfolder="EMY", output_type="output", node_id="30")]

    def download_output(self, output):
        assert output.filename == "render.mp4"
        return b"synthetic-mp4-content"


@pytest.fixture
def video_runtime():
    root = paths.project_root / ".tmp" / f"video-engine-{uuid4().hex}"
    fake = FakeComfyUI()
    worker = GPUWorker(1)
    engine = VideoGenerator(
        config=load_video_config(), characters=CharacterMemory(root / "characters"),
        assets=VideoAssetManager(root / "state", root / "assets"),
        worker=worker, connector_factory=lambda: fake,
    )
    yield engine, fake
    worker.shutdown()
    shutil.rmtree(root, ignore_errors=True)


def add_character(engine):
    return engine.characters.create(
        name="EMY Test Character", image=b"reference-image", mime_type="image/png",
        identity_data={"hair": "dark waves", "face": "approved reference"},
        style_profile={"render": "photoreal"}, recurring_attributes=["red wardrobe"],
        negative_constraints=["blue wardrobe"],
    )


def test_character_prompt_workflow_comfy_render_and_asset_persistence(video_runtime):
    engine, fake = video_runtime
    character = add_character(engine)
    request = VideoGenerationRequest(
        character_id=character.character_id, creative_idea="serum advertisement",
        video_duration=5, aspect_ratio="9:16", model_id="wan_video", seed=42, execute=False,
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
    assert engine.assets.asset_path(completed.final_video["asset_id"])[0].read_bytes() == b"synthetic-mp4-content"
    assert fake.workflow["6"]["inputs"]["text"].startswith("Create a polished cinematic")
    assert fake.workflow["10"]["inputs"]["image"] == "emy/reference.png"
    assert fake.workflow["20"]["inputs"]["length"] == 80
    assert fake.workflow["20"]["inputs"]["seed"] == 42
    engine.assets.mark_saved(completed.final_video["asset_id"])
    assert engine.assets.get_job(created.job_id).final_video["saved"] is True


def test_all_open_models_are_routable_and_capabilities_are_enforced(video_runtime):
    engine, _ = video_runtime
    character = add_character(engine)
    assert {item["model_id"] for item in engine.router.public_models()} == {
        "wan_video", "hunyuan_video", "animatediff", "stable_video_diffusion"
    }
    for model_id in ("wan_video", "hunyuan_video", "animatediff", "stable_video_diffusion"):
        request = VideoGenerationRequest(
            character_id=character.character_id, creative_idea="model routing",
            model_id=model_id, aspect_ratio="16:9", video_duration=5, execute=False,
        )
        model = ModelRouter(engine.config).select(request)
        injected = WorkflowManager().inject(
            WorkflowManager().load(model), model=model, request=request,
            prompt=engine.prompts.build(request, character), uploaded_reference="ref.png",
        )
        assert injected["10"]["inputs"]["image"] == "ref.png"
    with pytest.raises(ModelCapabilityError):
        ModelRouter(engine.config).select(VideoGenerationRequest(
            character_id=character.character_id, creative_idea="too long",
            model_id="stable_video_diffusion", video_duration=20, execute=False,
        ))


def test_batch_generation_preserves_content_calendar_links(video_runtime):
    engine, _ = video_runtime
    character = add_character(engine)
    batch = engine.create_batch(BatchGenerationRequest(
        character_id=character.character_id, execute=False,
        items=[
            ContentCalendarItem(idea="serum teaser", calendar_item_id="CAL-1"),
            ContentCalendarItem(idea="night routine", calendar_item_id="CAL-2"),
        ],
    ))
    jobs = engine.assets.list_jobs(batch_id=batch.batch_id)
    assert batch.total == 2 and len(jobs) == 2
    assert {item.request["calendar_item_id"] for item in jobs} == {"CAL-1", "CAL-2"}
    assert all(item.prompt_package["script"]["beats"] for item in jobs)
    status = engine.batch_status(batch.batch_id)
    assert status["status"] == "QUEUED" and status["progress"] == 0


def test_video_studio_discovery_api(api_request):
    response = api_request("GET", "/video-studio/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "comfyui"
    assert len(payload["models"]) == 4
    assert any(item["recipe_id"] == "EMY_CHARACTER_V1" for item in payload["recipes"])
