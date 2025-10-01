import asyncio
import logging
from typing import List

import pytest

from agents.event_polling_agent import EventPollingAgent


class DummyCalendar:
    def __init__(self, events: List[dict]):
        self._events = events

    async def list_events_async(self, *, max_results: int):
        assert max_results == 100
        return list(self._events)

    async def fetch_events_async(self, *args, **kwargs):
        return list(self._events)

    async def get_access_token_async(self):
        return "token"


class DummyContacts:
    def __init__(self, contacts: List[dict]):
        self._contacts = contacts

    async def list_contacts_async(self, *, page_size: int = 10):
        assert page_size == 10
        return list(self._contacts)


@pytest.fixture
def dummy_calendar_events():
    return [
        {"id": "1", "summary": "Projektmeeting"},
        {"id": "2", "eventType": "birthday", "summary": "Birthday: Alice"},
        {"id": "3", "summary": "Teamabend", "description": "Geburtstag feiern"},
        {"id": "4", "summary": "Geburtstag Max"},
        {"id": "5", "summary": "Produkt-Review"},
    ]


def test_poll_skips_birthday_events(dummy_calendar_events, caplog):
    caplog.set_level(logging.DEBUG)
    calendar = DummyCalendar(dummy_calendar_events)
    agent = EventPollingAgent(calendar_integration=calendar)

    polled_events = asyncio.run(agent.poll())

    assert [event["id"] for event in polled_events] == ["1", "5"]
    skipped_logs = [
        record
        for record in caplog.records
        if record.levelno == logging.DEBUG
        and "Skipping birthday event" in record.getMessage()
    ]
    assert len(skipped_logs) == 3


def test_agent_uses_public_fetch_events(mocker):
    integration = mocker.Mock()
    integration.fetch_events_async = mocker.AsyncMock(return_value=[{"id": "e1"}])

    agent = EventPollingAgent(calendar_integration=integration)

    events = agent.poll_events(
        "2025-01-01T00:00:00Z",
        "2025-01-02T00:00:00Z",
    )

    integration.fetch_events_async.assert_awaited_once_with(
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-02T00:00:00Z",
        max_results=None,
        query=None,
    )
    assert events == [{"id": "e1"}]


def test_poll_contacts_uses_async_flow(dummy_calendar_events, mocker):
    calendar = DummyCalendar(dummy_calendar_events)
    contacts = DummyContacts([{"resourceName": "people/1"}])

    agent = EventPollingAgent(
        calendar_integration=calendar,
        contacts_integration=contacts,
    )

    contacts_result = agent.poll_contacts()
    assert contacts_result == [{"resourceName": "people/1"}]
