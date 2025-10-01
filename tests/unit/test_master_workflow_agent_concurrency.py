import asyncio
from typing import Any, Dict, Optional

try:  # Python 3.11+
    from builtins import ExceptionGroup  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Python 3.10 fallback
    from types import ExceptionGroup  # type: ignore[attr-defined]

import pytest

from agents.master_workflow_agent import MasterWorkflowAgent


def _build_synthetic_agent() -> MasterWorkflowAgent:
    agent = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    agent.dossier_research_agent = object()
    agent.similar_companies_agent = object()
    agent._log_research_step = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    agent._can_run_dossier = lambda info: True  # type: ignore[attr-defined]
    agent._can_run_similar = lambda info: True  # type: ignore[attr-defined]
    return agent  # type: ignore[return-value]


def test_taskgroup_cancels_parallel_tasks_on_failure() -> None:
    agent = _build_synthetic_agent()

    cancelled: Dict[str, bool] = {"similar": False}

    async def fake_run(
        _agent: Optional[Any],
        agent_name: str,
        event_result: Dict[str, Any],
        event: Dict[str, Any],
        info: Dict[str, Any],
        event_id: Optional[Any],
        *,
        force: bool,
    ) -> None:
        if agent_name == "dossier_research":
            await asyncio.sleep(0.05)
            raise RuntimeError("boom")
        if agent_name == "similar_companies":
            try:
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                cancelled["similar"] = True
                raise

    agent._run_research_agent = fake_run  # type: ignore[assignment]

    event_result: Dict[str, Any] = {"research": {}}
    event: Dict[str, Any] = {"id": "evt-123"}
    info = {"company_name": "Example", "company_domain": "example.com"}

    with pytest.raises(ExceptionGroup) as exc_info:
        asyncio.run(
            agent._execute_precrm_research(  # type: ignore[attr-defined]
                event_result,
                event,
                info,
                event_id=event["id"],
                requires_dossier=True,
            )
        )

    assert any(isinstance(err, RuntimeError) for err in exc_info.value.exceptions)
    assert cancelled["similar"] is True
