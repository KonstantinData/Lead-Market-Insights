from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.event_polling_agent import EventPollingAgent


@pytest.fixture
def calendar_mock():
    calendar = MagicMock()
    calendar.list_events_async = AsyncMock()
    calendar.fetch_events_async = AsyncMock()
    calendar.get_access_token_async = AsyncMock()
    calendar.aclose = AsyncMock()
    return calendar


@pytest.fixture
def contacts_mock():
    contacts = MagicMock()
    contacts.list_contacts_async = AsyncMock()
    contacts.aclose = AsyncMock()
    return contacts


@pytest.mark.asyncio
async def test_poll_filters_birthday_events(calendar_mock):
    agent = EventPollingAgent(calendar_integration=calendar_mock)
    calendar_mock.list_events_async.return_value = [
        {"id": "1", "summary": "Strategy sync"},
        {"id": "2", "eventType": "birthday", "summary": "CEO birthday"},
        {"id": "3", "summary": "Geburtstag Sales"},
    ]

    events = await agent.poll()

    assert [event["id"] for event in events] == ["1"]
    calendar_mock.list_events_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_propagates_errors(calendar_mock):
    agent = EventPollingAgent(calendar_integration=calendar_mock)
    calendar_mock.list_events_async.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await agent.poll()


@pytest.mark.asyncio
async def test_poll_contacts_initialises_integration(monkeypatch, calendar_mock):
    created = {}

    class FakeContacts:
        def __init__(self, access_token):
            created["token"] = access_token
            self.access_token = access_token
            self.list_contacts_async = AsyncMock(return_value=[{"name": "Alice"}])
            self.aclose = AsyncMock()

    monkeypatch.setattr(
        "agents.event_polling_agent.GoogleContactsIntegration", FakeContacts
    )

    calendar_mock.get_access_token_async.return_value = "token-123"
    agent = EventPollingAgent(calendar_integration=calendar_mock)

    contacts = await agent.poll_contacts()

    assert contacts == [{"name": "Alice"}]
    assert created["token"] == "token-123"


@pytest.mark.asyncio
async def test_poll_contacts_uses_existing_integration(calendar_mock, contacts_mock):
    contacts_mock.list_contacts_async.side_effect = RuntimeError("failure")
    agent = EventPollingAgent(
        calendar_integration=calendar_mock,
        contacts_integration=contacts_mock,
    )
    calendar_mock.get_access_token_async.return_value = "token"

    with pytest.raises(RuntimeError):
        await agent.poll_contacts()

    assert contacts_mock.access_token == "token"


@pytest.mark.asyncio
async def test_poll_events_async_delegates(calendar_mock):
    agent = EventPollingAgent(calendar_integration=calendar_mock)
    calendar_mock.fetch_events_async.return_value = [{"id": "evt"}]

    result = await agent.poll_events_async("start", "end", max_results=5, query="demo")

    assert result == [{"id": "evt"}]
    calendar_mock.fetch_events_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_closes_clients(calendar_mock, contacts_mock):
    agent = EventPollingAgent(
        calendar_integration=calendar_mock,
        contacts_integration=contacts_mock,
    )

    await agent.aclose()

    calendar_mock.aclose.assert_awaited_once()
    contacts_mock.aclose.assert_awaited_once()


@pytest.mark.parametrize(
    "event, expected",
    [
        ({"eventType": "birthday"}, True),
        ({"summary": "CEO Birthday"}, True),
        ({"summary": "Project kickoff"}, False),
        ({"metadata": {"isBirthday": "true"}}, True),
        ({"isBirthday": False}, False),
        ("not-a-dict", False),
    ],
)
def test_is_birthday_event(event, expected):
    assert EventPollingAgent._is_birthday_event(event) is expected
