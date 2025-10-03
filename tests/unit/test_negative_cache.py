from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from utils.negative_cache import NegativeEventCache


def _set_time(monkeypatch: pytest.MonkeyPatch, value: float) -> None:
    monkeypatch.setattr("utils.negative_cache.time.time", lambda: value)


def _make_event(summary: str = "Kick-off", description: str = "") -> dict[str, str]:
    return {"id": "evt-1", "summary": summary, "description": description}


def test_should_skip_returns_true_when_fingerprint_and_rule_hash_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    cache = NegativeEventCache.load(cache_path, rule_hash="hash", now=0)
    event = _make_event()
    _set_time(monkeypatch, 100.0)
    cache.record_no_trigger(event, "hash", "no_trigger")

    assert cache.should_skip(event, "hash") is True


def test_should_skip_false_when_rule_hash_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    cache = NegativeEventCache.load(cache_path, rule_hash="hash", now=0)
    event = _make_event()
    _set_time(monkeypatch, 50.0)
    cache.record_no_trigger(event, "hash", "no_trigger")

    assert cache.should_skip(event, "other") is False


def test_should_skip_false_when_fingerprint_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    cache = NegativeEventCache.load(cache_path, rule_hash="hash", now=0)
    event = _make_event()
    _set_time(monkeypatch, 10.0)
    cache.record_no_trigger(event, "hash", "no_trigger")

    changed = _make_event(summary="Updated")
    assert cache.should_skip(changed, "hash") is False


def test_record_and_forget_removes_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    cache = NegativeEventCache.load(cache_path, rule_hash="hash", now=0)
    event = _make_event()
    _set_time(monkeypatch, 20.0)
    cache.record_no_trigger(event, "hash", "no_trigger")

    cache.forget("evt-1")
    assert cache.should_skip(event, "hash") is False


def test_purge_stale_removes_old_entries(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    raw = {
        "version": 1,
        "entries": {
            "evt-old": {
                "fingerprint": "abc",
                "updated": "2000-01-01T00:00:00Z",
                "rule_hash": "hash",
                "decision": "no_trigger",
                "first_seen": 0,
                "last_seen": 0,
                "classification_version": "v1",
            },
            "evt-last-seen": {
                "fingerprint": "def",
                "updated": None,
                "rule_hash": "hash",
                "decision": "no_trigger",
                "first_seen": 0,
                "last_seen": 0,
                "classification_version": "v1",
            },
        },
    }
    cache_path.write_text(json.dumps(raw), encoding="utf-8")

    reference_now = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    cache = NegativeEventCache.load(
        cache_path, rule_hash="hash", now=reference_now
    )

    assert cache.entries == {}


def test_cache_persists_and_reloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    event = _make_event()

    cache = NegativeEventCache.load(cache_path, rule_hash="hash", now=0)
    _set_time(monkeypatch, 30.0)
    cache.record_no_trigger(event, "hash", "no_trigger")
    cache.flush()

    reloaded = NegativeEventCache.load(cache_path, rule_hash="hash", now=35.0)
    assert reloaded.should_skip(event, "hash") is True
