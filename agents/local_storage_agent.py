"""Local storage helper for persisting workflow artefacts on disk."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


Metadata = Dict[str, object]


class LocalStorageAgent:
    """Persist generated artefacts in a structured local directory."""

    def __init__(self, base_dir: Path, *, logger: Optional[logging.Logger] = None) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._index_file = self.base_dir / "index.json"

    def create_run_directory(self, run_id: str) -> Path:
        """Create (or return) the directory for a given run."""

        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug("Initialised run directory at %s", run_dir)
        return run_dir

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

        with self._index_file.open("w", encoding="utf-8") as handle:
            json.dump(existing, handle, ensure_ascii=False, indent=2)

        self.logger.info("Recorded run %s in index with log %s", run_id, log_reference)
