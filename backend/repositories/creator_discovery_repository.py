"""Persistence operations for the Creator Discovery Studio."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.db.models.creator import Creator
from backend.db.models.creator_discovery import (
    CreatorCandidate,
    CreatorContentSample,
    CreatorDiscoveryAccount,
    CreatorDiscoveryAnalysis,
    CreatorDiscoveryJob,
    CreatorDiscoveryProfile,
    CreatorDiscoveryRun,
    CreatorIndustry,
    CreatorMatchEvidence,
    CreatorSource,
)


class CreatorDiscoveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(self, values: dict[str, Any]) -> CreatorDiscoveryRun:
        item = CreatorDiscoveryRun(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def create_job(self, values: dict[str, Any]) -> CreatorDiscoveryJob:
        item = CreatorDiscoveryJob(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def get_run(self, identifier: str | int) -> CreatorDiscoveryRun | None:
        condition = CreatorDiscoveryRun.id == identifier if isinstance(identifier, int) else CreatorDiscoveryRun.run_uid == identifier
        return self.session.scalar(
            select(CreatorDiscoveryRun)
            .where(condition)
            .options(selectinload(CreatorDiscoveryRun.jobs))
        )

    def list_runs(self, offset: int, limit: int) -> tuple[list[CreatorDiscoveryRun], int]:
        total = self.session.scalar(select(func.count()).select_from(CreatorDiscoveryRun)) or 0
        rows = list(self.session.scalars(
            select(CreatorDiscoveryRun)
            .options(selectinload(CreatorDiscoveryRun.jobs))
            .order_by(CreatorDiscoveryRun.created_at.desc(), CreatorDiscoveryRun.id.desc())
            .offset(offset).limit(limit)
        ))
        return rows, int(total)

    def pending_jobs(self, run_id: int, limit: int, *, include_failed: bool = False) -> list[CreatorDiscoveryJob]:
        statuses = ["PENDING"] + (["FAILED"] if include_failed else [])
        return list(self.session.scalars(
            select(CreatorDiscoveryJob)
            .where(CreatorDiscoveryJob.run_id == run_id, CreatorDiscoveryJob.status.in_(statuses))
            .order_by(CreatorDiscoveryJob.id)
            .limit(limit)
        ))

    def remaining_jobs(self, run_id: int) -> int:
        return int(self.session.scalar(
            select(func.count()).select_from(CreatorDiscoveryJob).where(
                CreatorDiscoveryJob.run_id == run_id,
                CreatorDiscoveryJob.status == "PENDING",
            )
        ) or 0)

    def existing_candidate(self, run_id: int, platform: str, profile_url: str) -> CreatorCandidate | None:
        return self.session.scalar(select(CreatorCandidate).where(
            CreatorCandidate.run_id == run_id,
            CreatorCandidate.platform == platform,
            CreatorCandidate.profile_url == profile_url,
        ))

    def create_candidate(self, values: dict[str, Any]) -> CreatorCandidate:
        item = CreatorCandidate(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def get_candidate(self, candidate_uid: str) -> CreatorCandidate | None:
        return self.session.scalar(
            select(CreatorCandidate)
            .where(CreatorCandidate.candidate_uid == candidate_uid)
            .options(selectinload(CreatorCandidate.match_evidence))
        )

    def add_match_evidence(self, values: dict[str, Any]) -> CreatorMatchEvidence:
        item = CreatorMatchEvidence(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def list_candidates(
        self,
        *,
        offset: int,
        limit: int,
        run_uid: str | None = None,
        platform: str | None = None,
        review_status: str | None = None,
        classification: str | None = None,
    ) -> tuple[list[CreatorCandidate], int]:
        statement = select(CreatorCandidate).join(CreatorDiscoveryRun)
        count_statement = select(func.count()).select_from(CreatorCandidate).join(CreatorDiscoveryRun)
        filters = []
        if run_uid:
            filters.append(CreatorDiscoveryRun.run_uid == run_uid)
        if platform:
            filters.append(CreatorCandidate.platform == platform)
        if review_status == "OPEN":
            filters.append(CreatorCandidate.review_status.in_(["PENDING", "EXCEPTION"]))
        elif review_status:
            filters.append(CreatorCandidate.review_status == review_status)
        if classification:
            filters.append(CreatorCandidate.classification == classification)
        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)
        total = int(self.session.scalar(count_statement) or 0)
        rows = list(self.session.scalars(
            statement.options(selectinload(CreatorCandidate.match_evidence))
            .order_by(CreatorCandidate.confidence.desc(), CreatorCandidate.id.desc())
            .offset(offset).limit(limit)
        ))
        return rows, total

    def create_profile(self, values: dict[str, Any]) -> CreatorDiscoveryProfile:
        item = CreatorDiscoveryProfile(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def get_profile_by_creator(self, creator_id: int) -> CreatorDiscoveryProfile | None:
        return self.session.scalar(select(CreatorDiscoveryProfile).where(CreatorDiscoveryProfile.creator_id == creator_id))

    def get_profile(self, identifier: str | int) -> CreatorDiscoveryProfile | None:
        condition = CreatorDiscoveryProfile.id == identifier if isinstance(identifier, int) else CreatorDiscoveryProfile.profile_uid == identifier
        return self.session.scalar(select(CreatorDiscoveryProfile).where(condition))

    def get_profile_by_creator_uid(self, creator_uid: str) -> CreatorDiscoveryProfile | None:
        return self.session.scalar(
            select(CreatorDiscoveryProfile).join(Creator).where(Creator.creator_uid == creator_uid)
        )

    def list_profiles(
        self,
        *,
        offset: int,
        limit: int,
        query: str | None = None,
        platform: str | None = None,
        industry: str | None = None,
        niche: str | None = None,
        influence_min: int | None = None,
        influence_max: int | None = None,
        match_confidence_min: float | None = None,
        analysis_status: str | None = None,
        start_year: int | None = None,
        creator_uids: list[str] | None = None,
    ) -> tuple[list[tuple[CreatorDiscoveryProfile, Creator]], int]:
        statement = select(CreatorDiscoveryProfile, Creator).join(Creator)
        count_statement = select(func.count()).select_from(CreatorDiscoveryProfile).join(Creator)
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(or_(Creator.display_name.ilike(pattern), Creator.creator_uid.ilike(pattern), CreatorDiscoveryProfile.normalized_name.ilike(pattern)))
        if platform:
            filters.append(or_(
                CreatorDiscoveryProfile.main_platform == platform,
                getattr(CreatorDiscoveryProfile, f"{platform}_url").is_not(None),
            ))
        if industry:
            filters.append(func.lower(CreatorDiscoveryProfile.industry) == industry.strip().casefold())
        if niche:
            filters.append(CreatorDiscoveryProfile.niche.ilike(f"%{niche.strip()}%"))
        if influence_min is not None:
            filters.append(CreatorDiscoveryProfile.influence_size_numeric >= influence_min)
        if influence_max is not None:
            filters.append(CreatorDiscoveryProfile.influence_size_numeric <= influence_max)
        if match_confidence_min is not None:
            filters.append(CreatorDiscoveryProfile.match_confidence >= match_confidence_min)
        if analysis_status:
            filters.append(CreatorDiscoveryProfile.analysis_status == analysis_status)
        if start_year is not None:
            filters.append(CreatorDiscoveryProfile.start_year == start_year)
        if creator_uids:
            filters.append(Creator.creator_uid.in_(creator_uids))
        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)
        total = int(self.session.scalar(count_statement) or 0)
        rows = list(self.session.execute(
            statement.order_by(Creator.updated_at.desc(), Creator.id.desc()).offset(offset).limit(limit)
        ).all())
        return rows, total

    def creator_uids_for_run(self, run_uid: str) -> list[str]:
        return list(self.session.scalars(
            select(Creator.creator_uid)
            .join(CreatorCandidate, CreatorCandidate.creator_id == Creator.id)
            .join(CreatorDiscoveryRun, CreatorDiscoveryRun.id == CreatorCandidate.run_id)
            .where(CreatorDiscoveryRun.run_uid == run_uid, CreatorCandidate.creator_id.is_not(None))
            .distinct()
            .order_by(Creator.creator_uid)
        ))

    def find_account(self, platform: str, profile_url: str) -> CreatorDiscoveryAccount | None:
        return self.session.scalar(select(CreatorDiscoveryAccount).where(
            CreatorDiscoveryAccount.platform == platform,
            CreatorDiscoveryAccount.profile_url == profile_url,
        ))

    def accounts_for_creator(self, creator_id: int) -> list[CreatorDiscoveryAccount]:
        return list(self.session.scalars(
            select(CreatorDiscoveryAccount)
            .where(CreatorDiscoveryAccount.creator_id == creator_id)
            .order_by(CreatorDiscoveryAccount.platform, CreatorDiscoveryAccount.id)
        ))

    def create_account(self, values: dict[str, Any]) -> CreatorDiscoveryAccount:
        item = CreatorDiscoveryAccount(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def samples_for_creator(self, creator_id: int, limit: int = 1000) -> list[CreatorContentSample]:
        return list(self.session.scalars(
            select(CreatorContentSample)
            .where(CreatorContentSample.creator_id == creator_id)
            .order_by(CreatorContentSample.published_at.desc(), CreatorContentSample.id.desc())
            .limit(limit)
        ))

    def find_sample(self, platform: str, content_url: str) -> CreatorContentSample | None:
        return self.session.scalar(select(CreatorContentSample).where(
            CreatorContentSample.platform == platform,
            CreatorContentSample.content_url == content_url,
        ))

    def create_sample(self, values: dict[str, Any]) -> CreatorContentSample:
        item = CreatorContentSample(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def add_analysis(self, values: dict[str, Any]) -> CreatorDiscoveryAnalysis:
        item = CreatorDiscoveryAnalysis(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def analyses_for_profile(self, profile_id: int) -> list[CreatorDiscoveryAnalysis]:
        return list(self.session.scalars(
            select(CreatorDiscoveryAnalysis)
            .where(CreatorDiscoveryAnalysis.profile_id == profile_id)
            .order_by(CreatorDiscoveryAnalysis.created_at.desc())
        ))

    def add_source(self, values: dict[str, Any]) -> CreatorSource:
        item = CreatorSource(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def sources_for_profile(self, profile_id: int) -> list[CreatorSource]:
        return list(self.session.scalars(
            select(CreatorSource)
            .where(CreatorSource.profile_id == profile_id)
            .order_by(CreatorSource.retrieved_at.desc())
        ))

    def sync_industries(self, industries: list[dict[str, Any]]) -> list[CreatorIndustry]:
        existing = {item.code: item for item in self.session.scalars(select(CreatorIndustry))}
        for values in industries:
            item = existing.get(values["code"])
            if item is None:
                item = CreatorIndustry(**values)
                self.session.add(item)
            else:
                item.name = values["name"]
                item.aliases = values.get("aliases", [])
                item.active = True
        self.session.flush()
        return list(self.session.scalars(select(CreatorIndustry).order_by(CreatorIndustry.name)))

    def list_industries(self) -> list[CreatorIndustry]:
        return list(self.session.scalars(select(CreatorIndustry).where(CreatorIndustry.active.is_(True)).order_by(CreatorIndustry.name)))
