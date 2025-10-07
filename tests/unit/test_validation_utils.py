from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from utils.persistence import ProcessedEventsState, atomic_write_json
from utils.validation import (
    InvalidExtractionError,
    _extract_domain_keyword,
    finalize_dossier,
    is_valid_business_domain,
    normalize_domain,
    normalize_similar_companies,
    validate_extraction_or_raise,
)


def test_is_valid_business_domain_filters_placeholders() -> None:
    assert is_valid_business_domain("acme.io")
    assert not is_valid_business_domain("example.com")
    assert not is_valid_business_domain("localhost")
    assert not is_valid_business_domain("invalid")
    assert not is_valid_business_domain("printer.local")


def test_normalize_domain_strips_protocol_and_slashes() -> None:
    assert normalize_domain("HTTPS://Example.com/") == "example.com"
    assert normalize_domain("example.org///") == "example.org"
    assert normalize_domain(None) == ""


def test_validate_extraction_or_raise_normalises_inputs() -> None:
    payload = {"company_name": " Acme Corp ", "company_domain": "HTTPS://Acme.IO"}
    validated = validate_extraction_or_raise(payload)

    assert validated["company_name"] == "Acme Corp"
    assert validated["company_domain"] == "acme.io"
    assert validated["web_domain"] == "acme.io"

    with pytest.raises(InvalidExtractionError):
        validate_extraction_or_raise({"company_name": "Acme", "company_domain": "example.com"})


def test_validate_extraction_or_raise_requires_core_fields() -> None:
    with pytest.raises(InvalidExtractionError, match="company_name missing"):
        validate_extraction_or_raise({"company_domain": "acme.io"})

    with pytest.raises(InvalidExtractionError, match="company_domain missing"):
        validate_extraction_or_raise({"company_name": "Acme"})

    with pytest.raises(InvalidExtractionError, match="invalid web_domain"):
        validate_extraction_or_raise({"company_name": "Acme", "company_domain": "invalid"})


def test_validate_extraction_or_raise_normalises_salutations() -> None:
    validated = validate_extraction_or_raise(
        {
            "company_name": "Herr Milonas Firma Condata",
            "company_domain": "condata.io",
        }
    )

    assert validated["company_name"] == "Milonas Firma Condata"

    # Allow legitimate companies that coincidentally start with "Herr" but include a suffix.
    validated_suffix = validate_extraction_or_raise(
        {"company_name": "Herr GmbH", "company_domain": "herr-gmbh.de"}
    )
    assert validated_suffix["company_name"] == "Herr GmbH"


@pytest.mark.parametrize(
    "name, expected_valid, expected_normalised",
    [
        ("Firma Condata", True, "Condata"),
        ("Herr GmbH", True, "Herr GmbH"),
        ("HERR Industrie GmbH", True, "HERR Industrie GmbH"),
        ("Frau Müller Consulting", False, None),
        ("Herr AG", True, "Herr AG"),
        ("Mr. Smith LLC", True, "Mr. Smith LLC"),
        ("Herr Milonas Condata", True, "Milonas Condata"),
    ],
)
def test_validate_extraction_or_raise_salutation_matrix(
    name: str, expected_valid: bool, expected_normalised: str | None
) -> None:
    payload = {"company_name": name, "company_domain": "condata.io"}

    if expected_valid:
        validated = validate_extraction_or_raise(payload)
        assert validated["company_name"] == expected_normalised
    else:
        with pytest.raises(InvalidExtractionError):
            validate_extraction_or_raise(payload)


def test_normalize_similar_companies_handles_empty_results() -> None:
    empty_payload = normalize_similar_companies({"results": []})
    assert empty_payload["status"] == "no_candidates"
    assert empty_payload["result_count"] == 0

    populated = normalize_similar_companies({"results": [{"id": 1}]})
    assert populated["status"] == "completed"
    assert populated["result_count"] == 1

    preserved_status = normalize_similar_companies(
        {"results": [{"id": 2}], "status": "in_progress"}
    )
    assert preserved_status["status"] == "in_progress"


def test_extract_domain_keyword_ignores_www_labels() -> None:
    assert _extract_domain_keyword("www.") == ""
    assert _extract_domain_keyword("www.acme.test") == "acme"


def test_finalize_dossier_sets_status_flags() -> None:
    insufficient = finalize_dossier({"summary": "", "sources": []})
    assert insufficient["status"] == "insufficient_context"

    complete = finalize_dossier({"summary": "Overview", "sources": ["https://acme.io"]})
    assert complete["status"] == "completed"

    preserved = finalize_dossier(
        {"summary": "Overview", "status": "pending", "sources": ["https://acme.io"]}
    )
    assert preserved["status"] == "pending"


def test_atomic_write_json_validates_payload(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    payload = {"entries": {"evt": {"fingerprint": "abc", "updated": "2024-01-01"}}}

    atomic_write_json(path, payload, model=ProcessedEventsState)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["entries"]["evt"]["fingerprint"] == "abc"

    with pytest.raises(ValidationError):
        atomic_write_json(path, {"entries": {"evt": {}}}, model=ProcessedEventsState)
