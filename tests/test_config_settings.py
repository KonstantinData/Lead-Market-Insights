"""Tests for configuration settings loading."""

import importlib
from pathlib import Path


def reload_settings():
    config_module = importlib.import_module("config.config")
    importlib.reload(config_module)
    return config_module.settings


def test_log_storage_dir_defaults(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    for key in [
        "LOG_STORAGE_DIR",
        "EVENT_LOG_DIR",
        "WORKFLOW_LOG_DIR",
        "RUN_LOG_DIR",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = reload_settings()

    expected = Path(__file__).resolve().parents[1] / "log_storage" / "run_history"
    assert settings.log_storage_dir == expected
    assert settings.event_log_dir == expected / "events"
    assert settings.workflow_log_dir == expected / "workflows"
    assert settings.run_log_dir == expected / "runs"


def test_log_storage_dir_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    target = tmp_path / "custom-root"
    monkeypatch.setenv("LOG_STORAGE_DIR", str(target))
    monkeypatch.setenv("EVENT_LOG_DIR", str(target / "events"))

    settings = reload_settings()

    assert settings.log_storage_dir == target.resolve()
    assert settings.event_log_dir == (target / "events").resolve()
