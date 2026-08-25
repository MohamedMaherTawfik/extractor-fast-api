"""Creator and account use cases."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.enums import Platform
from backend.core.exceptions import ConflictError, NotFoundError
from backend.db.models.creator import Creator
from backend.db.models.platform_account import PlatformAccount
from backend.repositories.creator_repository import CreatorRepository
from backend.repositories.platform_account_repository import (
    PlatformAccountRepository,
)
from backend.schemas.creator import (
    CreatorCreate,
    CreatorUpdate,
    PlatformAccountCreate,
    PlatformAccountUpdate,
)
from backend.services.normalization import AccountNormalizer


class CreatorService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self.creators = CreatorRepository(session)
        self.accounts = PlatformAccountRepository(session)
        self.normalizer = AccountNormalizer()

    def list_creators(
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
        return self.creators.list(
            search=search,
            platform=platform,
            country=country,
            category=category,
            active=active,
            offset=offset,
            limit=limit,
        )

    def get_creator(self, creator_id: int) -> Creator:
        creator = self.creators.get(creator_id)
        if creator is None:
            raise NotFoundError(f"Creator {creator_id} was not found")
        return creator

    def create_creator(self, data: CreatorCreate) -> Creator:
        try:
            return self.creators.create(data.model_dump())
        except IntegrityError as exc:
            raise ConflictError("creator_uid already exists") from exc

    def update_creator(self, creator_id: int, data: CreatorUpdate) -> Creator:
        creator = self.get_creator(creator_id)
        return self.creators.update(
            creator,
            data.model_dump(exclude_unset=True),
        )

    def list_accounts(self, creator_id: int) -> list[PlatformAccount]:
        self.get_creator(creator_id)
        return self.accounts.list_for_creator(creator_id)

    def add_account(
        self,
        creator_id: int,
        data: PlatformAccountCreate,
    ) -> PlatformAccount:
        self.get_creator(creator_id)
        values = data.model_dump()
        normalized = self.normalizer.normalize_account(
            platform=values["platform"],
            username=values.get("username"),
            profile_url=values.get("profile_url"),
            platform_user_id=values.get("platform_user_id"),
        )
        values.update(
            platform=normalized.platform,
            username=normalized.username,
            profile_url=normalized.profile_url,
            platform_user_id=normalized.platform_user_id,
        )
        matches = self.accounts.find_matches(
            platform=normalized.platform,
            username=normalized.username,
            profile_url=normalized.profile_url,
            platform_user_id=normalized.platform_user_id,
        )
        if matches:
            raise ConflictError("Platform account already exists")
        try:
            return self.accounts.create(creator_id, values)
        except IntegrityError as exc:
            raise ConflictError("Platform account already exists") from exc

    def update_account(
        self,
        account_id: int,
        data: PlatformAccountUpdate,
    ) -> PlatformAccount:
        account = self.accounts.get(account_id)
        if account is None:
            raise NotFoundError(f"Platform account {account_id} was not found")
        values = data.model_dump(exclude_unset=True)
        normalized = self.normalizer.normalize_account(
            platform=values.get("platform", account.platform),
            username=values.get("username", account.username),
            profile_url=values.get("profile_url", account.profile_url),
            platform_user_id=values.get(
                "platform_user_id",
                account.platform_user_id,
            ),
        )
        values.update(
            platform=normalized.platform,
            username=normalized.username,
            profile_url=normalized.profile_url,
            platform_user_id=normalized.platform_user_id,
        )
        matches = self.accounts.find_matches(
            platform=normalized.platform,
            username=normalized.username,
            profile_url=normalized.profile_url,
            platform_user_id=normalized.platform_user_id,
            exclude_id=account.id,
        )
        if matches:
            raise ConflictError("Platform account already exists")
        try:
            return self.accounts.update(account, values)
        except IntegrityError as exc:
            raise ConflictError("Platform account already exists") from exc
