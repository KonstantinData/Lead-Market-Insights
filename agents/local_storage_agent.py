"""Local storage helper for persisting workflow artefacts on disk."""

from __future__ import annotations

import json
import logging
import os
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Optional


Metadata = Dict[str, object]


class LocalStorageAgent:
    """Persist generated artefacts in a structured local directory."""

    def __init__(
        self, base_dir: Path, *, logger: Optional[logging.Logger] = None
    ) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._index_file = self.base_dir / "index.json"
        self._failure_state_file = self.base_dir / "failure_state.json"

    def create_run_directory(self, run_id: str) -> Path:
        """Create (or return) the directory for a given run."""

        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug("Initialised run directory at %s", run_dir)
        return run_dir

    def get_audit_log_path(self, run_id: str) -> Path:
        """Return the filesystem path for the run's audit log."""

        run_dir = self.create_run_directory(run_id)
        return run_dir / "audit_log.jsonl"

    def load_audit_entries(self, run_id: str) -> list[Dict[str, object]]:
        """Load audit log entries for a run as structured dictionaries."""

        path = self.get_audit_log_path(run_id)
        if not path.exists():
            return []

        entries = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    self.logger.warning(
                        "Skipping invalid audit log line in %s: %s", path, line
                    )

        return entries

    def record_run(
        self,
        run_id: str,
        log_path: Path,
        *,
        metadata: Optional[Metadata] = None,
    ) -> None:
        """Append run metadata to the local index for quick discovery."""

        resolved_base = self.base_dir.resolve()
        resolved_log = Path(log_path).resolve()
        try:
            relative_log = resolved_log.relative_to(resolved_base)
            log_reference = relative_log.as_posix()
        except ValueError:
            log_reference = resolved_log.as_posix()

        entry: Metadata = {
            "run_id": run_id,
            "log_path": log_reference,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            entry.update(metadata)

        existing = []
        if self._index_file.exists():
            try:
                existing = json.loads(self._index_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.logger.warning(
                    "Index file %s was invalid JSON. Rebuilding from scratch.",
                    self._index_file,
                )
                existing = []

        # Replace previous entries for the same run_id to keep the index tidy.
        existing = [item for item in existing if item.get("run_id") != run_id]
        existing.append(entry)

        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.base_dir, delete=False
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(existing, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())

        try:
            temp_path.replace(self._index_file)
        except Exception:
            with suppress(FileNotFoundError):
                temp_path.unlink()
            raise

        self.logger.info("Recorded run %s in index with log %s", run_id, log_reference)

    # ------------------------------------------------------------------
    # Failure tracking helpers
    # ------------------------------------------------------------------
    def increment_failure_count(self, key: str) -> int:
        """Increment and persist the failure counter for *key*."""

        state = self._load_failure_state()
        new_value = int(state.get(key, 0)) + 1
        state[key] = new_value
        self._write_failure_state(state)
        return new_value

    def reset_failure_count(self, key: str) -> None:
        """Reset the stored failure counter for *key*."""

        state = self._load_failure_state()
        if key in state:
            del state[key]
            self._write_failure_state(state)

    def _load_failure_state(self) -> Dict[str, int]:
        if not self._failure_state_file.exists():
            return {}

        try:
            raw = json.loads(self._failure_state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.logger.warning(
                "Failure state file %s was invalid JSON. Resetting state.",
                self._failure_state_file,
            )
            return {}

        return {k: int(v) for k, v in raw.items()}

    def _write_failure_state(self, state: Dict[str, int]) -> None:
        self._failure_state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
