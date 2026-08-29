"""Append-only raw staging and streaming canonical exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from uuid import uuid4

from openpyxl import Workbook

from backend.core.paths import paths
from backend.core.runtime_capabilities import load_pyarrow_runtime
from backend.db.models.leads import Lead
from backend.repositories.lead_repository import LeadRepository
from backend.schemas.leads import LeadExportRequest


EXPORT_COLUMNS = (
    "lead_uid", "business_name_raw", "business_name_normalized", "category_id",
    "segment_tier", "buyer_type", "governorate", "city", "district",
    "address_raw", "latitude", "longitude", "phone_raw", "phone_normalized",
    "email", "website", "business_status", "source_id", "source_record_id",
    "source_first_seen_at", "source_last_seen_at", "last_verified_at",
    "source_confidence", "fit_score", "fit_class", "lead_status",
    "dedupe_status", "chain_key",
)


class ParquetExportUnavailableError(RuntimeError):
    """Raised when the optional Parquet runtime cannot be loaded safely."""

    code = "PARQUET_EXPORT_UNAVAILABLE"


class LeadRawStore:
    def path_for(self, run_uid: str, job_uid: str) -> Path:
        directory = paths.lead_raw / paths.safe_component(run_uid)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{paths.safe_component(job_uid)}.jsonl"

    def append(self, run_uid: str, job_uid: str, payload: dict) -> str:
        target = self.path_for(run_uid, job_uid)
        with target.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":")) + "\n")
        return paths.relative(target).as_posix()


class LeadExportService:
    def __init__(self, repository: LeadRepository) -> None:
        self.repository = repository

    def export(self, request: LeadExportRequest) -> Path:
        paths.lead_exports.mkdir(parents=True, exist_ok=True)
        target = paths.lead_exports / f"leads_{uuid4().hex}.{request.format}"
        if request.format == "csv":
            self._csv(target, request)
        elif request.format == "xlsx":
            self._xlsx(target, request)
        else:
            self._parquet(target, request)
        return target

    def _pages(self, request: LeadExportRequest, batch_size: int = 5000):
        offset = 0
        while True:
            rows, _ = self.repository.query_leads(
                offset=offset,
                limit=batch_size,
                fit_class=request.fit_class,
                governorate=request.governorate,
                category=request.category,
                source=request.source,
                verified_only=request.verified_only,
            )
            if not rows:
                break
            yield rows
            offset += len(rows)

    def _csv(self, target: Path, request: LeadExportRequest) -> None:
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()
            for rows in self._pages(request):
                writer.writerows(self._row(row) for row in rows)

    def _xlsx(self, target: Path, request: LeadExportRequest) -> None:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Leads")
        sheet.append(EXPORT_COLUMNS)
        for rows in self._pages(request):
            for row in rows:
                values = self._row(row)
                sheet.append([values[column] for column in EXPORT_COLUMNS])
        workbook.save(target)

    def _parquet(self, target: Path, request: LeadExportRequest) -> None:
        runtime = load_pyarrow_runtime()
        if not runtime.available:
            raise ParquetExportUnavailableError(ParquetExportUnavailableError.code)
        table_type = runtime.table_type
        parquet_writer_type = runtime.parquet_writer_type
        writer = None
        try:
            for rows in self._pages(request):
                table = table_type.from_pylist([self._row(row) for row in rows])
                if writer is None:
                    writer = parquet_writer_type(target, table.schema, compression="zstd")
                writer.write_table(table)
            if writer is None:
                table = table_type.from_pylist([{column: None for column in EXPORT_COLUMNS}]).slice(0, 0)
                writer = parquet_writer_type(target, table.schema, compression="zstd")
        finally:
            if writer is not None:
                writer.close()

    @staticmethod
    def _row(lead: Lead) -> dict:
        values = {}
        for column in EXPORT_COLUMNS:
            value = getattr(lead, column)
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
                value = "'" + value
            values[column] = value
        return values

