from dataclasses import replace

import pytest

from backend.connectors.config import ConnectorConfigLoader
from backend.connectors.resilience import RateLimiter, RetryPolicy
from backend.connectors.url_router import PlatformURLKind, route_platform_url
from backend.core.enums import ConnectorAvailability, Platform
from backend.core.exceptions import (
    ConnectorPermissionError,
    ConnectorRateLimitError,
    ConfigurationError,
    InvalidAccountError,
)


def test_url_router_distinguishes_profiles_and_content() -> None:
    profile = route_platform_url("https://www.instagram.com/example/")
    content = route_platform_url("https://x.com/example/status/123")
    youtube = route_platform_url("https://youtube.com/watch?v=abc")

    assert (profile.platform, profile.kind) == (
        Platform.INSTAGRAM,
        PlatformURLKind.PROFILE,
    )
    assert content.kind is PlatformURLKind.CONTENT
    assert youtube.kind is PlatformURLKind.CONTENT


def test_retry_honors_rate_limit_delay_and_stops_on_permission() -> None:
    calls = 0
    delays = []

    def retryable_operation():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectorRateLimitError("slow down", retry_after=2.5)
        return "ok"

    policy = RetryPolicy(2, 1, 10, sleep=delays.append)
    assert policy.run(retryable_operation) == "ok"
    assert delays == [2.5]

    with pytest.raises(ConnectorPermissionError):
        policy.run(lambda: (_ for _ in ()).throw(ConnectorPermissionError("denied")))

    invalid_calls = []

    def invalid_operation():
        invalid_calls.append(True)
        raise InvalidAccountError("invalid")

    with pytest.raises(InvalidAccountError):
        policy.run(invalid_operation)
    assert len(invalid_calls) == 1


def test_unexpected_connector_errors_have_a_bounded_retry() -> None:
    calls = []

    def operation():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("unexpected")
        return "recovered"

    policy = RetryPolicy(1, 0, 0, sleep=lambda delay: None)
    assert policy.run(operation) == "recovered"
    assert len(calls) == 2


def test_rate_limiter_uses_injected_clock_without_network_or_real_sleep() -> None:
    now = [0.0]
    waits = []

    def sleep(delay: float) -> None:
        waits.append(delay)
        now[0] += delay

    limiter = RateLimiter(60, clock=lambda: now[0], sleep=sleep)
    limiter.acquire()
    limiter.acquire()

    assert waits == [1.0]


def test_platform_configs_are_explicit_and_credential_free(tmp_path, monkeypatch) -> None:
    statuses = {
        platform: ConnectorConfigLoader().load(platform).availability
        for platform in Platform
    }
    assert statuses[Platform.INSTAGRAM] is ConnectorAvailability.PERMISSION_REQUIRED
    assert statuses[Platform.YOUTUBE] is ConnectorAvailability.NOT_CONFIGURED
    assert statuses[Platform.WEBSITE] is ConnectorAvailability.UNSUPPORTED

    source = tmp_path / "instagram.yaml"
    source.write_text("access_token: forbidden", encoding="utf-8")
    from backend.connectors import config as config_module

    monkeypatch.setattr(
        config_module,
        "paths",
        replace(config_module.paths, connector_configs=tmp_path),
    )
    with pytest.raises(ConfigurationError):
        ConnectorConfigLoader().load(Platform.INSTAGRAM)
