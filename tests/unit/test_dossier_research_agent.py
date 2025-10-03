"""Unit tests for the dossier research agent implementation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.dossier_research_agent import DossierResearchAgent


pytestmark = pytest.mark.asyncio


class _Config:
    def __init__(self, base: Path) -> None:
        self.research_artifact_dir = base


@pytest.fixture()
def agent(tmp_path: Path) -> DossierResearchAgent:
    return DossierResearchAgent(config=_Config(tmp_path))


@pytest.fixture()
def base_trigger() -> dict[str, object]:
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


@pytest.fixture()
def trigger_factory(base_trigger: dict[str, object]):
    def _factory(**updates: object) -> dict[str, object]:
        trigger = json.loads(json.dumps(base_trigger))
        trigger_payload = trigger["payload"]
        if isinstance(updates.get("payload"), dict):
            trigger_payload.update(updates["payload"])  # type: ignore[arg-type]
        for key, value in updates.items():
            if key != "payload":
                trigger[key] = value
        return trigger

    return _factory


async def test_run_serializes_output_and_persists_artifact(
    agent: DossierResearchAgent, trigger_factory
) -> None:
    trigger = trigger_factory()

    result = await agent.run(trigger)

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


@pytest.mark.parametrize(
    "insights_input,sources_input,expected_insights,expected_sources",
    [
        ("One liner", "https://example.com", ["One liner"], ["https://example.com"]),
        (
            ["Primary insight", None, 42],
            ["https://example.com", None],
            ["Primary insight", "42"],
            ["https://example.com"],
        ),
        (None, [], [], []),
    ],
)
async def test_sequences_are_normalised(
    agent: DossierResearchAgent,
    trigger_factory,
    insights_input,
    sources_input,
    expected_insights,
    expected_sources,
) -> None:
    trigger = trigger_factory(
        payload={"insights": insights_input, "sources": sources_input}
    )

    dossier = (await agent.run(trigger))["payload"]

    assert dossier["insights"] == expected_insights
    assert dossier["sources"] == expected_sources


async def test_summary_falls_back_to_description(
    agent: DossierResearchAgent, trigger_factory
) -> None:
    trigger = trigger_factory(
        payload={
            "summary": None,
            "company_summary": "",
            "company_description": None,
            "description": " Provided summary ",
        }
    )

    dossier = (await agent.run(trigger))["payload"]

    assert dossier["summary"] == "Provided summary"
    assert dossier["company"]["description"] == " Provided summary "


async def test_missing_required_fields_raise_value_error(
    agent: DossierResearchAgent, trigger_factory
) -> None:
    trigger = trigger_factory()
    trigger["payload"].pop("company_domain")  # type: ignore[index]

    with pytest.raises(ValueError):
        await agent.run(trigger)


async def test_artifacts_are_traceable_by_run_and_event(
    agent: DossierResearchAgent, trigger_factory
) -> None:
    trigger = trigger_factory()
    await agent.run(trigger)

    second_trigger = trigger_factory(
        event_id="evt-789",
        payload={"company_name": "Example Subsidiary"},
    )
    await agent.run(second_trigger)

    base_dir = Path(agent.output_dir) / trigger["run_id"]
    assert base_dir.parent == Path(agent.output_dir)
    artefacts = sorted(path.name for path in base_dir.glob("*.json"))
    assert artefacts == [
        "evt-456_company_detail_research.json",
        "evt-789_company_detail_research.json",
    ]


async def test_company_detail_schema_snapshot(
    agent: DossierResearchAgent, trigger_factory, monkeypatch
) -> None:
    class _FixedDatetime:
        @classmethod
        def now(cls, tz=None):
            base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
            if tz:
                return base.astimezone(tz)
            return base

    monkeypatch.setattr("agents.dossier_research_agent.datetime", _FixedDatetime)

    trigger = trigger_factory()
    result = await agent.run(trigger)

    artifact_path = Path(result["artifact_path"])
    saved_payload = json.loads(artifact_path.read_text(encoding="utf-8"))

    snapshot_path = (
        Path(__file__).resolve().parent / "snapshots" / "company_detail_research.json"
    )
    expected_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert saved_payload == expected_payload
    assert result["payload"] == expected_payload
