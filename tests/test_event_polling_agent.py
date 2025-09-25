import logging

import pytest

import agents.event_polling_agent as event_polling_agent
from agents.event_polling_agent import EventPollingAgent


class DummyCalendar:
    def __init__(self, events):
        self._events = events

    def list_events(self, *, max_results):
        assert max_results == 100
        return list(self._events)


@pytest.fixture
def dummy_calendar(monkeypatch):
    events = [
        {"id": "1", "summary": "Projektmeeting"},
        {"id": "2", "eventType": "birthday", "summary": "Birthday: Alice"},
        {"id": "3", "summary": "Teamabend", "description": "Geburtstag feiern"},
        {"id": "4", "summary": "Geburtstag Max"},
        {"id": "5", "summary": "Produkt-Review"},
    ]

    dummy = DummyCalendar(events)
    monkeypatch.setattr(
        event_polling_agent, "GoogleCalendarIntegration", lambda: dummy
    )
    return events


def test_poll_skips_birthday_events(dummy_calendar, caplog):
    caplog.set_level(logging.DEBUG)
    agent = EventPollingAgent()

    polled_events = list(agent.poll())

    assert [event["id"] for event in polled_events] == ["1", "5"]
    skipped_logs = [
        record
        for record in caplog.records
        if record.levelno == logging.DEBUG
        and "Skipping birthday event" in record.getMessage()
    ]
    assert len(skipped_logs) == 3
