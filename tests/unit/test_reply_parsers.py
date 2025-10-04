from human_in_the_loop.reply_parsers import (
    parse_dossier_reply,
    parse_missing_info_reply,
)


def test_parse_missing_info_extracts_key_value_pairs() -> None:
    subject = "Re: Details"
    body = "Company Domain: example.com\nPhone: 123-456\nNo colon line"

    result = parse_missing_info_reply(subject, body)

    assert result["outcome"] == "parsed"
    assert result["fields"] == {"company_domain": "example.com", "phone": "123-456"}


def test_parse_dossier_reply_detects_decision() -> None:
    subject = "Approved"
    body = "Yes, proceed"

    result = parse_dossier_reply(subject, body)

    assert result["decision"] == "approved"
    assert result["outcome"] == "approved"


def test_parse_dossier_reply_handles_decline() -> None:
    subject = "Re: Dossier"
    body = "We must decline"

    result = parse_dossier_reply(subject, body)

    assert result["decision"] == "declined"
    assert result["outcome"] == "declined"
