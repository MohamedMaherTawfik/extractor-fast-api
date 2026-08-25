"""Persistence queries for the isolated lead/prospect data plane."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.db.models.leads import (
    Lead,
    LeadDedupeEvent,
    LeadJob,
    LeadRun,
    LeadSource,
    LeadSourceRecord,
)


class LeadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_source(self, values: dict[str, Any]) -> LeadSource:
        source = self.session.scalar(select(LeadSource).where(LeadSource.source_uid == values["source_uid"]))
        if source is None:
            source = LeadSource(**values)
            self.session.add(source)
        else:
            for key, value in values.items():
                setattr(source, key, value)
        self.session.flush()
        return source

    def list_sources(self) -> list[LeadSource]:
        return list(self.session.scalars(select(LeadSource).order_by(LeadSource.id)))

    def create_run(self, values: dict[str, Any]) -> LeadRun:
        run = LeadRun(**values)
        self.session.add(run)
        self.session.flush()
        return run

    def create_job(self, values: dict[str, Any]) -> LeadJob:
        job = LeadJob(**values)
        self.session.add(job)
        self.session.flush()
        return job

    def get_run(self, run_uid: str, *, with_jobs: bool = True) -> LeadRun | None:
        statement = select(LeadRun).where(LeadRun.run_uid == run_uid)
        if with_jobs:
            statement = statement.options(selectinload(LeadRun.jobs))
        return self.session.scalar(statement)

    def list_runs(self, *, offset: int, limit: int) -> tuple[list[LeadRun], int]:
        total = int(self.session.scalar(select(func.count()).select_from(LeadRun)) or 0)
        rows = list(self.session.scalars(select(LeadRun).order_by(LeadRun.created_at.desc()).offset(offset).limit(limit)))
        return rows, total

    def jobs_for_execution(self, run_id: int) -> list[LeadJob]:
        return list(
            self.session.scalars(
                select(LeadJob)
                .where(LeadJob.run_id == run_id, LeadJob.status.in_(("PENDING", "PAUSED", "PARTIAL")))
                .order_by(LeadJob.id)
            )
        )

    def get_source_record(self, source_uid: str, source_record_id: str) -> LeadSourceRecord | None:
        return self.session.scalar(
            select(LeadSourceRecord)
            .options(selectinload(LeadSourceRecord.lead))
            .where(LeadSourceRecord.source_uid == source_uid, LeadSourceRecord.source_record_id == source_record_id)
        )

    def dedupe_candidates(self, normalized: dict[str, Any]) -> list[Lead]:
        predicates = []
        if normalized.get("phone_normalized"):
            predicates.append(Lead.phone_normalized == normalized["phone_normalized"])
        if normalized.get("domain_normalized"):
            predicates.append(Lead.domain_normalized == normalized["domain_normalized"])
        if normalized.get("business_name_normalized") and normalized.get("address_normalized"):
            predicates.append(
                (Lead.business_name_normalized == normalized["business_name_normalized"])
                & (Lead.address_normalized == normalized["address_normalized"])
            )
        if normalized.get("business_name_normalized"):
            predicates.append(Lead.business_name_normalized == normalized["business_name_normalized"])
        if not predicates:
            return []
        return list(self.session.scalars(select(Lead).where(or_(*predicates)).limit(100)))

    def add_lead(self, values: dict[str, Any]) -> Lead:
        lead = Lead(**values)
        self.session.add(lead)
        self.session.flush()
        return lead

    def add_source_record(self, values: dict[str, Any]) -> LeadSourceRecord:
        record = LeadSourceRecord(**values)
        self.session.add(record)
        self.session.flush()
        return record

    def add_dedupe_event(self, values: dict[str, Any]) -> LeadDedupeEvent:
        event = LeadDedupeEvent(**values)
        self.session.add(event)
        self.session.flush()
        return event

    def source_count(self, lead_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.count(func.distinct(LeadSourceRecord.source_uid))).where(LeadSourceRecord.lead_id == lead_id)
            )
            or 0
        )

    def query_leads(
        self,
        *,
        offset: int,
        limit: int,
        fit_class: str | None = None,
        governorate: str | None = None,
        category: str | None = None,
        source: str | None = None,
        verified_only: bool = False,
        query: str | None = None,
    ) -> tuple[list[Lead], int]:
        criteria = []
        if fit_class:
            criteria.append(Lead.fit_class == fit_class)
        if governorate:
            criteria.append(Lead.governorate == governorate)
        if category:
            criteria.append(Lead.category_id == category)
        if verified_only:
            criteria.append(Lead.last_verified_at.is_not(None))
        if query:
            pattern = f"%{query}%"
            criteria.append(or_(Lead.business_name_raw.ilike(pattern), Lead.phone_normalized.ilike(pattern), Lead.website.ilike(pattern)))
        if source:
            criteria.append(
                exists(select(LeadSourceRecord.id).where(LeadSourceRecord.lead_id == Lead.id, LeadSourceRecord.source_uid == source))
            )
        base = select(Lead)
        count_statement = select(func.count()).select_from(Lead)
        if criteria:
            base = base.where(*criteria)
            count_statement = count_statement.where(*criteria)
        total = int(self.session.scalar(count_statement) or 0)
        rows = list(self.session.scalars(base.order_by(Lead.fit_score.desc(), Lead.id.desc()).offset(offset).limit(limit)))
        return rows, total

    def get_lead(self, lead_uid: str) -> Lead | None:
        return self.session.scalar(
            select(Lead)
            .options(selectinload(Lead.source_records), selectinload(Lead.dedupe_events))
            .where(Lead.lead_uid == lead_uid)
        )

    def stats(self) -> dict[str, Any]:
        total = int(self.session.scalar(select(func.count()).select_from(Lead)) or 0)
        classes = {str(key): int(value) for key, value in self.session.execute(select(Lead.fit_class, func.count()).group_by(Lead.fit_class))}
        active = int(self.session.scalar(select(func.count()).select_from(LeadRun).where(LeadRun.status.in_(("PENDING", "RUNNING", "PAUSED", "WAITING_RATE_LIMIT", "WAITING_CREDENTIAL")))) or 0)
        source_count = int(self.session.scalar(select(func.count()).select_from(LeadSource).where(LeadSource.enabled.is_(True))) or 0)
        last_run = self.session.scalar(select(LeadRun).order_by(LeadRun.created_at.desc()).limit(1))
        errors = int(self.session.scalar(select(func.coalesce(func.sum(LeadRun.errors), 0))) or 0)
        return {
            "total_leads": total,
            "classes": {name: classes.get(name, 0) for name in ("A+", "A", "B", "C")},
            "active_runs": active,
            "sources": source_count,
            "last_run": last_run.run_uid if last_run else None,
            "last_run_status": last_run.status if last_run else None,
            "errors": errors,
        }

