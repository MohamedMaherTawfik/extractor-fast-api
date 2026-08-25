"""Database access for system metadata."""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.db.models.system_meta import SystemMeta


class SystemMetaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_key(self, key: str) -> SystemMeta | None:
        statement = select(SystemMeta).where(SystemMeta.key == key)
        return self._session.scalar(statement)

    def set(self, key: str, value: str) -> SystemMeta:
        record = self.get_by_key(key)
        if record is None:
            record = SystemMeta(key=key, value=value)
            self._session.add(record)
        else:
            record.value = value
        self._session.flush()
        return record

    def health_check(self) -> bool:
        return self._session.execute(text("SELECT 1")).scalar_one() == 1
