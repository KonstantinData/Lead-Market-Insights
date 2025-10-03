from __future__ import annotations

from pathlib import Path
import textwrap

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
    validator = SoftTriggerValidator(
        synonyms=["hintergrundanalyse"], similarity_threshold=0.8
    )
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
    config_file.write_text(
        textwrap.dedent(
            """
            # comment

            termin mit kunde
            meeting mit kunden
            # another comment

            """
        ).strip(),
        encoding="utf-8",
    )

    phrases = load_synonym_phrases(config_file)

    assert phrases == ("termin mit kunde", "meeting mit kunden")


def test_load_synonym_phrases_missing_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing_file = tmp_path / "missing.txt"

    with caplog.at_level("WARNING"):
        phrases = load_synonym_phrases(missing_file)

    assert phrases == ()
    assert any("not found" in message for message in caplog.text.splitlines())


def test_validator_marks_invalid_candidate() -> None:
    validator = SoftTriggerValidator(synonyms=["kunden gespräch"])

    accepted, rejected = validator.validate(
        summary="",
        description="",
        matches=[{"soft_trigger": "", "source_field": "summary"}],
    )

    assert accepted == []
    assert rejected and rejected[0]["reject_reason"] == "invalid_candidate"


def test_validator_accepts_without_similarity_when_disabled() -> None:
    validator = SoftTriggerValidator(
        synonyms=[],
        require_evidence_substring=False,
        similarity_threshold=0.99,
    )

    candidate = {
        "soft_trigger": "Custom Phrase",
        "matched_hard_trigger": "placeholder",
        "source_field": "summary",
        "reason": "  extra spacing  ",
    }

    accepted, rejected = validator.validate(
        summary="Custom Phrase present", description="", matches=[candidate]
    )

    assert len(accepted) == 1
    assert accepted[0]["reason"] == "extra spacing"
    assert accepted[0]["validation"]["similarity"] == 1.0
    assert rejected == []


def test_validator_tfidf_similarity_path() -> None:
    validator = SoftTriggerValidator(
        synonyms=["kunden termin", "projekt kickoff"],
        similarity_method="tfidf",
        similarity_threshold=0.1,
    )

    candidate = {
        "soft_trigger": "Projekt Kickoff",
        "matched_hard_trigger": "meeting",
        "source_field": "summary",
    }

    accepted, rejected = validator.validate(
        summary="Projekt Kickoff besprochen", description="", matches=[candidate]
    )

    assert accepted and accepted[0]["validation"]["method"] == "tfidf"
    assert rejected == []


def test_validator_unknown_similarity_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    validator = SoftTriggerValidator(
        synonyms=["kunden termin"],
        similarity_method="unknown",
        similarity_threshold=0.5,
    )

    candidate = {
        "soft_trigger": "Kunden Termin",
        "matched_hard_trigger": "meeting",
        "source_field": "summary",
    }

    with caplog.at_level("DEBUG"):
        accepted, rejected = validator.validate(
            summary="Kunden Termin anberaumt", description="", matches=[candidate]
        )

    assert accepted
    assert rejected == []
    assert any(
        "falling back to Jaccard" in message for message in caplog.text.splitlines()
    )


def test_load_synonym_phrases_empty_file_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config_file = tmp_path / "synonyms.txt"
    config_file.write_text("\n\n", encoding="utf-8")

    with caplog.at_level("WARNING"):
        phrases = load_synonym_phrases(config_file)

    assert phrases == ()
    assert any("is empty" in message for message in caplog.text.splitlines())
