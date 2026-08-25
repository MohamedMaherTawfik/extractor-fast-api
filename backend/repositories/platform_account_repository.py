"""Persistence operations for creator platform accounts."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.core.enums import Platform
from backend.db.models.platform_account import PlatformAccount


class PlatformAccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, account_id: int) -> PlatformAccount | None:
        return self._session.get(PlatformAccount, account_id)

    def list_for_creator(self, creator_id: int) -> list[PlatformAccount]:
        statement = (
            select(PlatformAccount)
            .where(PlatformAccount.creator_id == creator_id)
            .order_by(PlatformAccount.platform, PlatformAccount.username)
        )
        return list(self._session.scalars(statement))

    def find_matches(
        self,
        *,
        platform: Platform,
        username: str | None,
        platform_user_id: str | None,
        profile_url: str | None,
        exclude_id: int | None = None,
    ) -> list[PlatformAccount]:
        conditions = []
        if username:
            conditions.append(PlatformAccount.username == username)
        if platform_user_id:
            conditions.append(PlatformAccount.platform_user_id == platform_user_id)
        if profile_url:
            conditions.append(PlatformAccount.profile_url == profile_url)
        if not conditions:
            return []
        statement = select(PlatformAccount).where(
            PlatformAccount.platform == platform,
            or_(*conditions),
        )
        if exclude_id is not None:
            statement = statement.where(PlatformAccount.id != exclude_id)
        return list(self._session.scalars(statement))

    def create(self, creator_id: int, values: dict) -> PlatformAccount:
        account = PlatformAccount(creator_id=creator_id, **values)
        self._session.add(account)
        self._session.flush()
        return account

    def update(
        self,
        account: PlatformAccount,
        values: dict,
    ) -> PlatformAccount:
        for field, value in values.items():
            setattr(account, field, value)
        self._session.flush()
        return account
