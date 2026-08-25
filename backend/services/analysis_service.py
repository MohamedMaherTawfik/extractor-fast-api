"""Rules-driven universal analysis orchestration and persistent job lifecycle."""

import logging
from collections import defaultdict
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.analyzers.engine import UNKNOWN
from backend.analyzers.normalizer import AnalysisResultNormalizer
from backend.analyzers.registry import AnalysisEngineRegistry
from backend.analyzers.router import ContentRouter
from backend.analyzers.rules import AnalysisRuleCatalog
from backend.analyzers.timeline import EmbeddedTimelineProvider, TimelineProvider
from backend.core.config import Settings, get_settings
from backend.core.enums import (
    AnalysisMode,
    AnalysisResultStatus,
    AnalysisRunStatus,
    AnalysisStatus,
)
from backend.core.exceptions import AnalysisEngineError, NotFoundError
from backend.db.base import utc_now
from backend.db.models.analysis import AnalysisRun
from backend.db.models.content_item import ContentItem
from backend.repositories.analysis_repository import (
    AnalysisRepository,
    TimelineEntities,
)
from backend.repositories.content_repository import ContentRepository
from backend.schemas.analysis import (
    AnalysisBatchRequest,
    AnalysisOptions,
    ContentAnalysisResponse,
    EngineResultDraft,
)
from backend.schemas.analysis_rules import ExtractionRule
from backend.services.analysis_cache import AnalysisCacheKeyBuilder


logger = logging.getLogger(__name__)

_MODE_ENGINES = {
    AnalysisMode.VISUAL_ONLY: {"metadata", "video_structure", "vision", "ocr"},
    AnalysisMode.AUDIO_ONLY: {"metadata", "audio", "speech"},
    AnalysisMode.TEXT_ONLY: {"metadata", "copy", "behavior", "seo"},
}


