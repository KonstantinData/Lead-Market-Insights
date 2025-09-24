from agents.trigger_detection_agent import TriggerDetectionAgent
from utils.text_normalization import normalize_text


def test_agent_normalises_triggers_and_summary() -> None:
    agent = TriggerDetectionAgent(trigger_words=["  KücHe  ", "KÜCHE"])
    assert agent.trigger_words == (normalize_text("Küche"),)
    assert agent.check({"summary": "Die KUCHE ist bereit"}) is True


def test_agent_falls_back_to_defaults_when_no_triggers() -> None:
    agent = TriggerDetectionAgent(trigger_words=[])
    assert agent.trigger_words
    assert agent.check({"summary": "This contains a Trigger Word"}) is True


def test_agent_handles_missing_summary() -> None:
    agent = TriggerDetectionAgent(trigger_words=["alert"])
    assert agent.check({}) is False
