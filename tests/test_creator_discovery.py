from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook

from backend.creator_discovery.analysis import EvidenceOnlyCreatorAnalyzer
from backend.creator_discovery.connectors import DirectURLConnector
from backend.creator_discovery.export import REFERENCE_COLUMNS, build_xlsx, export_rows
from backend.creator_discovery.input import parse_creator_input
from backend.creator_discovery.matching import IdentityMatcher
from backend.creator_discovery.normalization import (
    detect_platform,
    normalize_creator_name,
    normalize_discovery_input,
    normalize_profile_url,
)
from backend.schemas.creator_discovery import DiscoveryPlatform


def test_name_url_and_platform_normalization():
    assert normalize_creator_name("  Ahmed—Example!  ") == "ahmed example"
    assert detect_platform("https://www.linkedin.com/in/ahmed-example") is DiscoveryPlatform.LINKEDIN
    platform, url, username = normalize_profile_url("http://twitter.com/Ahmed_Example/?ref=home")
    assert (platform, url, username) == (DiscoveryPlatform.X, "https://x.com/Ahmed_Example", "ahmed_example")
    direct = normalize_discovery_input("https://www.snapchat.com/add/Ahmed")
    assert direct.kind == "PROFILE_URL" and direct.username == "ahmed"


def test_identity_matching_does_not_confirm_on_name_alone():
    matcher = IdentityMatcher()
    name_only = matcher.match("Ahmed Example", {"display_name": "Ahmed Example"})
    assert name_only.confidence < 80
    complete = matcher.match("Ahmed Example", {"display_name": "Ahmed Example", "username": "ahmedexample"})
    assert complete.confidence >= 80
    cross_platform = matcher.match("Ahmed Example", {
        "display_name": "Ahmed Example", "username": "ahmedexample",
        "linked_social_urls": ["https://x.com/ahmed"],
        "reference_social_urls": ["https://x.com/ahmed"],
        "content_topics": ["technology", "reviews"],
        "reference_content_topics": ["technology", "reviews"],
        "location": "Cairo", "reference_location": "Cairo",
        "brand_names": ["EMY"], "reference_brand_names": ["EMY"],
    })
    assert cross_platform.confidence >= complete.confidence
    assert {item.signal for item in cross_platform.signals} >= {"linked_social_urls", "content_topic_similarity", "public_location", "brand_names", "profile_naming_consistency"}
    direct = matcher.match("https://www.youtube.com/@ahmed", {"profile_url": "https://www.youtube.com/@ahmed"}, direct_url=True)
    assert direct.confidence == 100 and direct.classification.value == "CONFIRMED"


def test_csv_and_xlsx_inputs_are_bounded_and_deduplicated():
    csv_values = parse_creator_input("names.csv", b"Name\nAhmed\nSara\nAhmed\n")
    assert csv_values == ["Ahmed", "Sara"]
    payload = build_xlsx([{"name": "Ahmed", "industry": "Education"}])
    assert parse_creator_input("names.xlsx", payload) == ["Ahmed"]


def test_reference_export_mapping_and_summary():
    profile = {
        "name": "Ahmed", "niche": "Edutainment / Education", "industry": "Education",
        "main_platform": "youtube", "youtube_url": "https://www.youtube.com/@ahmed",
        "content_mechanism_style": "Educational explainers", "influence_size": "+800K",
        "kpi_impact": "UNKNOWN", "start_year": 2018, "x_url": "https://x.com/ahmed",
    }
    rows = export_rows([profile])
    assert list(rows[0]) == REFERENCE_COLUMNS and "X" not in rows[0]
    workbook = load_workbook(BytesIO(build_xlsx([profile])))
    assert workbook.sheetnames == ["EGYPT_MASSIVE_DUMP", "INDUSTRY_SUMMARY"]
    assert [cell.value for cell in workbook["EGYPT_MASSIVE_DUMP"][1]] == REFERENCE_COLUMNS
    assert workbook["INDUSTRY_SUMMARY"][2][0].value == "Education"
    assert export_rows([{**profile, "name": "=HYPERLINK(\"bad\")"}])[0]["Name"].startswith("'=")


