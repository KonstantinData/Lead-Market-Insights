from __future__ import annotations

import logging
from typing import Dict, Set, Tuple, Optional

logger = logging.getLogger(__name__)


class WorkflowStepRecorder:
    """Idempotent recorder for workflow steps and run manifests.

    - Each (run_id, event_id, step) tuple is logged at most once.
    - Each run_id triggers at most one manifest write.
    """

    def __init__(self) -> None:
        self._seen_steps: Dict[Tuple[str, str], Set[str]] = {}
        self._manifests: Set[str] = set()

    def record_step(
        self,
        run_id: str,
        event_id: Optional[str],
        step: str,
        *,
        extra: Optional[dict] = None,
    ) -> bool:
        key = (run_id, event_id or "_no_event_")
        steps = self._seen_steps.setdefault(key, set())
        if step in steps:
            return False
        steps.add(step)
        if extra:
            logger.info(
                "Workflow log appended for run %s (step: %s) %s",
                run_id,
                step,
                extra,
            )
        else:
            logger.info("Workflow log appended for run %s (step: %s)", run_id, step)
        return True

    def should_write_manifest(self, run_id: str) -> bool:
        if run_id in self._manifests:
            return False
        self._manifests.add(run_id)
        return True

    def clear_run(self, run_id: str) -> None:
        to_drop = [k for k in self._seen_steps if k[0] == run_id]
        for k in to_drop:
            del self._seen_steps[k]
        self._manifests.discard(run_id)


workflow_step_recorder = WorkflowStepRecorder()
