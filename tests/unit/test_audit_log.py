"""Unit tests for :mod:`utils.audit_log`."""

from __future__ import annotations

import json

from pathlib import Path

from utils.audit_log import AuditLog


def test_record_creates_jsonl_entry(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    audit_log = AuditLog(log_path)

    audit_id = audit_log.record(
        event_id="evt-1",
        request_type="dossier_confirmation",
        stage="request",
        responder="workflow",
        outcome="pending",
    )

    assert audit_id
    entries = audit_log.load_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["audit_id"] == audit_id
    assert entry["request_type"] == "dossier_confirmation"
    assert "payload" not in entry


def test_record_preserves_payload(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    audit_log = AuditLog(log_path)

    payload = {"note": "Manual override"}
    audit_id = audit_log.record(
        event_id=None,
        request_type="info_request",
        stage="response",
        responder="human",
        outcome="provided",
        payload=payload,
    )

    entries = audit_log.load_entries()
    assert entries[0]["audit_id"] == audit_id
    assert entries[0]["payload"] == payload


def test_iter_entries_skips_invalid_json(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    log_path.write_text(
        "{invalid}\n" + json.dumps({"audit_id": "a"}) + "\n", encoding="utf-8"
    )

    audit_log = AuditLog(log_path)
    entries = list(audit_log.iter_entries())

    assert entries == [{"audit_id": "a"}]


def test_iter_entries_no_file(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    audit_log = AuditLog(log_path)

    entries = list(audit_log.iter_entries())

    assert entries == []


def test_record_uses_provided_audit_id(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    audit_log = AuditLog(log_path)

    audit_log.record(
        event_id="evt-2",
        request_type="dossier_confirmation",
        stage="response",
        responder="human",
        outcome="approved",
        audit_id="existing",
    )

    entries = audit_log.load_entries()

    assert entries[0]["audit_id"] == "existing"