def test_connector_fallback_and_evidence_only_industry_classification():
    connector = DirectURLConnector(DiscoveryPlatform.INSTAGRAM)
    outcome = connector.discover(normalize_discovery_input("https://www.instagram.com/ahmed"))
    assert outcome.status == "FOUND"
    assert outcome.candidates[0].discovery_source == "operator_supplied_url"
    assert outcome.candidates[0].followers is None

    account = SimpleNamespace(
        bio="Technology and gadget reviews", followers=None, content_count=None,
        metadata_json={}, platform="instagram", account_uid="CDA_TEST",
    )
    result = EvidenceOnlyCreatorAnalyzer().analyze(accounts=[account], samples=[])
    assert result["industry"] == "Technology"
    assert result["niche"] == "Technology / Gadgets"
    assert result["kpi_impact"] == "UNKNOWN"


def test_direct_url_run_review_merge_profile_and_export_api(api_request):
    created = api_request("POST", "/creator-discovery/runs", json={
        "inputs": ["https://www.youtube.com/@example"],
        "platforms": ["youtube", "instagram"],
        "analyze_content": True,
        "resolve_cross_platform_identity": True,
        "update_existing_profiles": False,
        "content_sample_size": 10,
        "execute": True,
    })
    assert created.status_code == 201
    assert created.json()["status"] == "PARTIAL"
    assert created.json()["matched"] == 1

    queue = api_request("GET", "/creator-discovery/candidates", params={"review_status": "PENDING"})
    assert queue.status_code == 200 and queue.json()["total"] == 1
    candidate = queue.json()["items"][0]
    assert candidate["platform"] == "youtube" and candidate["confidence"] == 100
    detail = api_request(
        "POST", f"/creator-discovery/candidates/{candidate['candidate_uid']}/confirm",
        json={"action": "THIS_IS_THE_ACCOUNT"},
    )
    assert detail.status_code == 200
    unified = detail.json()["unified_profile"]
    assert unified["youtube_url"] == "https://www.youtube.com/@example"
    assert unified["analysis_status"] == "INSUFFICIENT_EVIDENCE"
    corrected = api_request(
        "PATCH", f"/creator-discovery/creators/{unified['profile_uid']}",
        json={"niche": "Technology / Reviews", "main_platform": None, "start_year": None},
    )
    assert corrected.status_code == 200
    assert corrected.json()["unified_profile"]["niche"] == "Technology / Reviews"
    assert corrected.json()["unified_profile"]["main_platform"] == "UNKNOWN"

    second = api_request("POST", "/creator-discovery/runs", json={
        "inputs": ["https://www.instagram.com/example"], "platforms": ["instagram"],
        "execute": True,
    })
    assert second.status_code == 201
    second_queue = api_request("GET", "/creator-discovery/candidates", params={"review_status": "PENDING"}).json()
    instagram = next(item for item in second_queue["items"] if item["platform"] == "instagram")
    merged = api_request(
        "POST", f"/creator-discovery/candidates/{instagram['candidate_uid']}/confirm",
        json={"action": "MERGE", "creator_uid": unified["creator_uid"]},
    )
    assert merged.status_code == 200
    assert set(merged.json()["unified_profile"]["platforms_found"]) == {"youtube", "instagram"}

    result_page = api_request("GET", "/creator-discovery/creators", params={"platform": "instagram"})
    assert result_page.status_code == 200 and result_page.json()["total"] == 1
    exported = api_request("POST", "/creators/export", json={"format": "xlsx", "extended": False})
    assert exported.status_code == 200
    workbook = load_workbook(BytesIO(exported.content))
    assert workbook.sheetnames == ["EGYPT_MASSIVE_DUMP", "INDUSTRY_SUMMARY"]


def test_run_pause_resume_and_connector_capabilities(api_request):
    capabilities = api_request("GET", "/creator-discovery/connectors")
    assert capabilities.status_code == 200 and len(capabilities.json()) == 7
    assert all(item["name_discovery"] in {"API_REQUIRED", "MANUAL_URL_REQUIRED", "CONFIGURED"} for item in capabilities.json())
    created = api_request("POST", "/creator-discovery/runs", json={
        "inputs": ["Ahmed Example"], "platforms": ["youtube"], "execute": False,
    }).json()
    paused = api_request("POST", f"/creator-discovery/runs/{created['run_uid']}/pause")
    assert paused.status_code == 200 and paused.json()["status"] == "PAUSED"
    resumed = api_request("POST", f"/creator-discovery/runs/{created['run_uid']}/resume")
    assert resumed.status_code == 200 and resumed.json()["status"] == "PARTIAL"
