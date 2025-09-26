"""Unit tests for the configuration hot reload watcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.watcher import LlmConfigurationWatcher


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
