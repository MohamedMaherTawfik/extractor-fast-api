"""Minimal metadata table used to verify the persistence layer."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin


class SystemMeta(TimestampMixin, Base):
    __tablename__ = "system_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
