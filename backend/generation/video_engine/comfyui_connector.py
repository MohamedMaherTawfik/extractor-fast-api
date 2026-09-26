"""Small, safe client for the local ComfyUI HTTP API.

The connector deliberately keeps ComfyUI's response body with every failure.
That body is often the only place ComfyUI identifies a rejected node or input.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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


class ComfyUIResponseError(ProviderUnavailableError):
    """A ComfyUI failure with stable stage and preserved diagnostic fields."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        code: str = "COMFYUI_API_UNAVAILABLE",
        http_status: int | None = None,
        response_body: Any = None,
        node_errors: Any = None,
    ) -> None:
        self.stage = stage
        self.code = code
        self.http_status = http_status
        self.response_body = response_body
        self.node_errors = node_errors
        super().__init__(message)

    def details(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "stage": self.stage,
            "http_status": self.http_status,
            "response_body": self.response_body,
            "node_errors": self.node_errors,
        }


class ComfyUIConnector:
    def __init__(
        self,
        base_url: str,
        *,
        poll_interval_seconds: float = 1.0,
        timeout_seconds: int = 3600,
        request_timeout_seconds: float = 300.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.client_id = f"emy-generation-{uuid4().hex}"
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.base_url, timeout=request_timeout_seconds, trust_env=False
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def system_stats(self) -> dict[str, Any]:
        return self._get_object("/system_stats", stage="system_stats")

    def queue(self) -> dict[str, Any]:
        return self._get_object("/queue", stage="queue")

    def object_info(self) -> dict[str, Any]:
        return self._get_object("/object_info", stage="object_info")

    def runtime_status(self) -> dict[str, Any]:
        """Probe the three read-only endpoints required for safe preflight."""

        checks: dict[str, dict[str, Any]] = {}
        payloads: dict[str, dict[str, Any]] = {}
        methods = {
            "system_stats": self.system_stats,
            "queue": self.queue,
            "object_info": self.object_info,
        }
        for name, method in methods.items():
            try:
                payload = method()
                payloads[name] = payload
                checks[name] = {"reachable": True, "http_status": 200}
            except ComfyUIResponseError as exc:
                checks[name] = {
                    "reachable": False,
                    "http_status": exc.http_status,
                    "error": str(exc),
                    "response_body": exc.response_body,
                }
        system = payloads.get("system_stats", {})
        queue = payloads.get("queue", {})
        object_info = payloads.get("object_info")
        system_info = system.get("system") if isinstance(system.get("system"), dict) else {}
        if "system_stats" in checks:
            checks["system_stats"].update({
                "comfyui_version": system_info.get("comfyui_version"),
                "device_types": [item.get("type") for item in system.get("devices", []) if isinstance(item, dict)],
            })
        if "queue" in checks:
            checks["queue"].update({
                "running": len(queue.get("queue_running", [])),
                "pending": len(queue.get("queue_pending", [])),
            })
        if isinstance(object_info, dict) and "object_info" in checks:
            checks["object_info"]["node_count"] = len(object_info)
        return {
            "reachable": any(check.get("reachable") for check in checks.values()),
            "api_available": all(check.get("reachable") for check in checks.values()),
            "checks": checks,
            "object_info": object_info,
        }

    def upload_reference(self, source: Path) -> str:
        try:
            with source.open("rb") as handle:
                response = self._client.post(
                    "/upload/image",
                    files={"image": (source.name, handle, self._mime(source))},
                    data={"type": "input", "overwrite": "true"},
                )
            payload = _body(response)
            if not response.is_success:
                raise ComfyUIResponseError(
                    "ComfyUI reference upload failed", stage="upload",
                    code="COMFYUI_UPLOAD_FAILED", http_status=response.status_code,
                    response_body=payload, node_errors=_node_errors(payload),
                )
            if not isinstance(payload, dict) or not isinstance(payload.get("name"), str) or not payload["name"]:
                raise ComfyUIResponseError(
                    "ComfyUI upload response did not contain an image name", stage="upload",
                    code="COMFYUI_UPLOAD_FAILED", http_status=response.status_code, response_body=payload,
                )
            name = _safe_output_component(payload["name"], field="uploaded image name")
            subfolder = _safe_subfolder(payload.get("subfolder") or "")
            return f"{subfolder}/{name}".lstrip("/")
        except ComfyUIResponseError:
            raise
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise ComfyUIResponseError(
                "ComfyUI reference upload failed", stage="upload", code="COMFYUI_UPLOAD_FAILED",
                response_body={"exception": str(exc)},
            ) from exc

    def queue_workflow(self, workflow: dict[str, Any]) -> str:
        try:
            response = self._client.post("/prompt", json={"prompt": workflow, "client_id": self.client_id})
            payload = _body(response)
            if not response.is_success:
                raise ComfyUIResponseError(
                    "ComfyUI prompt request failed", stage="submit", code="COMFYUI_PROMPT_REJECTED",
                    http_status=response.status_code, response_body=payload, node_errors=_node_errors(payload),
                )
            if not isinstance(payload, dict):
                raise ComfyUIResponseError(
                    "ComfyUI prompt response was not a JSON object", stage="submit",
                    code="COMFYUI_PROMPT_REJECTED", http_status=response.status_code, response_body=payload,
                )
            if payload.get("node_errors"):
                raise ComfyUIResponseError(
                    "ComfyUI rejected workflow nodes", stage="submit", code="COMFYUI_PROMPT_REJECTED",
                    http_status=response.status_code, response_body=payload, node_errors=payload["node_errors"],
                )
            prompt_id = payload.get("prompt_id")
            if not prompt_id:
                raise ComfyUIResponseError(
                    "ComfyUI prompt response did not contain a prompt ID", stage="submit",
                    code="COMFYUI_PROMPT_REJECTED", http_status=response.status_code, response_body=payload,
                )
            return str(prompt_id)
        except ComfyUIResponseError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ComfyUIResponseError(
                "ComfyUI prompt request failed", stage="submit", code="COMFYUI_PROMPT_REJECTED",
                response_body={"exception": str(exc)},
            ) from exc

    def wait_for_outputs(
        self,
        prompt_id: str,
        *,
        output_node_ids: list[str] | None = None,
        accepted_extensions: set[str] | None = None,
        progress: Callable[[int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> list[ComfyOutput]:
        started = monotonic()
        reported = -1
        while monotonic() - started < self.timeout_seconds:
            if cancelled and cancelled():
                self.interrupt()
                raise ComfyUIResponseError(
                    "Generation was cancelled", stage="generation", code="GENERATION_CANCELLED",
                )
            history = self._history(prompt_id)
            entry = history.get(prompt_id) if isinstance(history, dict) else None
            if isinstance(entry, dict):
                status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
                if status.get("status_str") == "error":
                    messages = status.get("messages") or []
                    raise ComfyUIResponseError(
                        "ComfyUI generation failed", stage="history", code="GENERATION_FAILED",
                        http_status=200, response_body=entry, node_errors=messages,
                    )
                outputs = self._outputs(entry.get("outputs") or {}, output_node_ids or [], accepted_extensions)
                if outputs:
                    if progress:
                        progress(90, "Retrieving generated output")
                    return outputs
                if status.get("completed") is True or status.get("status_str") in {"success", "completed"}:
                    raise ComfyUIResponseError(
                        "ComfyUI completed the prompt without an accepted output", stage="output",
                        code="COMFYUI_OUTPUT_MISSING", http_status=200, response_body=entry,
                    )
            queued, running = self._queue_position(prompt_id)
            value = 35 if queued else 55 if running else min(85, 40 + int((monotonic() - started) / 5))
            if value != reported and progress:
                progress(value, "Rendering in ComfyUI" if running else "Waiting in ComfyUI queue")
                reported = value
            sleep(self.poll_interval_seconds)
        raise ComfyUIResponseError(
            "ComfyUI generation timed out", stage="generation", code="GENERATION_TIMEOUT",
            response_body={"prompt_id": prompt_id, "timeout_seconds": self.timeout_seconds},
        )

    def download_output(self, output: ComfyOutput) -> bytes:
        filename = _safe_output_component(output.filename, field="output filename")
        subfolder = _safe_subfolder(output.subfolder)
        output_type = output.output_type if output.output_type in {"output", "input", "temp"} else "output"
        url = f"/view?filename={quote(filename)}&subfolder={quote(subfolder)}&type={quote(output_type)}"
        try:
            response = self._client.get(url)
            payload = _body(response) if not response.is_success else None
            if not response.is_success:
                raise ComfyUIResponseError(
                    "Unable to retrieve ComfyUI output", stage="download",
                    code="COMFYUI_OUTPUT_DOWNLOAD_FAILED", http_status=response.status_code,
                    response_body=payload, node_errors=_node_errors(payload),
                )
            if not response.content:
                raise ComfyUIResponseError(
                    "ComfyUI returned an empty output", stage="download",
                    code="COMFYUI_OUTPUT_DOWNLOAD_FAILED", http_status=response.status_code,
                )
            return response.content
        except ComfyUIResponseError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ComfyUIResponseError(
                "Unable to retrieve ComfyUI output", stage="download", code="COMFYUI_OUTPUT_DOWNLOAD_FAILED",
                response_body={"exception": str(exc)},
            ) from exc

    def interrupt(self) -> None:
        try:
            response = self._client.post("/interrupt")
            if not response.is_success:
                raise ComfyUIResponseError(
                    "ComfyUI did not accept cancellation", stage="interrupt", code="GENERATION_CANCELLED",
                    http_status=response.status_code, response_body=_body(response),
                )
        except ComfyUIResponseError:
            raise
        except httpx.HTTPError as exc:
            raise ComfyUIResponseError(
                "Unable to request ComfyUI cancellation", stage="interrupt", code="GENERATION_CANCELLED",
                response_body={"exception": str(exc)},
            ) from exc

    def _get_object(self, endpoint: str, *, stage: str) -> dict[str, Any]:
        try:
            response = self._client.get(endpoint)
            payload = _body(response)
            if not response.is_success:
                raise ComfyUIResponseError(
                    f"ComfyUI {endpoint} request failed", stage=stage,
                    http_status=response.status_code, response_body=payload, node_errors=_node_errors(payload),
                )
            if not isinstance(payload, dict):
                raise ComfyUIResponseError(
                    f"ComfyUI {endpoint} response was not a JSON object", stage=stage,
                    http_status=response.status_code, response_body=payload,
                )
            return payload
        except ComfyUIResponseError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ComfyUIResponseError(
                f"ComfyUI {endpoint} is unavailable", stage=stage,
                response_body={"exception": str(exc)},
            ) from exc

    def _history(self, prompt_id: str) -> dict[str, Any]:
        try:
            return self._get_object(f"/history/{quote(prompt_id)}", stage="history")
        except ComfyUIResponseError as exc:
            exc.code = "COMFYUI_HISTORY_FAILED"
            raise

    def _queue_position(self, prompt_id: str) -> tuple[bool, bool]:
        try:
            payload = self.queue()
        except ComfyUIResponseError:
            return False, False
        running = any(self._prompt_id(item) == prompt_id for item in payload.get("queue_running", []))
        queued = any(self._prompt_id(item) == prompt_id for item in payload.get("queue_pending", []))
        return queued, running

    @staticmethod
    def _prompt_id(item: Any) -> str | None:
        return str(item[1]) if isinstance(item, list) and len(item) > 1 else None

    @staticmethod
    def _outputs(
        outputs: dict[str, Any], allowed_nodes: list[str], accepted_extensions: set[str] | None = None,
    ) -> list[ComfyOutput]:
        found: list[ComfyOutput] = []
        extensions = accepted_extensions or {".mp4", ".webm", ".mov", ".gif"}
        allowed = {str(value) for value in allowed_nodes}
        for node_id, payload in outputs.items():
            if allowed and str(node_id) not in allowed:
                continue
            for key in ("videos", "gifs", "images"):
                values = payload.get(key, []) if isinstance(payload, dict) else []
                for item in values if isinstance(values, list) else []:
                    if not isinstance(item, dict):
                        continue
                    filename = str(item.get("filename", ""))
                    if Path(filename).suffix.lower() not in extensions:
                        continue
                    try:
                        found.append(ComfyOutput(
                            filename=_safe_output_component(filename, field="output filename"),
                            subfolder=_safe_subfolder(str(item.get("subfolder", ""))),
                            output_type=str(item.get("type", "output")), node_id=str(node_id),
                        ))
                    except ValueError:
                        continue
        return found

    @staticmethod
    def _mime(source: Path) -> str:
        return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(source.suffix.lower(), "image/png")


def _body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:4000]


def _node_errors(value: Any) -> Any:
    return value.get("node_errors") if isinstance(value, dict) else None


def _safe_output_component(value: str, *, field: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if not value or path.name != value or value in {".", ".."}:
        raise ValueError(f"Unsafe ComfyUI {field}")
    return value


def _safe_subfolder(value: str) -> str:
    if not value:
        return ""
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe ComfyUI output subfolder")
    return path.as_posix().strip("/")
