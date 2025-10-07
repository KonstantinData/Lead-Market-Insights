from datetime import datetime
from types import SimpleNamespace

from utils.datetime_formatting import format_cet_timestamp, format_report_datetime, now_cet_timestamp


def test_format_report_datetime_with_iso_string():
    value = "2024-03-05T15:30:00+01:00"
    assert format_report_datetime(value) == "05.03.2024 15:30 CET"


def test_format_report_datetime_with_naive_datetime():
    naive_value = datetime(2024, 7, 1, 8, 15, 0)
    assert format_report_datetime(naive_value) == "01.07.2024 10:15 CET"


def test_format_report_datetime_with_unparseable_input():
    sentinel = object()
    assert format_report_datetime(sentinel) == str(sentinel)


def test_format_cet_timestamp_with_epoch_seconds():
    timestamp = 1_700_000_000  # deterministic epoch
    result = format_cet_timestamp(timestamp)
    assert result is not None
    parsed = datetime.strptime(result, "%Y-%m-%d %H:%M:%S")
    assert parsed.tzinfo is None


def test_format_cet_timestamp_rejects_invalid_input():
    assert format_cet_timestamp("not-a-timestamp") is None


def test_now_cet_timestamp_uses_cet_timezone(monkeypatch):
    captured: dict[str, object] = {}

    def fake_now(zone):
        captured["zone"] = zone
        return datetime(2024, 12, 1, 13, 0, tzinfo=zone)

    monkeypatch.setattr(
        "utils.datetime_formatting.datetime",
        SimpleNamespace(now=fake_now),
    )

    assert now_cet_timestamp() == "2024-12-01 13:00:00"
    assert getattr(captured["zone"], "key", None) == "Europe/Berlin"
