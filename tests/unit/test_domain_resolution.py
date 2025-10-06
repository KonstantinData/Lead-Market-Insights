"""Unit-Tests für ``utils.domain_resolution``."""

from __future__ import annotations

from pathlib import Path

from utils import domain_resolution as dr


def _reset_mapping_cache() -> None:
    """Cache des Mapping-Laders zwischen den Tests leeren."""

    dr.load_company_domain_mapping.cache_clear()


def test_resolve_company_domain_prefers_provided_domain() -> None:
    _reset_mapping_cache()
    domain, source = dr.resolve_company_domain({"company_domain": "HTTPS://Acme.io/"})

    assert domain == "acme.io"
    assert source == "provided"


def test_resolve_company_domain_uses_mapping(tmp_path: Path, monkeypatch) -> None:
    mapping_file = tmp_path / "company_domains.yaml"
    mapping_file.write_text("Acme Corp: acme.test\n", encoding="utf-8")

    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", mapping_file)
    _reset_mapping_cache()

    domain, source = dr.resolve_company_domain({"company_name": "Acme Corp"})

    assert domain == "acme.test"
    assert source == "mapping"


def test_resolve_company_domain_from_info_email(monkeypatch) -> None:
    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", Path("/dev/null"))
    _reset_mapping_cache()

    info = {"primary_email": "ceo@contoso.io"}
    domain, source = dr.resolve_company_domain(info)

    assert domain == "contoso.io"
    assert source == "info_email"


def test_resolve_company_domain_from_event_contacts(monkeypatch) -> None:
    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", Path("/dev/null"))
    _reset_mapping_cache()

    domain, source = dr.resolve_company_domain(
        info={},
        event={"organizer": {"email": "host@sample.ai"}, "attendees": ["guest@ignored.com"]},
    )

    assert domain == "sample.ai"
    assert source == "contact_email"


def test_resolve_company_domain_heuristic_fallback(monkeypatch) -> None:
    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", Path("/dev/null"))
    _reset_mapping_cache()

    domain, source = dr.resolve_company_domain({"company_name": "Blue Ocean"})

    assert domain == "blueocean.com"
    assert source == "heuristic"
