"""Persistence boundary for providers, jobs, prompts, assets, QA, and provenance."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.enums import GenerationJobStatus
from backend.db.models.generation import (
    AssetReference, AssetVersion, ContinuityState, GeneratedAsset, GenerationAttempt,
    GenerationCostRecord, GenerationEvent, GenerationJob, GenerationQARun,
    GenerationQAResult, ModelProfile, PromptPackage, PromptPackageVersion,
    ProviderProfile, ProvenanceRecord, Storyboard, StoryboardShot,
)


class GenerationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_provider(self, **values) -> ProviderProfile:
        item = self.session.scalar(select(ProviderProfile).where(ProviderProfile.provider_code == values["provider_code"]))
        if item is None:
            item = ProviderProfile(**values)
            self.session.add(item)
        else:
            for key, value in values.items(): setattr(item, key, value)
        self.session.flush()
        return item

    def get_provider(self, code: str) -> ProviderProfile | None:
        return self.session.scalar(select(ProviderProfile).where(ProviderProfile.provider_code == code))

    def list_providers(self) -> list[ProviderProfile]:
        return list(self.session.scalars(select(ProviderProfile).order_by(ProviderProfile.provider_code)))

    def upsert_model(self, **values) -> ModelProfile:
        item = self.session.scalar(select(ModelProfile).where(
            ModelProfile.provider_code == values["provider_code"],
            ModelProfile.model_id == values["model_id"],
            ModelProfile.model_version == values["model_version"],
        ))
        if item is None:
            item = ModelProfile(**values)
            self.session.add(item)
        else:
            for key, value in values.items(): setattr(item, key, value)
        self.session.flush()
        return item

    def list_models(self) -> list[ModelProfile]:
        return list(self.session.scalars(select(ModelProfile).order_by(ModelProfile.provider_code, ModelProfile.model_id)))

    def create_job(self, **values) -> GenerationJob:
        item = GenerationJob(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def get_job(self, identifier: int | str) -> GenerationJob | None:
        predicate = GenerationJob.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else GenerationJob.job_uid == str(identifier)
        return self.session.scalar(self._job_statement().where(predicate))

    def list_jobs(self, *, status: str | None = None, limit: int = 100) -> list[GenerationJob]:
        statement = self._job_statement()
        if status: statement = statement.where(GenerationJob.status == status)
        return list(self.session.scalars(statement.order_by(GenerationJob.created_at.desc()).limit(limit)).unique())

    def find_cached(self, key: str) -> GenerationJob | None:
        # Sessions intentionally disable autoflush; make terminal state changes
        # visible to the idempotency query when jobs are executed inline.
        self.session.flush()
        return self.session.scalar(self._job_statement().where(
            GenerationJob.idempotency_key == key,
            GenerationJob.status.in_([GenerationJobStatus.COMPLETED, GenerationJobStatus.COMPLETED_WITH_FALLBACK, GenerationJobStatus.APPROVED]),
        ).order_by(GenerationJob.id.desc()))

    def add_attempt(self, job: GenerationJob, **values) -> GenerationAttempt:
        item = GenerationAttempt(**values)
        job.attempts.append(item)
        self.session.flush()
        return item

    def add_event(self, job: GenerationJob, **values) -> GenerationEvent:
        item = GenerationEvent(**values)
        job.events.append(item)
        return item

    def create_prompt_package(self, job: GenerationJob, **values) -> PromptPackage:
        item = PromptPackage(job_id=job.id, **values)
        self.session.add(item)
        self.session.flush()
        return item

    def add_prompt_version(self, package: PromptPackage, **values) -> PromptPackageVersion:
        item = PromptPackageVersion(**values)
        package.versions.append(item)
        package.current_version = item.version
        self.session.flush()
        return item

    def prompt_for_job(self, job_id: int) -> PromptPackage | None:
        return self.session.scalar(select(PromptPackage).options(selectinload(PromptPackage.versions)).where(PromptPackage.job_id == job_id))

    def create_asset(self, job: GenerationJob, **values) -> GeneratedAsset:
        item = GeneratedAsset(**values)
        job.assets.append(item)
        self.session.flush()
        return item

    def add_asset_version(self, asset: GeneratedAsset, **values) -> AssetVersion:
        item = AssetVersion(**values)
        asset.versions.append(item)
        asset.current_version = item.version
        self.session.flush()
        return item

    def get_asset(self, identifier: int | str) -> GeneratedAsset | None:
        predicate = GeneratedAsset.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else GeneratedAsset.asset_uid == str(identifier)
        return self.session.scalar(select(GeneratedAsset).options(selectinload(GeneratedAsset.versions)).where(predicate))

    def add_reference(self, job: GenerationJob, **values) -> AssetReference:
        item = AssetReference(job_id=job.id, **values)
        self.session.add(item)
        return item

    def references_for_job(self, job_id: int) -> list[AssetReference]:
        return list(self.session.scalars(select(AssetReference).where(AssetReference.job_id == job_id)))

    def create_qa_run(self, **values) -> GenerationQARun:
        item = GenerationQARun(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def add_qa_result(self, run: GenerationQARun, **values) -> GenerationQAResult:
        item = GenerationQAResult(**values)
        run.results.append(item)
        return item

    def qa_for_asset_version(self, version_id: int) -> list[GenerationQARun]:
        return list(self.session.scalars(select(GenerationQARun).options(selectinload(GenerationQARun.results)).where(GenerationQARun.asset_version_id == version_id)))

    def add_cost(self, **values) -> GenerationCostRecord:
        item = GenerationCostRecord(**values)
        self.session.add(item)
        return item

    def add_continuity(self, **values) -> ContinuityState:
        item = ContinuityState(**values)
        self.session.add(item)
        return item

    def create_storyboard(self, **values) -> Storyboard:
        item = Storyboard(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def add_storyboard_shot(self, storyboard: Storyboard, **values) -> StoryboardShot:
        item = StoryboardShot(**values)
        storyboard.shots.append(item)
        return item

    def add_provenance(self, **values) -> ProvenanceRecord:
        item = ProvenanceRecord(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def provenance_for_asset(self, asset: GeneratedAsset) -> list[ProvenanceRecord]:
        version_ids = [item.id for item in asset.versions]
        if not version_ids: return []
        return list(self.session.scalars(select(ProvenanceRecord).where(ProvenanceRecord.asset_version_id.in_(version_ids)).order_by(ProvenanceRecord.id)))

    @staticmethod
    def _job_statement():
        return select(GenerationJob).options(
            selectinload(GenerationJob.assets).selectinload(GeneratedAsset.versions),
            selectinload(GenerationJob.attempts), selectinload(GenerationJob.events),
        )
