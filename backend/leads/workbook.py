"""Excel command-workbook discovery, validation, and managed import."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from backend.core.paths import paths
from backend.db.models.leads import LeadControlImport
from backend.leads.config import LeadCatalog, get_lead_catalog


class LeadWorkbookService:
    def __init__(self, session: Session | None = None, catalog: LeadCatalog | None = None) -> None:
        self.session = session
        self.catalog = catalog or get_lead_catalog()

    @property
    def placement(self) -> str:
        return (Path(self.catalog.workbook.get("directory", "data/imports/lead_control")) / "EMY_Egypt_Lead_Acquisition_OS_v1.xlsx").as_posix()

    def find(self) -> Path | None:
        patterns = self.catalog.workbook.get("patterns", ["EMY_Egypt_Lead_Acquisition_OS_v*.xlsx"])
        for directory in (paths.lead_control_imports, paths.project_root):
            for pattern in patterns:
                matches = sorted(directory.glob(str(pattern)), key=lambda item: item.stat().st_mtime, reverse=True)
                if matches:
                    return matches[0]
        return None

    def preview(self, workbook_path: Path | None = None) -> dict[str, Any]:
        candidate = workbook_path or self.find()
        required = list(self.catalog.workbook.get("required_sheets", []))
        if candidate is None:
            return {
                "available": False,
                "status": "NOT_FOUND_USING_CONFIG_DEFAULTS",
                "placement": self.placement,
                "required_sheets": required,
                "sheet_counts": {},
                "errors": [],
            }
        workbook = load_workbook(candidate, read_only=True, data_only=True)
        missing = [name for name in required if name not in workbook.sheetnames]
        counts = {name: max(0, workbook[name].max_row - 1) for name in required if name in workbook.sheetnames}
        workbook.close()
        return {
            "available": True,
            "status": "VALID" if not missing else "INVALID",
            "filename": candidate.name,
            "stored_path": paths.relative(candidate).as_posix(),
            "placement": self.placement,
            "required_sheets": required,
            "sheet_counts": counts,
            "errors": [f"Missing sheet: {name}" for name in missing],
        }

    def rows(self, sheet_name: str, workbook_path: Path | None = None) -> list[dict[str, Any]]:
        candidate = workbook_path or self.find()
        if candidate is None:
            return []
        workbook = load_workbook(candidate, read_only=True, data_only=True)
        if sheet_name not in workbook.sheetnames:
            workbook.close()
            return []
        sheet = workbook[sheet_name]
        iterator = sheet.iter_rows(values_only=True)
        headers = [str(value).strip() if value is not None else "" for value in next(iterator, ())]
        result = []
        for values in iterator:
            item = {headers[index]: value for index, value in enumerate(values) if index < len(headers) and headers[index]}
            if any(value not in (None, "") for value in item.values()):
                result.append(item)
        workbook.close()
        return result

    def effective_keywords(self) -> list[dict[str, Any]]:
        rows = self.rows("Keyword Master")
        parsed = []
        for row in rows:
            normalized = {str(key).strip().casefold().replace(" ", "_"): value for key, value in row.items()}
            keyword = normalized.get("keyword") or normalized.get("term") or normalized.get("search_phrase")
            approved = normalized.get("approved", True)
            if keyword and str(approved).strip().casefold() not in {"false", "0", "no", "n"}:
                parsed.append({"keyword": str(keyword), "category_id": normalized.get("category_id") or normalized.get("segment_id"), "approved": True, "language": normalized.get("language")})
        return parsed or self.catalog.approved_keywords

    def import_bytes(self, filename: str, content: bytes) -> dict[str, Any]:
        if Path(filename).suffix.casefold() != ".xlsx":
            raise ValueError("Lead command workbook must be an .xlsx file")
        if len(content) > 25 * 1024 * 1024:
            raise ValueError("Lead command workbook exceeds the 25 MB limit")
        paths.lead_control_imports.mkdir(parents=True, exist_ok=True)
        safe_name = f"EMY_Egypt_Lead_Acquisition_OS_v1_{uuid4().hex[:10]}.xlsx"
        destination = paths.lead_control_imports / safe_name
        destination.write_bytes(content)
        preview = self.preview(destination)
        if self.session is not None:
            record = LeadControlImport(
                import_uid=f"LCI_{uuid4().hex.upper()}",
                filename=Path(filename).name,
                stored_path=paths.relative(destination).as_posix(),
                sha256=hashlib.sha256(content).hexdigest(),
                status=preview["status"],
                sheet_counts=preview["sheet_counts"],
                errors=preview["errors"],
            )
            self.session.add(record)
            self.session.flush()
            preview["import_uid"] = record.import_uid
        return preview

