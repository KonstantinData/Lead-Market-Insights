from human_in_the_loop.reply_parsers import (
    extract_run_id,
    parse_dossier_reply,
    parse_hitl_reply,
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


def test_extract_run_id_prefers_header() -> None:
    class Message:
        def __init__(self) -> None:
            self.headers = {"X-Run-ID": "run-123"}
            self.subject = "[run:ignored]"

    assert extract_run_id(Message()) == "run-123"


def test_extract_run_id_falls_back_to_subject() -> None:
    class Message:
        headers: dict[str, str] = {}
        subject = "HITL Update [run:run-xyz]"

    assert extract_run_id(Message()) == "run-xyz"


def test_parse_hitl_reply_detects_change_requests() -> None:
    decision, extra = parse_hitl_reply("Change: WEBSITE = example.com; NOTE=test")

    assert decision == "change_requested"
    assert extra == {"website": "example.com", "note": "test"}
