"""Unit tests for the agent factory registry helpers."""

from __future__ import annotations

import pytest

from agents.factory import available_agents, create_agent, register_agent
from agents.interfaces import BasePollingAgent


class DummyPollingAgent(BasePollingAgent):
    def __init__(self, *, token: str = "") -> None:
        self.token = token

    async def poll(self):  # pragma: no cover - not exercised in tests
        return []

    async def poll_contacts(self):  # pragma: no cover - not exercised in tests
        return []


class NotAnAgent:  # pragma: no cover - intentional for type error test
    pass


def test_register_and_create_agent_defaults(isolated_agent_registry):
    register_agent(BasePollingAgent, "dummy", "alt", is_default=True)(DummyPollingAgent)

    agent = create_agent(BasePollingAgent, token="abc")

    assert isinstance(agent, DummyPollingAgent)
    assert agent.token == "abc"
    assert available_agents(BasePollingAgent) == ["alt", "dummy"]


def test_create_agent_uses_named_override(isolated_agent_registry):
    @register_agent(BasePollingAgent, "default", is_default=True)
    class DefaultAgent(DummyPollingAgent):
        pass

    @register_agent(BasePollingAgent, "custom")
    class CustomAgent(DummyPollingAgent):
        pass

    agent = create_agent(BasePollingAgent, name="custom", token="xyz")
    assert isinstance(agent, CustomAgent)
    assert agent.token == "xyz"


def test_register_agent_validates_names(isolated_agent_registry):
    with pytest.raises(ValueError):
        register_agent(BasePollingAgent)


def test_register_agent_validates_subclass(isolated_agent_registry):
    decorator = register_agent(BasePollingAgent, "bad")
    with pytest.raises(TypeError):
        decorator(NotAnAgent)  # type: ignore[arg-type]


def test_create_agent_errors_when_missing(isolated_agent_registry):
    register_agent(BasePollingAgent, "dummy", is_default=True)(DummyPollingAgent)

    with pytest.raises(KeyError):
        create_agent(BasePollingAgent, name="missing")


def test_create_agent_without_default_raises(isolated_agent_registry):
    register_agent(BasePollingAgent, "dummy")(DummyPollingAgent)
    from agents import factory as factory_module

    factory_module._DEFAULTS.pop(BasePollingAgent, None)

    with pytest.raises(KeyError):
        create_agent(BasePollingAgent)
