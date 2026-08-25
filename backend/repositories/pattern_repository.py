"""Pattern mining run, pattern, feature, and evidence persistence."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from backend.db.models.pattern_recipe import (
    Pattern,
    PatternContentLink,
    PatternFeature,
    PatternMiningRun,
)


class PatternRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(self, **values) -> PatternMiningRun:
        run = PatternMiningRun(**values)
        self._session.add(run)
        self._session.flush()
        return run

    def upsert(self, *, features: list[dict], links: list[dict], **values) -> Pattern:
        pattern = self._session.scalar(
            self._statement().where(Pattern.fingerprint == values["fingerprint"])
        )
        if pattern is None:
            pattern = Pattern(**values)
            self._session.add(pattern)
            self._session.flush()
        else:
            for key, value in values.items():
                if key not in {"pattern_uid", "created_at"}:
                    setattr(pattern, key, value)
            pattern.features.clear()
            pattern.content_links.clear()
            self._session.flush()
        pattern.features.extend(PatternFeature(**item) for item in features)
        pattern.content_links.extend(PatternContentLink(**item) for item in links)
        self._session.flush()
        return pattern

    def get(self, identifier: int | str) -> Pattern | None:
        predicate = (
            Pattern.id == int(identifier)
            if isinstance(identifier, int) or str(identifier).isdigit()
            else Pattern.pattern_uid == str(identifier)
        )
        return self._session.scalar(self._statement().where(predicate))

    def get_many(self, identifiers: list[int | str]) -> list[Pattern]:
        numeric = [int(item) for item in identifiers if isinstance(item, int) or str(item).isdigit()]
        uids = [str(item) for item in identifiers if not (isinstance(item, int) or str(item).isdigit())]
        predicates = []
        if numeric:
            predicates.append(Pattern.id.in_(numeric))
        if uids:
            predicates.append(Pattern.pattern_uid.in_(uids))
        if not predicates:
            return []
        return list(self._session.scalars(self._statement().where(or_(*predicates))))

    def list(
        self,
        *,
        pattern_type: str | None = None,
        status: str | None = None,
        platform: str | None = None,
        content_type: str | None = None,
        creator_id: int | None = None,
        category: str | None = None,
        language: str | None = None,
        country: str | None = None,
        traffic_type: str | None = None,
        limit: int = 100,
        top: bool = False,
    ) -> list[Pattern]:
        statement = self._statement()
        if pattern_type:
            statement = statement.where(Pattern.pattern_type == pattern_type)
        if status:
            statement = statement.where(Pattern.status == status)
        if platform:
            statement = statement.where(Pattern.scope["platform"].as_string() == platform)
        if content_type:
            statement = statement.where(Pattern.scope["content_type"].as_string() == content_type)
        if creator_id is not None:
            statement = statement.where(Pattern.scope["creator_id"].as_integer() == creator_id)
        for key, value in (
            ("category", category),
            ("language", language),
            ("country", country),
            ("traffic_type", traffic_type),
        ):
            if value:
                statement = statement.where(Pattern.scope[key].as_string() == value)
        ordering = Pattern.pattern_score.desc() if top else Pattern.updated_at.desc()
        return list(self._session.scalars(statement.order_by(ordering).limit(limit)))

    @staticmethod
    def _statement():
        return select(Pattern).options(
            selectinload(Pattern.features),
            selectinload(Pattern.content_links),
        )