class UniversalContentAnalyzer:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        engines: AnalysisEngineRegistry | None = None,
        rules: AnalysisRuleCatalog | None = None,
        router: ContentRouter | None = None,
        timeline_provider: TimelineProvider | None = None,
    ) -> None:
        self._session = session
        self.settings = settings or get_settings()
        self.engines = engines or AnalysisEngineRegistry()
        self.rules = rules or AnalysisRuleCatalog()
        self.router = router or ContentRouter()
        self.timeline_provider = timeline_provider or EmbeddedTimelineProvider()
        self.normalizer = AnalysisResultNormalizer()
        self.cache = AnalysisCacheKeyBuilder(
            self.settings.analysis_chunk_size_bytes
        )
        self.content = ContentRepository(session)
        self.analysis = AnalysisRepository(session)

    def analyze_content(
        self,
        content_identifier: int | str,
        options: AnalysisOptions | None = None,
        *,
        batch_uid: str | None = None,
    ) -> AnalysisRun:
        effective_options = options or AnalysisOptions()
        content = self._get_content(content_identifier)
        rule_set = self.rules.load(
            self.settings.analysis_rules_file,
            self.settings.analysis_taxonomy_file,
        )
        selected_rules = rule_set.select(effective_options.rules_subset)
        candidate_rules = self._filter_mode(selected_rules, effective_options.mode)
        route = self.router.route(content)
        engine_names = {rule.engine for rule in candidate_rules}
        model_version = self.engines.model_version(engine_names)
        media_hash = self.cache.media_hash(content)
        cache_key = self.cache.cache_key(
            media_hash=media_hash,
            analyzer_version=self.settings.analyzer_version,
            rules_version=rule_set.rules_version,
            taxonomy_version=rule_set.taxonomy_version,
            model_version=model_version,
            rule_ids=[rule.rule_id for rule in candidate_rules],
            options=effective_options,
        )
        if not effective_options.force_reanalysis:
            cached = self.analysis.find_cached(content.id, cache_key)
            if cached is not None:
                logger.info(
                    "analysis_cache_hit job=%s content=%s",
                    cached.job_uid,
                    content.content_uid,
                )
                return cached

        run = self.analysis.create_run(
            batch_uid=batch_uid,
            content_id=content.id,
            status=AnalysisRunStatus.QUEUED,
            media_hash=media_hash,
            cache_key=cache_key,
            analyzer_version=self.settings.analyzer_version,
            rules_version=rule_set.rules_version,
            taxonomy_version=rule_set.taxonomy_version,
            model_version=model_version,
            options=effective_options.model_dump(mode="json"),
        )
        run.started_at = utc_now()
        content.analysis_status = AnalysisStatus.RUNNING
        errors: list[dict[str, str]] = []
        logger.info(
            "analysis_started job=%s content=%s mode=%s",
            run.job_uid,
            content.content_uid,
            effective_options.mode.value,
        )

        try:
            run.status = AnalysisRunStatus.PREPROCESSING
            self._session.flush()
            try:
                timeline = self.timeline_provider.extract(content)
                entities = self.analysis.persist_timeline(run, timeline)
            except Exception as exc:
                errors.append(_safe_error("timeline", exc))
                entities = TimelineEntities({}, {}, {}, {}, {})
                logger.error(
                    "analysis_timeline_failed job=%s error_type=%s",
                    run.job_uid,
                    type(exc).__name__,
                )

            run.status = AnalysisRunStatus.ANALYZING
            self._session.flush()
            outputs: dict[str, tuple[EngineResultDraft, bool]] = {}
            grouped: dict[str, list[ExtractionRule]] = defaultdict(list)
            not_applicable: set[str] = set()
            for rule in candidate_rules:
                if (
                    rule.engine not in route.engines
                    or not rule.applies_to_modalities(set(route.modalities))
                ):
                    not_applicable.add(rule.rule_id)
                else:
                    grouped[rule.engine].append(rule)

            for engine_name, engine_rules in grouped.items():
                try:
                    engine = self.engines.get(engine_name)
                    drafts = engine.analyze(content, engine_rules)
                    by_rule = {draft.rule_id: draft for draft in drafts}
                    for rule in engine_rules:
                        outputs[rule.rule_id] = (
                            by_rule.get(
                                rule.rule_id,
                                EngineResultDraft(
                                    rule_id=rule.rule_id,
                                    value=UNKNOWN,
                                    confidence=0,
                                    evidence=None,
                                    source=engine_name,
                                ),
                            ),
                            False,
                        )
                except Exception as exc:
                    errors.append(_safe_error(engine_name, exc))
                    logger.error(
                        "analysis_engine_failed job=%s engine=%s error_type=%s",
                        run.job_uid,
                        engine_name,
                        type(exc).__name__,
                    )
                    for rule in engine_rules:
                        outputs[rule.rule_id] = (
                            EngineResultDraft(
                                rule_id=rule.rule_id,
                                value=UNKNOWN,
                                confidence=0,
                                evidence=None,
                                source=engine_name,
                            ),
                            True,
                        )

            run.status = AnalysisRunStatus.NORMALIZING
            self._session.flush()
            result_statuses = []
            for rule in candidate_rules:
                if rule.rule_id in not_applicable:
                    normalized = self.normalizer.not_applicable(
                        content_id=content.id,
                        rule=rule,
                    )
                else:
                    draft, engine_failed = outputs[rule.rule_id]
                    normalized = self.normalizer.normalize(
                        content_id=content.id,
                        rule=rule,
                        engine=rule.engine,
                        draft=draft,
                        engine_failed=engine_failed,
                    )
                self.analysis.add_result(run, normalized, entities)
                result_statuses.append(normalized.status)

            run.results_count = len(result_statuses)
            run.errors = errors or None
            run.error_summary = (
                f"{len(errors)} analysis component(s) failed"
                if errors
                else None
            )
            if errors and result_statuses and all(
                status is AnalysisResultStatus.FAILED
                for status in result_statuses
            ):
                final_status = AnalysisRunStatus.FAILED
            elif errors:
                final_status = AnalysisRunStatus.PARTIAL
            else:
                final_status = AnalysisRunStatus.COMPLETED
            self._complete(run, content, final_status)
        except Exception as exc:
            errors.append(_safe_error("orchestrator", exc))
            run.errors = errors
            run.error_summary = "Analysis orchestration failed"
            self._complete(run, content, AnalysisRunStatus.FAILED)
        return run

    def analyze_batch(self, request: AnalysisBatchRequest) -> list[AnalysisRun]:
        batch_uid = f"ANB_{uuid4().hex.upper()}"
        options = AnalysisOptions.model_validate(
            request.model_dump(exclude={"content_ids"})
        )
        return [
            self.analyze_content(identifier, options, batch_uid=batch_uid)
            for identifier in request.content_ids
        ]

    def get_run(self, identifier: int | str) -> AnalysisRun:
        run = self.analysis.get_run(identifier)
        if run is None:
            raise NotFoundError(f"Analysis job {identifier} was not found")
        return run

    def get_content_analysis(
        self,
        content_identifier: int | str,
    ) -> ContentAnalysisResponse:
        content = self._get_content(content_identifier)
        run = self.analysis.latest_for_content(content.id)
        if run is None:
            raise NotFoundError(
                f"Content {content_identifier} has no analysis"
            )
        return ContentAnalysisResponse.model_validate(
            {
                "run": run,
                "segments": run.segments,
                "shots": run.shots,
                "results": run.results,
                "visual_events": run.visual_events,
                "audio_events": run.audio_events,
                "text_events": run.text_events,
            }
        )

    def _get_content(self, identifier: int | str) -> ContentItem:
        content = (
            self.content.get(int(identifier))
            if isinstance(identifier, int) or str(identifier).isdigit()
            else self.content.get_by_uid(str(identifier))
        )
        if content is None:
            raise NotFoundError(f"Content {identifier} was not found")
        return content

    @staticmethod
    def _filter_mode(
        rules: tuple[ExtractionRule, ...],
        mode: AnalysisMode,
    ) -> tuple[ExtractionRule, ...]:
        if mode is AnalysisMode.FULL:
            return rules
        allowed = _MODE_ENGINES[mode]
        return tuple(rule for rule in rules if rule.engine in allowed)

    def _complete(
        self,
        run: AnalysisRun,
        content: ContentItem,
        status: AnalysisRunStatus,
    ) -> None:
        run.status = status
        run.completed_at = utc_now()
        if status is AnalysisRunStatus.FAILED:
            content.analysis_status = AnalysisStatus.FAILED
        elif status is AnalysisRunStatus.PARTIAL:
            content.analysis_status = AnalysisStatus.PARTIAL
        else:
            content.analysis_status = AnalysisStatus.COMPLETED
        self._session.flush()
        logger.info(
            "analysis_finished job=%s status=%s results=%d",
            run.job_uid,
            status.value,
            run.results_count,
        )


def _safe_error(component: str, exc: Exception) -> dict[str, str]:
    return {
        "component": component,
        "type": type(exc).__name__,
        "message": "Component failed without discarding other analysis results",
    }
