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
    monkeypatch.setenv("S3_BUCKET_NAME", "agentic-intelligence-research-logs")

    logs = reload_modules()

    class DummyManager:
        def __init__(self, bucket):
            self.bucket = bucket

    monkeypatch.setattr(logs, "EventLogManager", DummyManager)

    manager = logs.get_event_log_manager()

    assert isinstance(manager, DummyManager)
    assert manager.bucket == "agentic-intelligence-research-logs"


def test_get_event_log_manager_missing_bucket(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)

    logs = reload_modules()

    with pytest.raises(EnvironmentError):
        logs.get_event_log_manager()


def test_get_event_log_manager_prefers_argument(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "from-env")

    logs = reload_modules()

    class DummyManager:
        def __init__(self, bucket):
            self.bucket = bucket

    monkeypatch.setattr(logs, "EventLogManager", DummyManager)

    manager = logs.get_event_log_manager("explicit-bucket")

    assert manager.bucket == "explicit-bucket"
