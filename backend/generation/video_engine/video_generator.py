"""High-level orchestration for EMY's dedicated local AI video engine."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Callable

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError, GenerationError, ModelCapabilityError, ProviderUnavailableError
from backend.generation.video_engine.asset_manager import VideoAssetManager
from backend.generation.video_engine.character_memory import CharacterMemory
from backend.generation.video_engine.comfyui_connector import ComfyUIConnector, ComfyUIResponseError
from backend.generation.video_engine.config import VideoEngineConfig, load_video_config
from backend.generation.video_engine.gpu_worker import GPUWorker
from backend.generation.video_engine.model_router import ModelRouter, VideoStudioCapabilities
from backend.generation.video_engine.prompt_pipeline import PromptPipeline
from backend.generation.video_engine.schemas import (
    BatchGenerationRequest, BatchRecord, VideoGenerationRequest, VideoJob,
)
from backend.generation.video_engine.workflow_manager import WorkflowManager


ConnectorFactory = Callable[[], ComfyUIConnector]


class VideoGenerator:
    def __init__(
        self, *, config: VideoEngineConfig | None = None,
        characters: CharacterMemory | None = None,
        assets: VideoAssetManager | None = None,
        workflows: WorkflowManager | None = None,
        worker: GPUWorker | None = None,
        connector_factory: ConnectorFactory | None = None,
        capability_connector_factory: ConnectorFactory | None = None,
        capabilities: VideoStudioCapabilities | None = None,
    ) -> None:
        self.config = config or load_video_config()
        self.characters = characters or CharacterMemory(
            max_size_bytes=self.config.max_reference_size_bytes,
            max_dimension=self.config.max_reference_dimension,
        )
        self.assets = assets or VideoAssetManager()
        self.workflows = workflows or WorkflowManager()
        self.router = ModelRouter(self.config)
        self.prompts = PromptPipeline(self.config)
        self.worker = worker or GPUWorker(self.config.worker_concurrency)
        settings = get_settings()
        self.connector_factory = connector_factory or (lambda: ComfyUIConnector(
            settings.comfyui_base_url, poll_interval_seconds=self.config.poll_interval_seconds,
            timeout_seconds=self.config.generation_timeout_seconds,
            request_timeout_seconds=self.config.upload_timeout_seconds,
        ))
        self.capabilities = capabilities or VideoStudioCapabilities(
            self.config,
            self.workflows,
            capability_connector_factory or (lambda: ComfyUIConnector(settings.comfyui_base_url, request_timeout_seconds=5.0)),
        )
        self._lock = RLock()

    def create(self, request: VideoGenerationRequest, *, batch_id: str | None = None) -> VideoJob:
        character = self.characters.get(request.character_id)
        model = self.capabilities.select(request)
        prompt = self.prompts.build(request, character)
        job = self.assets.create_job(request, batch_id=batch_id)
        job.prompt_package = prompt.model_dump(mode="json")
        job.model = {
            "model_id": model.model_id, "display_name": model.display_name,
            "workflow_file": model.workflow_file, "fps": model.fps,
        }
        self.assets.save_job(job)
        if request.execute:
            self.worker.submit(job.job_id, lambda: self.run(job.job_id))
        return job

    def run(self, job_id: str) -> None:
        job = self.assets.get_job(job_id)
        if job.status == "COMPLETED":
            return
        connector: ComfyUIConnector | None = None
        try:
            request = VideoGenerationRequest.model_validate(job.request)
            character = self.characters.get(request.character_id)
            if self.worker.is_cancelled(job_id):
                raise ComfyUIResponseError("Generation was cancelled", stage="generation", code="GENERATION_CANCELLED")
            model = self.capabilities.select(request)
            prompt = self.prompts.build(request, character)
            connector = self.connector_factory()
            job.started_at = job.started_at or datetime.now(UTC)
            self._progress(job, 5, "UPLOADING: preparing character identity", status="UPLOADING")
            uploaded = connector.upload_reference(self.characters.reference_path(character))
            self._progress(job, 20, "BUILDING_WORKFLOW: character reference uploaded", status="BUILDING_WORKFLOW")
            workflow = self.workflows.inject(
                self.workflows.load_and_validate(model), model=model, request=request,
                prompt=prompt, uploaded_reference=uploaded,
            )
            self._progress(job, 28, "SUBMITTED: workflow prompt and reference injected", status="SUBMITTED")
            prompt_id = connector.queue_workflow(workflow)
            job.comfyui_prompt_id = prompt_id
            self._progress(job, 32, "GENERATING: queued in ComfyUI", status="GENERATING")
            outputs = connector.wait_for_outputs(
                prompt_id, output_node_ids=model.output_node_ids,
                accepted_extensions=set(self.config.accepted_output_extensions),
                progress=lambda value, stage: self._progress(job, value, f"GENERATING: {stage}", status="GENERATING"),
                cancelled=lambda: self.worker.is_cancelled(job_id),
            )
            output = outputs[0]
            content = connector.download_output(output)
            self._progress(job, 95, "PROCESSING: saving versioned EMY asset", status="PROCESSING")
            asset = self.assets.save_video(
                job=job, content=content, source_filename=output.filename,
                metadata={
                    "model": job.model, "prompt_package": job.prompt_package,
                    "character_id": character.character_id,
                    "character_version": character.version,
                    "reference_checksum": character.reference_checksum,
                    "comfyui_prompt_id": prompt_id, "comfyui_output_node": output.node_id,
                    "request": job.request,
                },
            )
            job.final_video = asset
            job.status = "COMPLETED"
            job.progress = 100
            job.stage = "Video ready in EMY Asset Library"
            job.completed_at = datetime.now(UTC)
            self.assets.save_job(job)
        except Exception as exc:
            cancelled = self.worker.is_cancelled(job_id) or getattr(exc, "code", None) == "GENERATION_CANCELLED"
            job.status = "CANCELLED" if cancelled else ("PARTIAL" if job.final_video else "FAILED")
            job.stage = "Cancelled" if job.status == "CANCELLED" else "Generation failed"
            job.error = self._error_details(exc, job)
            job.completed_at = datetime.now(UTC)
            self.assets.save_job(job)
        finally:
            close = getattr(connector, "close", None)
            if callable(close):
                close()

    def retry(self, job_id: str) -> VideoJob:
        job = self.assets.get_job(job_id)
        if job.status not in {"FAILED", "CANCELLED", "PARTIAL"}:
            raise GenerationError("Only failed or cancelled video jobs can be retried")
        job.status, job.progress, job.stage, job.error = "QUEUED", 0, "Queued for retry", None
        self.assets.save_job(job)
        self.worker.submit(job_id, lambda: self.run(job_id))
        return job

    def cancel(self, job_id: str) -> VideoJob:
        job = self.assets.get_job(job_id)
        if job.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return job
        self.worker.cancel(job_id)
        job.status, job.stage = "CANCELLED", "Cancellation requested"
        self.assets.save_job(job)
        return job

    def create_batch(self, request: BatchGenerationRequest) -> BatchRecord:
        batch_id = f"VBATCH_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        jobs = []
        for item in request.items:
            job_request = VideoGenerationRequest(
                character_id=request.character_id, recipe_id=request.recipe_id,
                creative_idea=item.idea, video_duration=item.video_duration or request.video_duration,
                style=item.style or request.style,
                camera_motion=item.camera_motion or request.camera_motion,
                aspect_ratio=item.aspect_ratio or request.aspect_ratio,
                model_id=item.model_id or request.model_id, execute=request.execute,
                calendar_item_id=item.calendar_item_id, publish_at=item.publish_at,
            )
            jobs.append(self.create(job_request, batch_id=batch_id))
        record = BatchRecord(
            batch_id=batch_id, status="QUEUED", job_ids=[item.job_id for item in jobs],
            total=len(jobs), created_at=datetime.now(UTC),
        )
        self.assets.save_batch(record)
        return record

    def batch_status(self, batch_id: str) -> dict[str, object]:
        record = self.assets.get_batch(batch_id)
        jobs = [self.assets.get_job(job_id) for job_id in record.job_ids]
        statuses = {job.status for job in jobs}
        if statuses == {"COMPLETED"}:
            status = "COMPLETED"
        elif statuses <= {"FAILED", "CANCELLED"}:
            status = "FAILED"
        elif statuses & {"UPLOADING", "BUILDING_WORKFLOW", "SUBMITTED", "GENERATING", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED", "PARTIAL"}:
            status = "RUNNING"
        else:
            status = "QUEUED"
        return {
            **record.model_dump(mode="json"), "status": status,
            "progress": round(sum(job.progress for job in jobs) / len(jobs)) if jobs else 0,
            "completed": sum(job.status == "COMPLETED" for job in jobs),
            "failed": sum(job.status in {"FAILED", "CANCELLED"} for job in jobs),
            "jobs": [job.model_dump(mode="json") for job in jobs],
        }

    def recover_pending(self) -> int:
        recovered = 0
        for job in self.assets.list_jobs(limit=1000):
            if job.status not in {"QUEUED", "UPLOADING", "BUILDING_WORKFLOW", "SUBMITTED", "GENERATING", "PROCESSING"} or not job.request.get("execute", True):
                continue
            if job.status != "QUEUED":
                job.status, job.stage = "QUEUED", "Recovered after backend restart"
                self.assets.save_job(job)
            self.worker.submit(job.job_id, lambda job_id=job.job_id: self.run(job_id))
            recovered += 1
        return recovered

    def _progress(self, job: VideoJob, value: int, stage: str, *, status: str | None = None) -> None:
        with self._lock:
            current = self.assets.get_job(job.job_id)
            if current.status == "CANCELLED":
                return
            if status:
                job.status = status
            job.progress = max(job.progress, min(value, 99))
            job.stage = stage
            self.assets.save_job(job)

    @staticmethod
    def _error_details(exc: Exception, job: VideoJob) -> dict[str, object]:
        if isinstance(exc, ComfyUIResponseError):
            details: dict[str, object] = exc.details()
        elif isinstance(exc, ModelCapabilityError):
            message = str(exc)
            details = {"code": message.split(":", 1)[0] or "NO_LOCAL_VIDEO_MODEL", "message": message}
        elif isinstance(exc, ConfigurationError):
            details = {"code": "INVALID_WORKFLOW", "message": str(exc)}
        elif isinstance(exc, ProviderUnavailableError):
            details = {"code": "COMFYUI_API_UNAVAILABLE", "message": str(exc)}
        elif isinstance(exc, GenerationError):
            details = {"code": getattr(exc, "code", "GENERATION_FAILED"), "message": str(exc)}
        else:
            details = {"code": "GENERATION_FAILED", "message": str(exc)}
        details["job_id"] = job.job_id
        if job.comfyui_prompt_id:
            details["prompt_id"] = job.comfyui_prompt_id
        return details
