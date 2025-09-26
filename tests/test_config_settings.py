"""Tests for configuration settings loading."""

import importlib


def reload_settings():
    config_module = importlib.import_module("config.config")
    importlib.reload(config_module)
    return config_module.settings


def test_postgres_dsn_prefers_primary_env(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://primary/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://alias/db")

    settings = reload_settings()

    assert settings.postgres_dsn == "postgresql://primary/db"


def test_postgres_dsn_supports_alias(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://alias/db")

    settings = reload_settings()

    assert settings.postgres_dsn == "postgresql://alias/db"


def test_postgres_table_defaults(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.delenv("POSTGRES_EVENT_LOG_TABLE", raising=False)
    monkeypatch.delenv("POSTGRES_WORKFLOW_LOG_TABLE", raising=False)
    monkeypatch.delenv("POSTGRES_FILE_LOG_TABLE", raising=False)

    settings = reload_settings()

    assert settings.postgres_event_log_table == "event_logs"
    assert settings.postgres_workflow_log_table == "workflow_logs"
    assert settings.postgres_file_log_table == "workflow_log_files"
