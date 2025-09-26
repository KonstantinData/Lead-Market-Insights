"""Dynamic configuration watchers for updating LLM settings at runtime."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable, Iterable, Optional, Set

from dotenv import load_dotenv

from config.config import Settings

try:  # pragma: no cover - optional dependency handling
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - graceful degradation
    FileSystemEventHandler = object  # type: ignore
    Observer = None  # type: ignore

logger = logging.getLogger(__name__)


class _LlmEventHandler(FileSystemEventHandler):
    """Watchdog event handler that delegates to a callback."""

    def __init__(self, callback: Callable[[Path], None]) -> None:
        self._callback = callback

    def on_modified(self, event):  # type: ignore[override]
        if getattr(event, "is_directory", False):
            return
        self._callback(Path(event.src_path))

    def on_created(self, event):  # type: ignore[override]
        if getattr(event, "is_directory", False):
            return
        self._callback(Path(event.src_path))

    def on_moved(self, event):  # type: ignore[override]
        if getattr(event, "is_directory", False):
            return
        self._callback(Path(event.dest_path))


class LlmConfigurationWatcher:
    """Watch `.env` and agent configuration files for LLM related updates."""

    def __init__(
        self,
        settings: Settings,
        *,
        on_update: Optional[Callable[[Settings], None]] = None,
        extra_paths: Optional[Iterable[Path]] = None,
    ) -> None:
        self._settings = settings
        self._on_update = on_update

        files_to_watch: Set[Path] = set()
        if os.getenv("SETTINGS_SKIP_DOTENV") != "1":
            files_to_watch.add(Path(".env").resolve())
        if settings.agent_config_file:
            files_to_watch.add(settings.agent_config_file.resolve())
        if extra_paths:
            files_to_watch.update(Path(p).resolve() for p in extra_paths)

        self._candidate_files: Set[Path] = files_to_watch
        self._directories: Set[Path] = {
            path.parent for path in self._candidate_files if path.parent.exists()
        }

        self._observer: Optional[Observer] = None
        self._lock = threading.Lock()
        self._handler = _LlmEventHandler(self._handle_event)

    def start(self) -> bool:
        """Start watching for configuration changes (if watchdog is available)."""

        if Observer is None:
            logger.warning(
                "watchdog is not installed; dynamic LLM configuration updates are disabled."
            )
            return False

        if not self._directories:
            logger.debug("No configuration files found for LLM watcher; skipping start.")
            return False

        self._observer = Observer()
        for directory in self._directories:
            self._observer.schedule(self._handler, str(directory), recursive=False)
        self._observer.start()
        logger.debug(
            "Started LLM configuration watcher for %s",
            [str(path) for path in self._candidate_files],
        )
        return True

    def stop(self) -> None:
        """Stop the watcher if it is running."""

        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=2)
        self._observer = None

    def _handle_event(self, path: Path) -> None:
        resolved = path.resolve()
        if resolved not in self._candidate_files:
            return

        with self._lock:
            if os.getenv("SETTINGS_SKIP_DOTENV") != "1" and any(
                candidate.name == ".env" and resolved == candidate
                for candidate in self._candidate_files
            ):
                load_dotenv(override=True)

            try:
                self._settings.refresh_llm_configuration()
            except EnvironmentError as exc:
                logger.error("Failed to refresh LLM configuration: %s", exc)
                return

            logger.info("Reloaded LLM configuration from %s", path)
            if self._on_update:
                self._on_update(self._settings)

