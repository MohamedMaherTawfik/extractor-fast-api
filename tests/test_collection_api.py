def test_collection_api_exposes_status_and_persistent_failed_job(api_request) -> None:
    creator_response = api_request(
        "POST",
        "/creators",
        json={"display_name": "API Collector Creator"},
    )
    creator = creator_response.json()
    account_response = api_request(
        "POST",
        f"/creators/{creator['id']}/accounts",
        json={"platform": "instagram", "username": "api_collector"},
    )
    account = account_response.json()

    status_response = api_request("GET", "/connectors/status")
    collection_response = api_request(
        "POST",
        f"/collection/account/{account['id']}",
        json={"metadata_only": True, "max_items": 5},
    )

    assert status_response.status_code == 200
    assert status_response.json()["instagram"] == "permission_required"
    assert collection_response.status_code == 201
    job = collection_response.json()
    assert job["status"] == "failed"
    assert job["platform_account_id"] == account["id"]

    get_response = api_request("GET", f"/collection/jobs/{job['id']}")
    list_response = api_request("GET", "/collection/jobs")
    assert get_response.status_code == 200
    assert get_response.json()["job_uid"] == job["job_uid"]
    assert [item["id"] for item in list_response.json()] == [job["id"]]
