from datetime import datetime

from utils.datetime_formatting import format_report_datetime


def test_format_report_datetime_with_iso_string():
    value = "2024-03-05T15:30:00+01:00"
    assert format_report_datetime(value) == "05.03.2024 15:30 CET"


def test_format_report_datetime_with_naive_datetime():
    naive_value = datetime(2024, 7, 1, 8, 15, 0)
    assert format_report_datetime(naive_value) == "01.07.2024 10:15 CET"


def test_format_report_datetime_with_unparseable_input():
    sentinel = object()
    assert format_report_datetime(sentinel) == str(sentinel)
