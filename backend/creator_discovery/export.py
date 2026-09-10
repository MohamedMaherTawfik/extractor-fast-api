"""Exact workbook-compatible Creator Discovery exports."""

from __future__ import annotations

import csv
from collections import Counter
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook


REFERENCE_COLUMNS = [
    "Name", "Niche", "Industry", "Main_Platform", "YouTube", "Facebook",
    "Instagram", "TikTok", "Snapchat", "LinkedIn", "Content_Mechanism_Style",
    "Influence_Size", "KPI_Impact", "Start_Year",
]
EXTENDED_COLUMNS = [*REFERENCE_COLUMNS, "X"]


def export_rows(profiles: list[dict[str, Any]], *, extended: bool = False) -> list[dict[str, Any]]:
    rows = []
    for item in profiles:
        row = {
            "Name": item["name"],
            "Niche": item.get("niche") or "UNKNOWN",
            "Industry": item.get("industry") or "UNKNOWN",
            "Main_Platform": item.get("main_platform") or "UNKNOWN",
            "YouTube": item.get("youtube_url") or "NOT_AVAILABLE",
            "Facebook": item.get("facebook_url") or "NOT_AVAILABLE",
            "Instagram": item.get("instagram_url") or "NOT_AVAILABLE",
            "TikTok": item.get("tiktok_url") or "NOT_AVAILABLE",
            "Snapchat": item.get("snapchat_url") or "NOT_AVAILABLE",
            "LinkedIn": item.get("linkedin_url") or "NOT_AVAILABLE",
            "Content_Mechanism_Style": item.get("content_mechanism_style") or "UNKNOWN",
            "Influence_Size": item.get("influence_size") or "UNKNOWN",
            "KPI_Impact": item.get("kpi_impact") or "UNKNOWN",
            "Start_Year": item.get("start_year") or "UNKNOWN",
        }
        if extended:
            row["X"] = item.get("x_url") or "NOT_AVAILABLE"
        rows.append({column: _spreadsheet_safe(value) for column, value in row.items()})
    return rows


def build_xlsx(profiles: list[dict[str, Any]], *, extended: bool = False) -> bytes:
    rows = export_rows(profiles, extended=extended)
    columns = EXTENDED_COLUMNS if extended else REFERENCE_COLUMNS
    workbook = Workbook()
    dump = workbook.active
    dump.title = "EGYPT_MASSIVE_DUMP"
    dump.append(columns)
    for row in rows:
        dump.append([row[column] for column in columns])
    summary = workbook.create_sheet("INDUSTRY_SUMMARY")
    summary.append(["Industry", "Count"])
    counts = Counter(str(row["Industry"]) for row in rows)
    for industry, count in sorted(counts.items(), key=lambda item: (item[0] == "UNKNOWN", item[0])):
        summary.append([industry, count])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def build_csv(profiles: list[dict[str, Any]], *, extended: bool = False) -> bytes:
    rows = export_rows(profiles, extended=extended)
    columns = EXTENDED_COLUMNS if extended else REFERENCE_COLUMNS
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _spreadsheet_safe(value: Any) -> Any:
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value
