"""Thin service layer for safe desktop discovery and operational read models."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.answer_bot.channels import ChannelRegistry
from backend.core.config import get_settings
from backend.core.exceptions import NotFoundError
from backend.repositories.operator_repository import OperatorRepository, WORKSPACES


class OperatorService:
    def __init__(self, session: Session) -> None: self.repository = OperatorRepository(session); self.settings = get_settings()

    def capabilities(self) -> dict:
        return {
            "app": {"name": self.settings.app_name, "version": self.settings.version, "environment": self.settings.environment},
            "modules": {
                "content": {"enabled": True, "version": self.settings.analyzer_version},
                "intelligence": {"enabled": True, "version": self.settings.pattern_engine_version},
                "patterns_recipes": {"enabled": True, "version": self.settings.recipe_engine_version},
                "rules": {"enabled": True, "version": self.settings.rules_engine_version},
                "generation": {"enabled": True, "version": self.settings.generation_engine_version},
                "sales": {"enabled": True, "version": self.settings.sales_engine_version},
                "msc": {"enabled": True, "version": self.settings.sales_engine_version},
                "answer_bot": {"enabled": True, "version": self.settings.answer_bot_version},
                "content_calendar": {"enabled": True, "version": "ui-planning-1.0.0", "mode": "planning_read_only"},
                "lead_engine": {"enabled": False, "status": "not_implemented"},
                "publishing": {"enabled": False, "status": "not_implemented"},
            },
            "features": {name.replace("-", "_") + "_enabled": True for name in WORKSPACES},
            "privacy_mode": self.settings.messaging_privacy_mode,
            "realtime": {"transport": "adaptive_polling", "recommended_interval_seconds": 15},
        }

    def health(self) -> dict:
        channels = ChannelRegistry().status()
        return {
            "backend": "ONLINE", "database": "ONLINE", "storage": "ONLINE",
            "generation_providers": "ONLINE", "messaging_providers": "ONLINE" if any(item["adapter_registered"] for item in channels) else "NOT_CONFIGURED",
            "msc_intake": "ONLINE", "queue": "ONLINE",
        }

    def workspace(self, name: str, offset: int, limit: int) -> dict:
        result = self.repository.workspace(name, offset=offset, limit=limit)
        if result is None: raise NotFoundError(f"Operator workspace {name} is not available")
        return result

    def settings_view(self) -> dict:
        return {
            "backend": {"host": self.settings.host, "port": self.settings.port, "environment": self.settings.environment},
            "privacy": {"messaging": self.settings.messaging_privacy_mode, "live_generation_tests": self.settings.run_live_generation_tests, "live_messaging_tests": self.settings.run_live_messaging_tests, "live_msc_tests": self.settings.run_live_msc_extraction_tests},
            "versions": {"app": self.settings.version, "generation": self.settings.generation_engine_version, "sales": self.settings.sales_engine_version, "answer_bot": self.settings.answer_bot_version},
            "channels": ChannelRegistry().status(),
        }
