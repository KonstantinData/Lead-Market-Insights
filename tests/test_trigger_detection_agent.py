from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import pytest

from agents.trigger_detection_agent import TriggerDetectionAgent
from utils.text_normalization import normalize_text


pytestmark = pytest.mark.asyncio


async def test_agent_normalises_hard_triggers_and_detects_summary_match() -> None:
    agent = TriggerDetectionAgent(trigger_words=["  KücHe  ", "KÜCHE"])
    assert agent.hard_trigger_words == (normalize_text("Küche"),)

    result = await agent.check({"summary": "Die KUCHE ist bereit"})
    assert result["trigger"] is True
    assert result["type"] == "hard"
    assert result["matched_word"] == normalize_text("Küche")
    assert result["matched_field"] == "summary"
    assert result["soft_trigger_matches"] == []


async def test_agent_detects_hard_trigger_in_description() -> None:
    agent = TriggerDetectionAgent(trigger_words=["briefing"])

    result = await agent.check({"description": "Bitte bereite das Briefing vor."})
    assert result["trigger"] is True
    assert result["type"] == "hard"
    assert result["matched_word"] == "briefing"
    assert result["matched_field"] == "description"


async def test_agent_detects_soft_triggers_via_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    soft_match = {
        "soft_trigger": "Kick-off Termin",
        "matched_hard_trigger": "meeting preparation",
        "source_field": "summary",
        "reason": "Kick-off signalisiert eine Meeting Vorbereitung",
    }

    def _detector(
        summary: str, description: str, hard_triggers: Sequence[str]
    ) -> Iterable[Mapping[str, str]]:
        assert summary == "Kick-off mit neuem Kunden"
        assert description == ""
        assert "meeting preparation" in hard_triggers
        return [soft_match]

    agent = TriggerDetectionAgent(
        trigger_words=["meeting preparation"], soft_trigger_detector=_detector
    )

    result = await agent.check({"summary": "Kick-off mit neuem Kunden"})
    assert result["trigger"] is True
    assert result["type"] == "soft"
    assert result["matched_word"] == soft_match["soft_trigger"]
    assert result["matched_field"] == soft_match["source_field"]
    assert result["soft_trigger_matches"] == [soft_match]
    assert result["extraction_context"]["soft_trigger_matches"] == [soft_match]


async def test_agent_ignores_invalid_llm_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _detector(
        summary: str, description: str, hard_triggers: Sequence[str]
    ) -> Iterable[Mapping[str, str]]:
        return [
            {"soft_trigger": "", "matched_hard_trigger": "", "source_field": "other"},
            "invalid",  # type: ignore[list-item]
        ]

    agent = TriggerDetectionAgent(trigger_words=["meeting"], soft_trigger_detector=_detector)

    result = await agent.check({"summary": "Quarterly planning"})
    assert result == {
        "trigger": False,
        "type": None,
        "matched_word": None,
        "matched_field": None,
        "soft_trigger_matches": [],
        "hard_triggers": ["meeting"],
    }


async def test_agent_handles_missing_fields() -> None:
    agent = TriggerDetectionAgent(trigger_words=["alert"])

    result = await agent.check({})
    assert result == {
        "trigger": False,
        "type": None,
        "matched_word": None,
        "matched_field": None,
        "soft_trigger_matches": [],
        "hard_triggers": ["alert"],
    }
