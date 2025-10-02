"""Unit tests for the configuration hot reload watcher."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from config.watcher import LlmConfigurationWatcher, _LlmEventHandler


class DummySettings:
    def __init__(self, config_file: Path | None = None) -> None:
        self.agent_config_file = config_file
        self.refresh_calls: list[Path] = []

    def refresh_llm_configuration(self) -> None:
        self.refresh_calls.append(Path("refreshed"))


class DummyObserver:
    def __init__(self) -> None:
        self.scheduled: list[tuple[str, object, bool]] = []
        self.started = False
        self.stopped = False
        self.joined = False

    def schedule(self, handler, directory: str, recursive: bool = False) -> None:
        self.scheduled.append((directory, handler, recursive))

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def join(self, timeout: float | None = None) -> None:
        self.joined = True


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "agents.json"
    file_path.write_text("{}", encoding="utf-8")
    return file_path


def test_watcher_start_registers_directories(monkeypatch, config_file):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    dummy_settings = DummySettings(config_file)

    observer = DummyObserver()
    monkeypatch.setattr("config.watcher.Observer", lambda: observer)

    watcher = LlmConfigurationWatcher(dummy_settings)
    assert watcher.start() is True
    assert observer.started is True
    scheduled_dirs = {entry[0] for entry in observer.scheduled}
    assert config_file.parent.as_posix() in scheduled_dirs


def test_handle_event_refreshes_settings(monkeypatch, config_file):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    updates: list[DummySettings] = []
    dummy_settings = DummySettings(config_file)

    watcher = LlmConfigurationWatcher(dummy_settings, on_update=updates.append)
    watcher._handle_event(config_file)  # type: ignore[attr-defined]

    assert dummy_settings.refresh_calls
    assert updates == [dummy_settings]


def test_handle_event_ignores_unknown_files(monkeypatch, tmp_path):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    dummy_settings = DummySettings()

    watcher = LlmConfigurationWatcher(dummy_settings)
    watcher._handle_event(tmp_path / "untracked.json")  # type: ignore[attr-defined]

    assert dummy_settings.refresh_calls == []


def test_event_handler_filters_directory_events(tmp_path: Path):
    received: list[Path] = []

    handler = _LlmEventHandler(received.append)

    class DirEvent:
        is_directory = True
        src_path = tmp_path / "ignored"
        dest_path = tmp_path / "ignored"

    class FileEvent:
        is_directory = False
        src_path = tmp_path / "file.txt"
        dest_path = tmp_path / "renamed.txt"

    handler.on_modified(DirEvent())
    handler.on_created(FileEvent())
    handler.on_moved(FileEvent())

    assert received == [FileEvent.src_path, FileEvent.dest_path]


def test_watcher_tracks_extra_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    extra = tmp_path / "custom.env"
    extra.write_text("", encoding="utf-8")

    watcher = LlmConfigurationWatcher(DummySettings(), extra_paths=[extra])

    assert extra.resolve() in watcher._candidate_files  # type: ignore[attr-defined]


def test_watcher_start_warns_without_watchdog(monkeypatch, caplog, config_file):
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr("config.watcher.Observer", None)

    watcher = LlmConfigurationWatcher(DummySettings(config_file))

    assert watcher.start() is False
    assert "watchdog is not installed" in caplog.text


def test_watcher_start_skips_when_no_directories(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")

    class DummyObserverFactory:
        def __call__(self):  # pragma: no cover - should not be invoked
            raise AssertionError("Observer should not be constructed")

    monkeypatch.setattr("config.watcher.Observer", DummyObserverFactory())

    watcher = LlmConfigurationWatcher(DummySettings())

    assert watcher.start() is False
    assert "skipping start" in caplog.text


def test_handle_event_loads_dotenv(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("SETTINGS_SKIP_DOTENV", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=1", encoding="utf-8")
    load_calls: list[bool] = []

    monkeypatch.setattr("config.watcher.load_dotenv", lambda override=True: load_calls.append(override))

    watcher = LlmConfigurationWatcher(DummySettings(), extra_paths=[env_file])
    watcher._handle_event(env_file)  # type: ignore[attr-defined]

    assert load_calls == [True]


def test_handle_event_logs_refresh_errors(monkeypatch, caplog, config_file: Path):
    caplog.set_level(logging.ERROR)
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")

    class ErrorSettings(DummySettings):
        def refresh_llm_configuration(self) -> None:  # type: ignore[override]
            raise EnvironmentError("boom")

    watcher = LlmConfigurationWatcher(ErrorSettings(config_file))
    watcher._handle_event(config_file)  # type: ignore[attr-defined]

    assert "Failed to refresh LLM configuration" in caplog.text
