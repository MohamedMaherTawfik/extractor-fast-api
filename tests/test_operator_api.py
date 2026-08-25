def test_operator_capabilities_feature_gate_and_safe_settings(api_request):
    capabilities = api_request("GET", "/system/capabilities")
    assert capabilities.status_code == 200
    modules = capabilities.json()["modules"]
    assert modules["answer_bot"]["enabled"] is True
    assert modules["lead_engine"] == {"enabled": False, "status": "not_implemented"}
    settings = api_request("GET", "/system/settings")
    assert settings.status_code == 200
    assert "secret" not in settings.text.casefold() and "api_key" not in settings.text.casefold()


def test_operator_dashboard_workspace_search_and_health(api_request):
    assert api_request("GET", "/system/dashboard").status_code == 200
    page = api_request("GET", "/system/workspaces/products", params={"offset": 0, "limit": 10})
    assert page.status_code == 200 and page.json()["limit"] == 10
    assert api_request("GET", "/system/workspaces/leads").status_code == 404
    assert api_request("GET", "/system/search", params={"q": "TEST"}).status_code == 200
    health = api_request("GET", "/system/health-detail")
    assert health.status_code == 200 and health.json()["database"] == "ONLINE"
