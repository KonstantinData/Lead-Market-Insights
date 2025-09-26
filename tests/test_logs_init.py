import importlib


def reload_modules():
    """Reload configuration and logging modules to pick up env changes."""

    config_module = importlib.import_module("config.config")
    importlib.reload(config_module)

    logs_module = importlib.import_module("logs")
    importlib.reload(logs_module)

    return logs_module


def test_get_event_log_manager_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("LOG_STORAGE_DIR", str(storage_root))

    logs = reload_modules()
    manager = logs.get_event_log_manager()

    assert manager.base_path == storage_root.resolve() / "events"


def test_get_event_log_manager_prefers_argument(monkeypatch, tmp_path):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("LOG_STORAGE_DIR", str(tmp_path / "storage"))

    logs = reload_modules()

    custom_path = tmp_path / "custom-events"
    manager = logs.get_event_log_manager(custom_path)

    assert manager.base_path == custom_path.resolve()


def test_event_log_manager_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    logs_module = reload_modules()
    manager = logs_module.EventLogManager(tmp_path)

    manager.write_event_log("evt-1", {"status": "done"})
    stored = manager.read_event_log("evt-1")

    assert stored is not None
    assert stored["status"] == "done"
    assert "last_updated" in stored

    manager.delete_event_log("evt-1")
    assert manager.read_event_log("evt-1") is None
