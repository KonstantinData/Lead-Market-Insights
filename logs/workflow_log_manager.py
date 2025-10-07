import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional

from utils.datetime_formatting import now_cet_timestamp

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


def _sanitise(identifier: str) -> str:
    cleaned = _SAFE_NAME.sub("_", identifier)
    cleaned = cleaned.strip("._")
    return cleaned or "workflow"


class WorkflowLogManager:
    """Logging for complete workflows stored as JSON lines locally."""

    def __init__(
        self,
        base_path: Path,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def _log_file(self, run_id: str) -> Path:
        return self.base_path / f"{_sanitise(run_id)}.jsonl"

    def append_log(
        self,
        run_id: str,
        step: str,
        message: str,
        event_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Append a log entry to the workflow log."""

        entry: Dict[str, Optional[str]] = {
            "timestamp": now_cet_timestamp(),
            "run_id": run_id,
            "step": step,
            "message": message,
            "event_id": event_id,
            "error": error,
        }

        log_file = self._log_file(run_id)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        if self.logger:
            self.logger.info(
                "Workflow log appended for run %s (step: %s)", run_id, step
            )


# Example:
# wlm = WorkflowLogManager(Path("log_storage/run_history/workflows"))
# wlm.append_log("run42", "start", "Workflow started", event_id="evt123")
