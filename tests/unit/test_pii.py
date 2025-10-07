from __future__ import annotations

from utils.pii import mask_pii


def test_mask_pii_forced_marker_propagates_into_nested_structures():
    payload = {
        "organizer": {
            "attendees": [
                {"phone": 1234567890, "name": "Alice"},
                {"email": "attendee@example.com"},
            ]
        }
    }

    masked = mask_pii(payload)

    attendees = masked["organizer"]["attendees"]
    assert attendees[0]["phone"] == "<redacted-phone>"
    assert attendees[0]["name"] == "<redacted-name>"
    assert attendees[1]["email"] == "<redacted-email>"


def test_mask_pii_strict_mode_redacts_numeric_fields():
    payload = {"details": {"account_number": 9876543210, "count": 42}}

    masked = mask_pii(payload, mode="strict")

    assert masked["details"]["account_number"] == "<redacted>"
    assert masked["details"]["count"] == "<redacted>"


def test_mask_pii_handles_sets_and_sequences():
    payload = {
        "metadata": {
            "contacts": {
                "emails": {"alice@example.com", "bob@example.com"},
                "tags": ["vip", "external"],
            }
        }
    }

    masked = mask_pii(payload)

    emails = masked["metadata"]["contacts"]["emails"]
    assert emails == {"<redacted-email>"}
    assert masked["metadata"]["contacts"]["tags"] == ["<redacted>", "<redacted>"]


def test_mask_pii_applies_category_marker_to_string_fields():
    payload = {"details": {"phone": "555-1234"}}

    masked = mask_pii(payload)

    assert masked["details"]["phone"] == "<redacted-phone>"


def test_mask_pii_forced_marker_applies_to_non_string_leaf():
    payload = {"organizer": {"attendees": 123456}}

    masked = mask_pii(payload)

    assert masked["organizer"]["attendees"] == "<redacted>"
