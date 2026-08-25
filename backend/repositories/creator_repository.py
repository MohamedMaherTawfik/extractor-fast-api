"""Persistence operations for Creator Master."""

from uuid import uuid4

from sqlalchemy import String, cast, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from backend.core.enums import Platform
from backend.db.models.creator import Creator
from backend.db.models.platform_account import PlatformAccount


class CreatorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, creator_id: int) -> Creator | None:
        statement = (
            select(Creator)
            .where(Creator.id == creator_id)
            .options(selectinload(Creator.accounts))
        )
        return self._session.scalar(statement)

    def get_by_uid(self, creator_uid: str) -> Creator | None:
        statement = (
            select(Creator)
            .where(Creator.creator_uid == creator_uid)
            .options(selectinload(Creator.accounts))
        )
        return self._session.scalar(statement)

    def list(
        self,
        *,
        search: str | None = None,
        platform: Platform | None = None,
        country: str | None = None,
        category: str | None = None,
        active: bool | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Creator]:
        statement = (
            select(Creator)
            .outerjoin(PlatformAccount)
            .options(selectinload(Creator.accounts))
        )
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Creator.display_name.ilike(pattern),
                    Creator.creator_uid.ilike(pattern),
                    PlatformAccount.username.ilike(pattern),
                    cast(PlatformAccount.platform, String).ilike(pattern),
                )
            )
        if platform is not None:
            statement = statement.where(PlatformAccount.platform == platform)
        if country:
            statement = statement.where(
                func.lower(Creator.country) == country.strip().casefold()
            )
        if category:
            statement = statement.where(
                func.lower(Creator.category) == category.strip().casefold()
            )
        if active is not None:
            statement = statement.where(Creator.active == active)
        statement = (
            statement.distinct()
            .order_by(Creator.priority.desc(), Creator.display_name, Creator.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement).unique())

    def create(self, values: dict) -> Creator:
        values = dict(values)
        requested_uid = values.pop("creator_uid", None)
        creator = Creator(
            creator_uid=requested_uid or f"TEMP_{uuid4().hex}",
            **values,
        )
        self._session.add(creator)
        self._session.flush()
        if requested_uid is None:
            creator.creator_uid = f"CR_{creator.id:06d}"
            self._session.flush()
        return creator

    def update(self, creator: Creator, values: dict) -> Creator:
        for field, value in values.items():
            setattr(creator, field, value)
        self._session.flush()
        return creator

    def possible_name_matches(
        self,
        display_name: str,
        country: str | None,
    ) -> list[Creator]:
        statement = select(Creator).where(
            func.lower(Creator.display_name) == display_name.strip().casefold()
        )
        if country:
            statement = statement.where(
                func.lower(Creator.country) == country.strip().casefold()
            )
        return list(self._session.scalars(statement))

    def mark_possible_duplicates(self, creator_ids: set[int]) -> None:
        if creator_ids:
            self._session.execute(
                update(Creator)
                .where(Creator.id.in_(creator_ids))
                .values(possible_duplicate=True)
            )
            self._session.flush()
