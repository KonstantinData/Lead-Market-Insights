import importlib

import pytest


def reload_modules():
    """Reload configuration and logging modules to pick up env changes."""

    config_module = importlib.import_module("config.config")
    importlib.reload(config_module)

    logs_module = importlib.import_module("logs")
    importlib.reload(logs_module)

    return logs_module


def test_get_event_log_manager_uses_env(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("POSTGRES_EVENT_LOG_TABLE", "custom_events")

    logs = reload_modules()

    class DummyManager:
        def __init__(self, dsn, *, table_name="event_logs"):
            self.dsn = dsn
            self.table_name = table_name

    monkeypatch.setattr(logs, "EventLogManager", DummyManager)

    manager = logs.get_event_log_manager()

    assert isinstance(manager, DummyManager)
    assert manager.dsn == "postgresql://user:pass@localhost/db"
    assert manager.table_name == "custom_events"


def test_get_event_log_manager_missing_dsn(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    logs = reload_modules()

    with pytest.raises(EnvironmentError):
        logs.get_event_log_manager()


def test_get_event_log_manager_prefers_argument(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://env/db")

    logs = reload_modules()

    class DummyManager:
        def __init__(self, dsn, *, table_name="event_logs"):
            self.dsn = dsn
            self.table_name = table_name

    monkeypatch.setattr(logs, "EventLogManager", DummyManager)

    manager = logs.get_event_log_manager(
        "postgresql://explicit/db", table_name="explicit_table"
    )

    assert manager.dsn == "postgresql://explicit/db"
    assert manager.table_name == "explicit_table"
