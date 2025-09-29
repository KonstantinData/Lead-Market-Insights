"""Unit tests for the dossier research agent implementation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.dossier_research_agent import DossierResearchAgent


class _Config:
    def __init__(self, base: Path) -> None:
        self.research_artifact_dir = base


@pytest.fixture()
def agent(tmp_path: Path) -> DossierResearchAgent:
    return DossierResearchAgent(config=_Config(tmp_path))


def _base_trigger() -> dict[str, object]:
    return {
        "run_id": "run-123",
        "event_id": "evt-456",
        "payload": {
            "company_name": "Example Corp",
            "company_domain": "example.com",
            "company_location": "New York, USA",
            "company_industry": "Technology",
            "company_description": "A sample organisation for testing purposes.",
            "summary": "Example Corp builds example solutions.",
            "insights": [
                "Revenue grew 25% year over year.",
                "Expanded into two new markets in 2023.",
            ],
            "sources": [
                "https://example.com/press",
                "https://news.example.com/article",
            ],
        },
    }


def test_run_serializes_output_and_persists_artifact(agent: DossierResearchAgent) -> None:
    trigger = _base_trigger()

    result = agent.run(trigger)

    dossier = result["payload"]
    assert list(dossier.keys()) == list(DossierResearchAgent.OUTPUT_FIELD_ORDER)
    assert dossier["report_type"] == "Company Detail Research"
    assert dossier["run_id"] == trigger["run_id"]
    assert dossier["event_id"] == trigger["event_id"]
    assert list(dossier["company"].keys()) == list(
        DossierResearchAgent.COMPANY_FIELD_ORDER
    )

    artifact_path = Path(result["artifact_path"])
    assert artifact_path.exists()
    expected_dir = Path(agent.output_dir) / trigger["run_id"]
    assert artifact_path.parent == expected_dir
    saved_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert list(saved_payload.keys()) == list(DossierResearchAgent.OUTPUT_FIELD_ORDER)


def test_missing_required_fields_raise_value_error(agent: DossierResearchAgent) -> None:
    trigger = _base_trigger()
    trigger["payload"].pop("company_domain")  # type: ignore[index]

    with pytest.raises(ValueError):
        agent.run(trigger)


def test_artifacts_are_traceable_by_run_and_event(agent: DossierResearchAgent) -> None:
    trigger = _base_trigger()
    agent.run(trigger)

    second_trigger = _base_trigger()
    second_trigger["event_id"] = "evt-789"
    second_trigger["payload"]["company_name"] = "Example Subsidiary"  # type: ignore[index]
    agent.run(second_trigger)

    base_dir = Path(agent.output_dir) / trigger["run_id"]
    assert base_dir.parent == Path(agent.output_dir)
    artefacts = sorted(path.name for path in base_dir.glob("*.json"))
    assert artefacts == [
        "evt-456_company_detail_research.json",
        "evt-789_company_detail_research.json",
    ]
