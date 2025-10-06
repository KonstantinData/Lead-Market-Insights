import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from utils.persistence import ProcessedEventsState, atomic_write_json
from utils.validation import (
    InvalidExtractionError,
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
    assert normalize_domain(None) == ""


def test_validate_extraction_or_raise_normalises_inputs() -> None:
    payload = {"company_name": " Acme Corp ", "company_domain": "HTTPS://Acme.IO"}
    validated = validate_extraction_or_raise(payload)

    assert validated["company_name"] == "Acme Corp"
    assert validated["company_domain"] == "acme.io"
    assert validated["web_domain"] == "acme.io"

    with pytest.raises(InvalidExtractionError):
        validate_extraction_or_raise({"company_name": "Acme", "company_domain": "example.com"})


def test_normalize_similar_companies_handles_empty_results() -> None:
    empty_payload = normalize_similar_companies({"results": []})
    assert empty_payload["status"] == "no_candidates"
    assert empty_payload["result_count"] == 0

    populated = normalize_similar_companies({"results": [{"id": 1}]})
    assert populated["status"] == "completed"
    assert populated["result_count"] == 1


def test_finalize_dossier_sets_status_flags() -> None:
    insufficient = finalize_dossier({"summary": "", "sources": []})
    assert insufficient["status"] == "insufficient_context"

    complete = finalize_dossier({"summary": "Overview", "sources": ["https://acme.io"]})
    assert complete["status"] == "completed"


def test_atomic_write_json_validates_payload(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    payload = {"entries": {"evt": {"fingerprint": "abc", "updated": "2024-01-01"}}}

    atomic_write_json(path, payload, model=ProcessedEventsState)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["entries"]["evt"]["fingerprint"] == "abc"

    with pytest.raises(ValidationError):
        atomic_write_json(path, {"entries": {"evt": {}}}, model=ProcessedEventsState)
