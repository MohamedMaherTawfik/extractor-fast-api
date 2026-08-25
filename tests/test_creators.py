from backend.core.enums import Platform
from backend.connectors.base import BaseConnector
from backend.connectors.registry import ConnectorRegistry


def create_creator(api_request, name: str, **extra):
    response = api_request(
        "POST",
        "/creators",
        json={"display_name": name, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_creator_and_add_multiple_platform_accounts(api_request) -> None:
    creator = create_creator(
        api_request,
        "Creator One",
        country="EG",
        category="education",
    )
    assert creator["creator_uid"].startswith("CR_")

    instagram = api_request(
        "POST",
        f"/creators/{creator['id']}/accounts",
        json={"platform": "instagram", "username": "@CreatorOne"},
    )
    tiktok = api_request(
        "POST",
        f"/creators/{creator['id']}/accounts",
        json={
            "platform": "tiktok",
            "profile_url": "https://tiktok.com/@CreatorOneTT/",
        },
    )

    assert instagram.status_code == 201
    assert tiktok.status_code == 201
    accounts = api_request(
        "GET",
        f"/creators/{creator['id']}/accounts",
    ).json()
    assert {account["platform"] for account in accounts} == {
        "instagram",
        "tiktok",
    }
    assert {account["creator_id"] for account in accounts} == {creator["id"]}


def test_username_is_unique_per_platform(api_request) -> None:
    first = create_creator(api_request, "First")
    second = create_creator(api_request, "Second")

    assert api_request(
        "POST",
        f"/creators/{first['id']}/accounts",
        json={"platform": "instagram", "username": "shared_name"},
    ).status_code == 201
    assert api_request(
        "POST",
        f"/creators/{second['id']}/accounts",
        json={"platform": "tiktok", "username": "shared_name"},
    ).status_code == 201
    duplicate = api_request(
        "POST",
        f"/creators/{second['id']}/accounts",
        json={"platform": "instagram", "username": "@SHARED_NAME"},
    )

    assert duplicate.status_code == 409


def test_search_by_name_username_platform_country_and_category(api_request) -> None:
    creator = create_creator(
        api_request,
        "Searchable Creator",
        country="Egypt",
        category="Travel",
    )
    api_request(
        "POST",
        f"/creators/{creator['id']}/accounts",
        json={"platform": "youtube", "username": "needle_handle"},
    )

    queries = (
        "/creators?q=Searchable",
        "/creators?q=needle_handle",
        "/creators?platform=youtube",
        "/creators?country=egypt",
        "/creators?category=travel",
    )
    for query in queries:
        response = api_request("GET", query)
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [creator["id"]]


class StubConnector(BaseConnector):
    def resolve_account(self, identifier, *, timeout=None):
        return {"identifier": identifier}

    def fetch_profile(self, account, *, timeout=None):
        return account

    def fetch_content_list(
        self,
        account,
        *,
        pagination=None,
        since=None,
        limit=None,
        timeout=None,
    ):
        from backend.connectors.pagination import ContentPage

        return ContentPage([])

    def fetch_content_item(self, content_id, *, timeout=None):
        return {"id": content_id}

    def normalize(self, raw_content):
        return dict(raw_content)


def test_account_platform_selects_connector_without_creator_coupling() -> None:
    registry = ConnectorRegistry()
    connector = StubConnector()
    registry.register(Platform.INSTAGRAM, connector)

    assert registry.get(Platform.INSTAGRAM) is connector
