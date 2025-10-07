"""Unit-Tests für ``utils.domain_resolution``."""

from __future__ import annotations

from pathlib import Path

from utils import domain_resolution as dr


def _reset_mapping_cache() -> None:
    """Cache des Mapping-Laders zwischen den Tests leeren."""

    dr.load_company_domain_mapping.cache_clear()


def test_resolve_company_domain_prefers_provided_domain() -> None:
    _reset_mapping_cache()
    domain, source = dr.resolve_company_domain(
        {"company_domain": "HTTPS://Acme.io/"},
        event={"summary": "Acme planning sync (https://acme.io)"},
    )

    assert domain == "acme.io"
    assert source == "provided"


def test_resolve_company_domain_uses_mapping(tmp_path: Path, monkeypatch) -> None:
    mapping_file = tmp_path / "company_domains.yaml"
    mapping_file.write_text("Acme Corp: acme.test\n", encoding="utf-8")

    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", mapping_file)
    _reset_mapping_cache()

    domain, source = dr.resolve_company_domain(
        {"company_name": "Acme Corp"},
        event={"description": "Agenda: deep dive at https://acme.test/platform"},
    )

    assert domain == "acme.test"
    assert source == "mapping"


def test_resolve_company_domain_from_info_email(monkeypatch) -> None:
    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", Path("/dev/null"))
    _reset_mapping_cache()

    info = {"primary_email": "ceo@contoso.io"}
    domain, source = dr.resolve_company_domain(
        info, event={"summary": "Strategy review with contoso.io leadership"}
    )

    assert domain == "contoso.io"
    assert source == "info_email"


def test_resolve_company_domain_from_event_contacts(monkeypatch) -> None:
    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", Path("/dev/null"))
    _reset_mapping_cache()

    domain, source = dr.resolve_company_domain(
        info={},
        event={
            "summary": "Kick-off with ACSYS Lastertechnik",
            "organizer": {"email": "host@sample.ai"},
            "attendees": ["guest@ignored.com"],
        },
    )

    assert domain is None
    assert source is None


def test_resolve_company_domain_heuristic_fallback(monkeypatch) -> None:
    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", Path("/dev/null"))
    _reset_mapping_cache()

    domain, source = dr.resolve_company_domain(
        {"company_name": "Blue Ocean"},
        event={"description": "Exploration call - see blueocean.com for deck"},
    )

    assert domain == "blueocean.com"
    assert source == "heuristic"


def test_resolve_company_domain_rejects_domain_missing_from_event_text() -> None:
    _reset_mapping_cache()

    domain, source = dr.resolve_company_domain(
        {"company_domain": "hidden.example"},
        event={"summary": "Sync with Hidden Example"},
    )

    assert domain is None
    assert source is None


def test_domain_in_event_text_accepts_non_mapping_event() -> None:
    """Non-Mapping ``event`` objects should default to allowing the domain."""

    assert dr._domain_in_event_text("example.com", event="raw string") is True


def test_domain_in_event_text_rejects_missing_domain() -> None:
    """A fehlender Domain-String muss strikt als nicht vorhanden gelten."""

    assert dr._domain_in_event_text(None, event={}) is False


def test_domain_in_event_text_handles_www_prefixes() -> None:
    """Ensure both present and missing ``www`` prefixes are considered."""

    event = {"summary": "Deep dive on https://example.com product"}
    assert dr._domain_in_event_text("www.example.com", event) is True

    absent_event = {"summary": "Kick-off without relevant URLs"}
    assert dr._domain_in_event_text("www.missing.io", absent_event) is False

    assert dr._domain_in_event_text("missing.io", {"description": "Visit www.missing.io"})


def test_domain_in_event_text_requires_text_segments() -> None:
    """Wenn keine beschreibenden Felder vorhanden sind, darf kein Treffer erfolgen."""

    assert dr._domain_in_event_text("example.com", {"location": "HQ"}) is False


def test_load_company_domain_mapping_without_yaml(monkeypatch) -> None:
    """When PyYAML is unavailable an empty mapping should be returned."""

    monkeypatch.setattr(dr, "yaml", None)
    _reset_mapping_cache()

    assert dr.load_company_domain_mapping(Path("/dev/null")) == {}


def test_load_company_domain_mapping_handles_errors(tmp_path: Path, monkeypatch) -> None:
    """Ein Lese- oder Parsefehler muss still auf ein leeres Mapping zurückfallen."""

    mapping_file = tmp_path / "companies.yaml"
    mapping_file.write_text("{}", encoding="utf-8")

    class _BadYaml:
        @staticmethod
        def safe_load(*_args: object, **_kwargs: object) -> dict[str, str]:  # pragma: no cover - shim
            raise RuntimeError("boom")

    monkeypatch.setattr(dr, "yaml", _BadYaml)
    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", mapping_file)
    _reset_mapping_cache()

    assert dr.load_company_domain_mapping() == {}


def test_load_company_domain_mapping_skips_non_strings(tmp_path: Path, monkeypatch) -> None:
    """Nicht-String-Einträge werden bei der Normalisierung verworfen."""

    mapping_file = tmp_path / "companies.yaml"
    mapping_file.write_text("invalid: 123\n", encoding="utf-8")

    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", mapping_file)
    _reset_mapping_cache()

    assert dr.load_company_domain_mapping() == {}


def test_extract_email_domain_skips_generic_providers() -> None:
    """Generic webmail domains must not be treated as company domains."""

    assert dr._extract_email_domain("user@gmail.com") is None


def test_extract_email_domain_non_string_inputs() -> None:
    """Nicht-String-Werte oder Domains ohne TLD dürfen nicht akzeptiert werden."""

    assert dr._extract_email_domain(42) is None
    assert dr._extract_email_domain("user@localhost") is None


def test_resolve_from_mapping_ignores_blank_name(monkeypatch) -> None:
    """Leere Unternehmensnamen können nicht im Mapping aufgelöst werden."""

    monkeypatch.setattr(dr, "_DEFAULT_MAPPING_PATH", Path("/dev/null"))
    _reset_mapping_cache()

    assert dr._resolve_from_mapping("   ") == (None, None)


def test_resolve_from_name_rejects_numeric_and_invalid_candidates(monkeypatch) -> None:
    """Numerische Namen oder ungültige Heuristiken liefern kein Ergebnis."""

    assert dr._resolve_from_name("12345") == (None, None)

    monkeypatch.setattr(dr, "is_valid_business_domain", lambda _domain: False)
    assert dr._resolve_from_name("Example") == (None, None)
