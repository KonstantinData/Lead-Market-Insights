from agents.trigger_detection_agent import TriggerDetectionAgent
from utils.text_normalization import normalize_text


def test_agent_normalises_triggers_and_summary() -> None:
    agent = TriggerDetectionAgent(trigger_words=["  KücHe  ", "KÜCHE"])
    assert agent.trigger_words == (normalize_text("Küche"),)

    result = agent.check({"summary": "Die KUCHE ist bereit"})
    assert result == {
        "trigger": True,
        "type": "hard",
        "matched_word": normalize_text("Küche"),
        "matched_field": "summary",
    }


def test_agent_detects_description_soft_trigger() -> None:
    agent = TriggerDetectionAgent(trigger_words=["briefing"])

    result = agent.check({"description": "Bitte bereite das Briefing vor."})
    assert result == {
        "trigger": True,
        "type": "soft",
        "matched_word": "briefing",
        "matched_field": "description",
    }


def test_agent_detects_trigger_within_longer_text() -> None:
    agent = TriggerDetectionAgent(trigger_words=["business client"])

    result = agent.check({"summary": "business client condata - v2"})
    assert result == {
        "trigger": True,
        "type": "hard",
        "matched_word": normalize_text("business client"),
        "matched_field": "summary",
    }


def test_agent_falls_back_to_defaults_when_no_triggers() -> None:
    agent = TriggerDetectionAgent(trigger_words=[])
    assert agent.trigger_words

    result = agent.check({"summary": "This contains a Trigger Word"})
    assert result["trigger"] is True
    assert result["type"] == "hard"
    assert result["matched_word"] == normalize_text("trigger word")
    assert result["matched_field"] == "summary"


def test_agent_handles_missing_fields() -> None:
    agent = TriggerDetectionAgent(trigger_words=["alert"])

    result = agent.check({})
    assert result == {
        "trigger": False,
        "type": None,
        "matched_word": None,
        "matched_field": None,
    }
