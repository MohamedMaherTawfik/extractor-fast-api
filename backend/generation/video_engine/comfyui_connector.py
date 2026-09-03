"""Minimal, dependency-light client for the local ComfyUI API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Callable
from urllib.parse import quote
from uuid import uuid4

import httpx

from backend.core.exceptions import ProviderUnavailableError


@dataclass(frozen=True)
class ComfyOutput:
    filename: str
    subfolder: str
    output_type: str
    node_id: str


class ComfyUIConnector:
    def __init__(
        self, base_url: str, *, poll_interval_seconds: float = 1.0,
        timeout_seconds: int = 3600, client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.client_id = f"emy-video-{uuid4().hex}"
        self._client = client or httpx.Client(base_url=self.base_url, timeout=60.0)

    def upload_reference(self, source: Path) -> str:
        try:
            with source.open("rb") as handle:
                response = self._client.post(
                    "/upload/image", files={"image": (source.name, handle, self._mime(source))},
                    data={"type": "input", "overwrite": "true"},
                )
            response.raise_for_status()
            payload = response.json()
            name = payload.get("name")
            if not name:
                raise ValueError("missing uploaded image name")
            subfolder = payload.get("subfolder") or ""
            return f"{subfolder}/{name}".lstrip("/")
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise ProviderUnavailableError(f"ComfyUI reference upload failed: {exc}") from exc

    def queue_workflow(self, workflow: dict[str, Any]) -> str:
        try:
            response = self._client.post("/prompt", json={"prompt": workflow, "client_id": self.client_id})
            response.raise_for_status()
            payload = response.json()
            if payload.get("node_errors"):
                raise ProviderUnavailableError(f"ComfyUI rejected workflow nodes: {payload['node_errors']}")
            prompt_id = payload.get("prompt_id")
            if not prompt_id:
                raise ValueError("missing prompt_id")
            return str(prompt_id)
        except ProviderUnavailableError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailableError(f"ComfyUI queue request failed: {exc}") from exc

    def wait_for_outputs(
        self, prompt_id: str, *, output_node_ids: list[str] | None = None,
        progress: Callable[[int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> list[ComfyOutput]:
        started = monotonic()
        reported = -1
        while monotonic() - started < self.timeout_seconds:
            if cancelled and cancelled():
                self.interrupt()
                raise ProviderUnavailableError("Video generation was cancelled")
            history = self._history(prompt_id)
            entry = history.get(prompt_id) if isinstance(history, dict) else None
            if entry:
                status = entry.get("status") or {}
                if status.get("status_str") == "error":
                    messages = status.get("messages") or []
                    raise ProviderUnavailableError(f"ComfyUI generation failed: {messages}")
                outputs = self._outputs(entry.get("outputs") or {}, output_node_ids or [])
                if outputs:
                    if progress:
                        progress(90, "Retrieving rendered video")
                    return outputs
            queued, running = self._queue_position(prompt_id)
            value = 35 if queued else 55 if running else min(85, 40 + int((monotonic() - started) / 5))
            if value != reported and progress:
                progress(value, "Rendering in ComfyUI" if running else "Waiting in ComfyUI queue")
                reported = value
            sleep(self.poll_interval_seconds)
        raise ProviderUnavailableError("ComfyUI generation timed out")

    def download_output(self, output: ComfyOutput) -> bytes:
        url = (
            f"/view?filename={quote(output.filename)}&subfolder={quote(output.subfolder)}"
            f"&type={quote(output.output_type)}"
        )
        try:
            response = self._client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Unable to retrieve ComfyUI output: {exc}") from exc

    def interrupt(self) -> None:
        try:
            self._client.post("/interrupt")
        except httpx.HTTPError:
            pass

    def _history(self, prompt_id: str) -> dict[str, Any]:
        try:
            response = self._client.get(f"/history/{quote(prompt_id)}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Unable to read ComfyUI history: {exc}") from exc

    def _queue_position(self, prompt_id: str) -> tuple[bool, bool]:
        try:
            response = self._client.get("/queue")
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError:
            return False, False
        running = any(self._prompt_id(item) == prompt_id for item in payload.get("queue_running", []))
        queued = any(self._prompt_id(item) == prompt_id for item in payload.get("queue_pending", []))
        return queued, running

    @staticmethod
    def _prompt_id(item: Any) -> str | None:
        return str(item[1]) if isinstance(item, list) and len(item) > 1 else None

    @staticmethod
    def _outputs(outputs: dict[str, Any], allowed_nodes: list[str]) -> list[ComfyOutput]:
        found = []
        for node_id, payload in outputs.items():
            if allowed_nodes and str(node_id) not in allowed_nodes:
                continue
            for key in ("videos", "gifs", "images"):
                for item in payload.get(key, []) if isinstance(payload, dict) else []:
                    filename = str(item.get("filename", ""))
                    if Path(filename).suffix.lower() not in {".mp4", ".webm", ".mov", ".gif"}:
                        continue
                    found.append(ComfyOutput(
                        filename=filename, subfolder=str(item.get("subfolder", "")),
                        output_type=str(item.get("type", "output")), node_id=str(node_id),
                    ))
        return found

    @staticmethod
    def _mime(source: Path) -> str:
        return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(source.suffix.lower(), "image/png")
