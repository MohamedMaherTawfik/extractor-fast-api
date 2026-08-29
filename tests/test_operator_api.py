def test_operator_capabilities_feature_gate_and_safe_settings(api_request):
    capabilities = api_request("GET", "/system/capabilities")
    assert capabilities.status_code == 200
    modules = capabilities.json()["modules"]
    assert modules["answer_bot"]["enabled"] is True
    assert modules["lead_engine"] == {"enabled": True, "status": "available", "version": "1.0.0"}
    assert modules["parquet_export"]["status"] in {"AVAILABLE_VIA_PYARROW", "NOT_AVAILABLE"}
    settings = api_request("GET", "/system/settings")
    assert settings.status_code == 200
    assert "secret" not in settings.text.casefold() and "api_key" not in settings.text.casefold()
    data_runtime = settings.json()["data_runtime"]
    assert data_runtime["pyarrow"]["required_at_startup"] is False
    assert data_runtime["parquet"]["available"] == modules["parquet_export"]["enabled"]


def test_operator_dashboard_workspace_search_and_health(api_request):
    assert api_request("GET", "/system/dashboard").status_code == 200
    page = api_request("GET", "/system/workspaces/products", params={"offset": 0, "limit": 10})
    assert page.status_code == 200 and page.json()["limit"] == 10
    assert api_request("GET", "/system/workspaces/leads").status_code == 404
    assert api_request("GET", "/system/search", params={"q": "TEST"}).status_code == 200
    health = api_request("GET", "/system/health-detail")
    assert health.status_code == 200 and health.json()["database"] == "ONLINE"
