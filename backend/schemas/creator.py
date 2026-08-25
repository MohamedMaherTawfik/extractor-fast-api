"""Pydantic contracts for creators and platform accounts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.enums import AccessStatus, Platform


class PlatformAccountCreate(BaseModel):
    platform: Platform
    username: str | None = Field(default=None, max_length=255)
    platform_user_id: str | None = Field(default=None, max_length=255)
    profile_url: str | None = Field(default=None, max_length=1000)
    display_name: str | None = Field(default=None, max_length=255)
    bio: str | None = None
    followers_count: int | None = Field(default=None, ge=0)
    following_count: int | None = Field(default=None, ge=0)
    content_count: int | None = Field(default=None, ge=0)
    verified: bool = False
    access_status: AccessStatus = AccessStatus.UNKNOWN
    last_checked_at: datetime | None = None

    @model_validator(mode="after")
    def identity_is_required(self) -> "PlatformAccountCreate":
        if not (self.username or self.platform_user_id or self.profile_url):
            raise ValueError(
                "username, platform_user_id, or profile_url is required"
            )
        return self


class PlatformAccountUpdate(BaseModel):
    platform: Platform | None = None
    username: str | None = Field(default=None, max_length=255)
    platform_user_id: str | None = Field(default=None, max_length=255)
    profile_url: str | None = Field(default=None, max_length=1000)
    display_name: str | None = Field(default=None, max_length=255)
    bio: str | None = None
    followers_count: int | None = Field(default=None, ge=0)
    following_count: int | None = Field(default=None, ge=0)
    content_count: int | None = Field(default=None, ge=0)
    verified: bool | None = None
    access_status: AccessStatus | None = None
    last_checked_at: datetime | None = None


class PlatformAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int
    platform: Platform
    username: str | None
    platform_user_id: str | None
    profile_url: str | None
    display_name: str | None
    bio: str | None
    followers_count: int | None
    following_count: int | None
    content_count: int | None
    verified: bool
    access_status: AccessStatus
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CreatorCreate(BaseModel):
    creator_uid: str | None = Field(
        default=None,
        pattern=r"^CR_\d{6,}$",
        max_length=32,
    )
    display_name: str = Field(min_length=1, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    primary_language: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    priority: int = Field(default=0, ge=0)
    active: bool = True
    possible_duplicate: bool = False


class CreatorUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    primary_language: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    priority: int | None = Field(default=None, ge=0)
    active: bool | None = None
    possible_duplicate: bool | None = None


class CreatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_uid: str
    display_name: str
    country: str | None
    primary_language: str | None
    category: str | None
    notes: str | None
    priority: int
    active: bool
    possible_duplicate: bool
    created_at: datetime
    updated_at: datetime
    accounts: list[PlatformAccountResponse] = Field(default_factory=list)
