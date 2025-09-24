import importlib

import pytest


@pytest.fixture(autouse=True)
def reload_logs_module(monkeypatch):
    """Ensure a clean logs module for each test."""
    # Reload the module to reset any previous monkeypatches or state.
    import logs

    yield

    importlib.reload(logs)


def test_get_event_log_manager_uses_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "agentic-intelligence-research-logs")

    import logs

    class DummyManager:
        def __init__(self, bucket):
            self.bucket = bucket

    monkeypatch.setattr(logs, "EventLogManager", DummyManager)

    manager = logs.get_event_log_manager()

    assert isinstance(manager, DummyManager)
    assert manager.bucket == "agentic-intelligence-research-logs"


def test_get_event_log_manager_missing_bucket(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)

    import logs

    with pytest.raises(EnvironmentError):
        logs.get_event_log_manager()


def test_get_event_log_manager_prefers_argument(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "from-env")

    import logs

    class DummyManager:
        def __init__(self, bucket):
            self.bucket = bucket

    monkeypatch.setattr(logs, "EventLogManager", DummyManager)

    manager = logs.get_event_log_manager("explicit-bucket")

    assert manager.bucket == "explicit-bucket"
