from typing import Optional

import pytest

from polling.inbox_agent import (
    parse_dossier_decision,
    parse_missing_info_key_values,
)


@pytest.mark.parametrize(
    "body,expected",
    [
        ("\n\nYes, approved", "approved"),
        ("Ok!", "approved"),
        ("JA bitte", "approved"),
        ("Nein, leider nicht", "declined"),
        ("We must decline this", "declined"),
        ("", None),
        ("Maybe later", None),
    ],
)
def test_parse_dossier_decision_variants(body: str, expected: Optional[str]) -> None:
    assert parse_dossier_decision(body) == expected


def test_parse_missing_info_key_values_filters_whitelist() -> None:
    body = (
        "Company Name: Acme Corp\n"
        "Web Domain: acme.com\n"
        "Phone: 123-456\n"
        "Company-Domain: example.org"
    )

    result = parse_missing_info_key_values(body)

    assert result == {"company_name": "Acme Corp", "web_domain": "example.org"}


def test_parse_missing_info_key_values_ignores_empty_values() -> None:
    body = "Company Name:  \nWeb Domain:   "

    result = parse_missing_info_key_values(body)

    assert result == {}
