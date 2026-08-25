"""Performance snapshots and normalized metric lookups."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models.pattern_recipe import PerformanceSnapshot


class PerformanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, **values) -> PerformanceSnapshot:
        snapshot = PerformanceSnapshot(**values)
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def list_for_contents(
        self,
        content_ids: list[int],
        *,
        metric_name: str | None = None,
    ) -> list[PerformanceSnapshot]:
        if not content_ids:
            return []
        statement = select(PerformanceSnapshot).where(
            PerformanceSnapshot.content_id.in_(content_ids)
        )
        if metric_name:
            statement = statement.where(PerformanceSnapshot.metric_name == metric_name)
        return list(
            self._session.scalars(
                statement.order_by(
                    PerformanceSnapshot.content_id,
                    PerformanceSnapshot.collected_at,
                )
            )
        )

    def find_exact(
        self,
        content_id: int,
        metric_name: str,
        collected_at: datetime,
    ) -> PerformanceSnapshot | None:
        return self._session.scalar(
            select(PerformanceSnapshot).where(
                PerformanceSnapshot.content_id == content_id,
                PerformanceSnapshot.metric_name == metric_name,
                PerformanceSnapshot.collected_at == collected_at,
            )
        )

