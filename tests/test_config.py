from backend.core.config import Settings, get_settings


def test_config_loads_yaml_defaults() -> None:
    settings = get_settings()

    assert settings.app_name == "EMY Private AI OS"
    assert settings.environment == "local"
    assert settings.version == "0.1.0"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000


def test_environment_overrides_yaml(monkeypatch) -> None:
    monkeypatch.setenv("EMY_PORT", "8123")

    assert Settings().port == 8123
