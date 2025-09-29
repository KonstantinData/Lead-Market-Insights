import json
from pathlib import Path
from typing import Iterable, Mapping

import pytest

from agents.int_lvl_1_agent import IntLvl1SimilarCompaniesAgent


class _Config:
    def __init__(self, base: Path) -> None:
        self.research_artifact_dir = base


class _StubIntegration:
    def __init__(self, responses: Iterable[Mapping[str, object]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def list_similar_companies(
        self,
        company_name: str,
        *,
        limit: int,
        properties: Iterable[str],
    ) -> list[Mapping[str, object]]:
        self.calls.append(
            {
                "company_name": company_name,
                "limit": limit,
                "properties": list(properties),
            }
        )
        return list(self._responses)


def _candidate(
    company_id: str,
    name: str,
    *,
    segment: str | None = None,
    product: str | None = None,
    description: str | None = None,
    domain: str | None = None,
) -> Mapping[str, object]:
    properties: dict[str, object] = {"name": name}
    if domain:
        properties["domain"] = domain
    if segment:
        properties["segment"] = segment
    if product:
        properties["product"] = product
    if description:
        properties["description"] = description
    return {"id": company_id, "properties": properties}


def _base_trigger() -> dict[str, object]:
    return {
        "run_id": "run-123",
        "event_id": "evt-456",
        "payload": {
            "company_name": "Example Analytics",
            "segment": "Enterprise",
            "product": "Insight Platform",
            "description": "Delivers predictive analytics for marketing teams.",
        },
    }


@pytest.fixture()
def tmp_agent(tmp_path: Path) -> IntLvl1SimilarCompaniesAgent:
    integration = _StubIntegration(
        [
            _candidate(
                "1",
                "Example Analytics",
                segment="Enterprise",
                product="Insight Platform",
                description="Predictive analytics tools for marketing departments.",
                domain="example.com",
            ),
            _candidate(
                "2",
                "Example Insights",
                segment="Mid-Market",
                product="Insight Platform",
                description="Analytics for marketing and sales teams.",
                domain="insights.example",
            ),
            _candidate(
                "3",
                "Example Services",
                segment="Enterprise",
                product="Support Suite",
                description="Customer success tooling.",
                domain="services.example",
            ),
        ]
    )
    return IntLvl1SimilarCompaniesAgent(
        config=_Config(tmp_path),
        hubspot_integration=integration,
        result_limit=2,
    )


def test_ranked_results_are_limited_and_persisted(tmp_agent: IntLvl1SimilarCompaniesAgent, tmp_path: Path) -> None:
    trigger = _base_trigger()

    result = tmp_agent.run(trigger)

    payload = result["payload"]
    assert payload["company_name"] == "Example Analytics"
    assert payload["run_id"] == "run-123"
    assert payload["event_id"] == "evt-456"
    assert payload["artifact_path"] == str(tmp_path / "similar_companies_level1.json")

    ranked = payload["results"]
    assert len(ranked) == 2
    assert ranked[0]["id"] == "1"
    assert ranked[0]["matching_fields"] == ["description", "name", "product", "segment"]
    assert ranked[1]["id"] == "2"
    assert ranked[1]["matching_fields"] == ["description", "product"]

    artifact_path = Path(payload["artifact_path"])
    assert artifact_path.exists()
    saved = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert saved["results"] == ranked


def test_deterministic_ordering_when_scores_equal(tmp_path: Path) -> None:
    integration = _StubIntegration(
        [
            _candidate("a", "Beta Systems", description="Cloud services"),
            _candidate("b", "Alpha Labs", description="Cloud services"),
        ]
    )

    agent = IntLvl1SimilarCompaniesAgent(
        config=_Config(tmp_path),
        hubspot_integration=integration,
        result_limit=5,
    )

    trigger = {
        "payload": {
            "company_name": "Gamma Tech",
            "description": "Cloud services",
        }
    }

    results = agent.run(trigger)["payload"]["results"]
    assert [item["name"] for item in results] == ["Alpha Labs", "Beta Systems"]


def test_missing_company_name_raises_value_error(tmp_path: Path) -> None:
    integration = _StubIntegration([])
    agent = IntLvl1SimilarCompaniesAgent(
        config=_Config(tmp_path),
        hubspot_integration=integration,
    )

    with pytest.raises(ValueError):
        agent.run({"payload": {}})
