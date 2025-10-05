"""Test configuration helpers and shared fixtures."""

from __future__ import annotations

import importlib
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable

import pytest

try:
    import pytest_asyncio
except ImportError:  # pragma: no cover - fallback for minimal environments

    class _PytestAsyncioModule:
        @staticmethod
        def fixture(*args, **kwargs):
            return pytest.fixture(*args, **kwargs)

    pytest_asyncio = _PytestAsyncioModule()  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STUBS = PROJECT_ROOT / "tests" / "stubs"
if STUBS.exists() and str(STUBS) not in sys.path:
    sys.path.insert(0, str(STUBS))


DEFAULT_TEST_GOOGLE_CALENDAR_ID = "test-calendar@example.com"
os.environ.setdefault("GOOGLE_CALENDAR_ID", DEFAULT_TEST_GOOGLE_CALENDAR_ID)


@pytest.fixture
def isolated_agent_registry(monkeypatch):
    """Provide an isolated registry for agent factory tests.

    The production registry is populated at import time by several modules. For
    deterministic tests we swap it out with an empty registry that is restored
    automatically once the test completes.
    """

    from agents import factory

    registry = defaultdict(dict)
    monkeypatch.setattr(factory, "_REGISTRY", registry)
    monkeypatch.setattr(factory, "_DEFAULTS", {})
    return registry


@pytest.fixture
def stub_agent_registry(isolated_agent_registry):
    """Register deterministic stub agents for integration tests."""

    from agents.factory import register_agent
    from agents.interfaces import (
        BaseCrmAgent,
        BaseExtractionAgent,
        BaseHumanAgent,
        BasePollingAgent,
        BaseResearchAgent,
        BaseTriggerAgent,
    )

    class StubPollingAgent(BasePollingAgent):
        def __init__(self, *, config=None):
            self.config = config

        async def poll(self) -> Iterable[Dict[str, object]]:
            return [
                {
                    "id": "evt-1",
                    "summary": "Test event",
                    "description": "Trigger phrase present",
                }
            ]

        async def poll_contacts(self) -> Iterable[Dict[str, object]]:
            return []

    class StubTriggerAgent(BaseTriggerAgent):
        def __init__(self, *, trigger_words=None):
            self.trigger_words = trigger_words or []

        async def check(self, event: Dict[str, object]) -> Dict[str, object]:
            return {
                "trigger": True,
                "type": "soft",
                "confidence": 0.95,
                "matched_word": "trigger",
                "matched_field": "description",
            }

    class StubExtractionAgent(BaseExtractionAgent):
        async def extract(self, event: Dict[str, object]) -> Dict[str, object]:
            return {
                "info": {
                    "company_name": "Example Co",
                    "web_domain": "example.ai",
                },
                "is_complete": True,
                "confidence": 0.9,
            }

    class StubHumanAgent(BaseHumanAgent):
        def __init__(self, *, communication_backend=None):
            self.communication_backend = communication_backend

        def request_info(
            self, event: Dict[str, object], extracted: Dict[str, object]
        ) -> Dict[str, object]:
            return {
                "info": extracted.get("info", {}),
                "is_complete": True,
                "audit_id": "audit-info",
            }

        def request_dossier_confirmation(
            self, event: Dict[str, object], info: Dict[str, object]
        ) -> Dict[str, object]:
            return {
                "approved": True,
                "audit_id": "audit-dossier",
            }

    class StubCrmAgent(BaseCrmAgent):
        def __init__(self):
            self.sent: list[Dict[str, object]] = []

        async def send(self, event: Dict[str, object], info: Dict[str, object]) -> None:
            self.sent.append({"event": event, "info": info})

    class StubInternalResearchAgent(BaseResearchAgent):
        def __init__(self, *, config: Any = None):
            self.config = config

        async def run(self, trigger: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "agent": "internal_research",
                "status": "REPORT_REQUIRED",
                "payload": {
                    "action": "REPORT_REQUIRED",
                    "existing_report": False,
                },
            }

    class StubDossierResearchAgent(BaseResearchAgent):
        def __init__(self, *, config: Any = None):
            self.config = config

        async def run(self, trigger: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "agent": "dossier_research",
                "status": "completed",
                "artifact_path": "stub/dossier.json",
                "payload": {},
            }

    class StubSimilarCompaniesAgent(BaseResearchAgent):
        def __init__(self, *, config: Any = None):
            self.config = config

        async def run(self, trigger: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "agent": "similar_companies_level1",
                "status": "completed",
                "payload": {"results": []},
            }

    register_agent(BasePollingAgent, "stub-polling", is_default=True)(StubPollingAgent)
    register_agent(BaseTriggerAgent, "stub-trigger", is_default=True)(StubTriggerAgent)
    register_agent(BaseExtractionAgent, "stub-extraction", is_default=True)(
        StubExtractionAgent
    )
    register_agent(BaseHumanAgent, "stub-human", is_default=True)(StubHumanAgent)
    register_agent(BaseCrmAgent, "stub-crm", is_default=True)(StubCrmAgent)
    register_agent(BaseResearchAgent, "internal_research", is_default=True)(
        StubInternalResearchAgent
    )
    register_agent(BaseResearchAgent, "dossier_research")(StubDossierResearchAgent)
    register_agent(BaseResearchAgent, "similar_companies_level1")(
        StubSimilarCompaniesAgent
    )

    return {
        "polling": StubPollingAgent,
        "trigger": StubTriggerAgent,
        "extraction": StubExtractionAgent,
        "human": StubHumanAgent,
        "crm": StubCrmAgent,
        "internal_research": StubInternalResearchAgent,
        "dossier_research": StubDossierResearchAgent,
        "similar_companies": StubSimilarCompaniesAgent,
    }


@pytest_asyncio.fixture
async def orchestrator_environment(monkeypatch, tmp_path):
    """Provide isolated settings directories for orchestrator-style tests."""

    run_dir = tmp_path / "runs"
    workflow_dir = tmp_path / "workflows"
    artifact_dir = tmp_path / "research" / "artifacts"
    pdf_dir = tmp_path / "research" / "pdfs"

    for directory in (run_dir, workflow_dir, artifact_dir, pdf_dir):
        directory.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("RUN_LOG_DIR", str(run_dir))
    monkeypatch.setenv("WORKFLOW_LOG_DIR", str(workflow_dir))
    monkeypatch.setenv("RESEARCH_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("RESEARCH_PDF_DIR", str(pdf_dir))

    import config.config as config_module
    import agents.master_workflow_agent as master_module
    import agents.workflow_orchestrator as orchestrator_module

    reloaded_config = importlib.reload(config_module)

    monkeypatch.setattr(
        master_module, "settings", reloaded_config.settings, raising=False
    )
    monkeypatch.setattr(
        orchestrator_module, "settings", reloaded_config.settings, raising=False
    )

    yield {
        "settings": reloaded_config.settings,
        "run_dir": run_dir,
        "workflow_dir": workflow_dir,
        "artifact_dir": artifact_dir,
        "pdf_dir": pdf_dir,
    }
