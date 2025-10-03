from __future__ import annotations

from pathlib import Path

import pytest

from agents.soft_trigger_validator import SoftTriggerValidator, load_synonym_phrases


def test_validator_accepts_with_evidence_and_similarity() -> None:
    validator = SoftTriggerValidator(synonyms=["kundengespräch"])
    summary = "Strategisches Kundengespräch mit ACME"
    candidate = {
        "soft_trigger": "Kundengespräch",
        "matched_hard_trigger": "kunden meeting",
        "source_field": "summary",
        "reason": "Synonym",
    }

    accepted, rejected = validator.validate(
        summary=summary,
        description="",
        matches=[candidate],
    )

    assert len(accepted) == 1
    assert accepted[0]["validation"]["similarity"] >= validator.similarity_threshold
    assert rejected == []


def test_validator_rejects_without_evidence() -> None:
    validator = SoftTriggerValidator(synonyms=["kundengespräch"])
    candidate = {
        "soft_trigger": "Kundengespräch",
        "matched_hard_trigger": "kunden meeting",
        "source_field": "summary",
    }

    accepted, rejected = validator.validate(
        summary="Planungsgespräch ohne Kundenbezug",
        description="",
        matches=[candidate],
    )

    assert accepted == []
    assert rejected and rejected[0]["reject_reason"] == "no_evidence"


def test_validator_rejects_low_similarity() -> None:
    validator = SoftTriggerValidator(synonyms=["hintergrundanalyse"], similarity_threshold=0.8)
    summary = "Statusupdate zur Projektplanung"
    candidate = {
        "soft_trigger": "Statusupdate",
        "matched_hard_trigger": "meeting",
        "source_field": "summary",
    }

    accepted, rejected = validator.validate(
        summary=summary,
        description="",
        matches=[candidate],
    )

    assert accepted == []
    assert rejected and rejected[0]["reject_reason"] == "low_similarity"


def test_validator_accepts_fuzzy_evidence() -> None:
    validator = SoftTriggerValidator(
        synonyms=["kickoff meeting"],
        fuzzy_evidence_threshold=0.5,
    )
    summary = "Kick-off Meeting mit dem Team"
    candidate = {
        "soft_trigger": "Kickoff Meeting",
        "matched_hard_trigger": "meeting",
        "source_field": "summary",
    }

    accepted, rejected = validator.validate(
        summary=summary,
        description="",
        matches=[candidate],
    )

    assert len(accepted) == 1
    assert accepted[0]["validation"]["evidence"] == "fuzzy"
    assert rejected == []


def test_load_synonym_phrases_ignores_comments(tmp_path: Path) -> None:
    config_file = tmp_path / "synonyms.txt"
    config_file.write_text("""
# comment

termin mit kunde
 meeting mit kunden  
# another comment

""".strip(), encoding="utf-8")

    phrases = load_synonym_phrases(config_file)

    assert phrases == ("termin mit kunde", "meeting mit kunden")


def test_load_synonym_phrases_missing_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    missing_file = tmp_path / "missing.txt"

    with caplog.at_level("WARNING"):
        phrases = load_synonym_phrases(missing_file)

    assert phrases == ()
    assert any("not found" in message for message in caplog.text.splitlines())
