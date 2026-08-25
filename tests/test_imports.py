from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import func, select

from backend.db.models.creator import Creator
from backend.db.models.platform_account import PlatformAccount
from backend.db.session import session_scope


def creator_counts() -> tuple[int, int]:
    with session_scope() as session:
        creators = session.scalar(select(func.count()).select_from(Creator))
        accounts = session.scalar(select(func.count()).select_from(PlatformAccount))
    return int(creators or 0), int(accounts or 0)


def test_import_csv_with_configured_column_mapping(api_request) -> None:
    content = (
        b"Creator,Instagram,TikTok,Country\n"
        b"CSV Creator,@CsvIG,https://tiktok.com/@CsvTT/,EG\n"
    )
    response = api_request(
        "POST",
        "/creator-imports",
        files={"file": ("creators.csv", content, "text/csv")},
    )

    assert response.status_code == 201, response.text
    batch = response.json()
    assert batch["status"] == "completed"
    assert batch["rows_success"] == 1
    assert batch["rows_failed"] == 0
    assert batch["source_file"].startswith("data/imports/")
    assert ":" not in batch["source_file"]
    assert creator_counts() == (1, 2)


def test_import_xlsx(api_request) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Name", "YouTube", "Category"])
    worksheet.append(["Excel Creator", "@ExcelChannel", "education"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()

    response = api_request(
        "POST",
        "/creator-imports",
        files={
            "file": (
                "creators.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "completed"
    assert creator_counts() == (1, 1)


def test_exact_account_deduplication_is_idempotent(api_request) -> None:
    content = b"Name,Instagram\nDedup Creator,@SameAccount\n"
    for _ in range(2):
        response = api_request(
            "POST",
            "/creator-imports",
            files={"file": ("dedup.csv", content, "text/csv")},
        )
        assert response.status_code == 201
        assert response.json()["rows_success"] == 1

    assert creator_counts() == (1, 1)


def test_uncertain_name_match_is_flagged_without_merge(api_request) -> None:
    content = b"Name,Country\nPossible Duplicate,EG\nPossible Duplicate,EG\n"
    response = api_request(
        "POST",
        "/creator-imports",
        files={"file": ("possible.csv", content, "text/csv")},
    )

    assert response.status_code == 201
    with session_scope() as session:
        creators = list(session.scalars(select(Creator).order_by(Creator.id)))
    assert len(creators) == 2
    assert all(creator.possible_duplicate for creator in creators)


def test_invalid_import_row_is_recorded(api_request) -> None:
    content = (
        b"Name,Instagram,Notes\n"
        b"Valid Creator,@valid_account,\n"
        b",,row has no identity\n"
    )
    response = api_request(
        "POST",
        "/creator-imports",
        files={"file": ("invalid.csv", content, "text/csv")},
    )

    assert response.status_code == 201
    batch = response.json()
    assert batch["status"] == "partial"
    assert batch["rows_total"] == 2
    assert batch["rows_success"] == 1
    assert batch["rows_failed"] == 1
    assert batch["errors"][0]["row_number"] == 3
    assert batch["errors"][0]["raw_data"]["Notes"] == "row has no identity"
