"""Connector discovery with explicit, credential-free availability states."""

from dataclasses import dataclass

from backend.connectors.base import BaseConnector
from backend.connectors.config import ConnectorConfig, ConnectorConfigLoader
from backend.core.enums import ConnectorAvailability, Platform
from backend.core.exceptions import ConnectorUnavailableError


@dataclass(frozen=True)
class ConnectorEntry:
    platform: Platform
    availability: ConnectorAvailability
    config: ConnectorConfig
    connector: BaseConnector | None = None


class ConnectorRegistry:
    def __init__(self, loader: ConnectorConfigLoader | None = None) -> None:
        self._loader = loader or ConnectorConfigLoader()
        self._entries = {
            platform: self._entry_from_config(platform)
            for platform in Platform
        }

    def _entry_from_config(self, platform: Platform) -> ConnectorEntry:
        config = self._loader.load(platform)
        return ConnectorEntry(platform, config.availability, config)

    def register(
        self,
        platform: Platform,
        connector: BaseConnector,
        config: ConnectorConfig | None = None,
    ) -> None:
        effective_config = config or self._loader.load(platform)
        self._entries[platform] = ConnectorEntry(
            platform=platform,
            availability=ConnectorAvailability.CONFIGURED,
            config=effective_config,
            connector=connector,
        )

    def describe(self, platform: Platform | str) -> ConnectorEntry:
        try:
            platform_value = (
                platform if isinstance(platform, Platform) else Platform(platform)
            )
        except ValueError as exc:
            raise ConnectorUnavailableError(
                str(platform), ConnectorAvailability.UNSUPPORTED.value
            ) from exc
        return self._entries[platform_value]

    def get(self, platform: Platform | str) -> BaseConnector:
        entry = self.describe(platform)
        if entry.connector is None:
            raise ConnectorUnavailableError(
                entry.platform.value,
                entry.availability.value,
            )
        return entry.connector

    def statuses(self) -> dict[str, str]:
        return {
            platform.value: entry.availability.value
            for platform, entry in self._entries.items()
        }


connector_registry = ConnectorRegistry()


def get_connector(platform: Platform | str) -> BaseConnector:
    return connector_registry.get(platform)
