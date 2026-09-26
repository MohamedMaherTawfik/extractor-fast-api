import httpx
import pytest

from backend.generation.video_engine.comfyui_connector import ComfyOutput, ComfyUIConnector, ComfyUIResponseError


def test_prompt_failure_keeps_non_json_comfy_response_body():
    client = httpx.Client(
        base_url="http://comfy.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(400, text="workflow validation failed")),
    )
    connector = ComfyUIConnector("http://comfy.test", client=client)
    with pytest.raises(ComfyUIResponseError) as raised:
        connector.queue_workflow({"1": {"class_type": "Missing", "inputs": {}}})
    assert raised.value.stage == "submit"
    assert raised.value.http_status == 400
    assert raised.value.response_body == "workflow validation failed"


def test_output_download_failure_keeps_comfy_response_body():
    client = httpx.Client(
        base_url="http://comfy.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(404, json={"error": "not found"})),
    )
    connector = ComfyUIConnector("http://comfy.test", client=client)
    with pytest.raises(ComfyUIResponseError) as raised:
        connector.download_output(ComfyOutput("absent.png", "", "output", "9"))
    assert raised.value.stage == "download"
    assert raised.value.response_body == {"error": "not found"}


def test_connector_exercises_all_supported_comfy_operations_and_preserves_outputs(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={"system": {"comfyui_version": "test"}, "devices": []})
        if request.url.path == "/queue":
            return httpx.Response(200, json={"queue_running": [], "queue_pending": []})
        if request.url.path == "/object_info":
            return httpx.Response(200, json={"SaveImage": {"input": {"required": {}}}})
        if request.url.path == "/upload/image":
            return httpx.Response(200, json={"name": "reference.png", "subfolder": "emy"})
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "prompt-1"})
        if request.url.path == "/history/prompt-1":
            return httpx.Response(200, json={"prompt-1": {"status": {"completed": True}, "outputs": {"9": {"images": [{"filename": "result.png", "subfolder": "emy", "type": "output"}]}}}})
        if request.url.path == "/view":
            return httpx.Response(200, content=b"image-content")
        if request.url.path == "/interrupt":
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"error": "unexpected"})

    source = tmp_path / "reference.png"
    source.write_bytes(b"png")
    connector = ComfyUIConnector("http://comfy.test", poll_interval_seconds=0.01, client=httpx.Client(base_url="http://comfy.test", transport=httpx.MockTransport(handler)))
    status = connector.runtime_status()
    assert status["api_available"] is True and status["object_info"]["SaveImage"]
    assert connector.upload_reference(source) == "emy/reference.png"
    prompt_id = connector.queue_workflow({"1": {"class_type": "SaveImage", "inputs": {}}})
    output = connector.wait_for_outputs(prompt_id, output_node_ids=["9"], accepted_extensions={".png"})[0]
    assert connector.download_output(output) == b"image-content"
    connector.interrupt()
    assert {path for _, path in seen} >= {"/system_stats", "/queue", "/object_info", "/upload/image", "/prompt", "/history/prompt-1", "/view", "/interrupt"}


def test_runtime_probe_handles_connection_refusal_and_history_errors_with_stable_codes():
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    connector = ComfyUIConnector("http://comfy.test", client=httpx.Client(base_url="http://comfy.test", transport=httpx.MockTransport(refused)))
    report = connector.runtime_status()
    assert report["api_available"] is False
    assert all(check["http_status"] is None for check in report["checks"].values())

    history_client = httpx.Client(base_url="http://comfy.test", transport=httpx.MockTransport(lambda request: httpx.Response(500, text="broken history")))
    connector = ComfyUIConnector("http://comfy.test", client=history_client)
    with pytest.raises(ComfyUIResponseError) as raised:
        connector.wait_for_outputs("prompt-2", output_node_ids=["9"], accepted_extensions={".mp4"})
    assert raised.value.stage == "history"
    assert raised.value.code == "COMFYUI_HISTORY_FAILED"
    assert raised.value.response_body == "broken history"
