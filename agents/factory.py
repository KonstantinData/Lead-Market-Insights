"""Factory utilities and registry for workflow agents."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, MutableMapping, Optional, Type, TypeVar

from agents.interfaces import (
    BaseCrmAgent,
    BaseExtractionAgent,
    BaseHumanAgent,
    BasePollingAgent,
    BaseTriggerAgent,
)

TAgent = TypeVar("TAgent")

_AgentRegistry = MutableMapping[Type[Any], Dict[str, Type[Any]]]

_REGISTRY: _AgentRegistry = defaultdict(dict)
_DEFAULTS: Dict[Type[Any], str] = {}


def register_agent(
    interface: Type[TAgent],
    *names: str,
    is_default: bool = False,
) -> Any:
    """Register a concrete implementation for the given interface."""

    if not names:
        raise ValueError("At least one registry name must be provided.")

    def decorator(cls: Type[TAgent]) -> Type[TAgent]:
        if not issubclass(cls, interface):
            raise TypeError(
                f"{cls.__name__} must inherit from {interface.__name__} to register."
            )

        registry = _REGISTRY[interface]
        for name in names:
            registry[name] = cls

        if is_default or interface not in _DEFAULTS:
            _DEFAULTS[interface] = names[0]

        return cls

    return decorator


def create_agent(
    interface: Type[TAgent],
    name: Optional[str] = None,
    **kwargs: Any,
) -> TAgent:
    """Instantiate an agent from the registry."""

    registry = _REGISTRY.get(interface)
    if not registry:
        raise KeyError(f"No agents registered for interface {interface.__name__}.")

    if not name:
        default_name = _DEFAULTS.get(interface)
        if not default_name:
            raise KeyError(
                f"No default agent registered for interface {interface.__name__}."
            )
        name = default_name

    cls = registry.get(name)
    if cls is None:
        available = ", ".join(sorted(registry)) or "<none>"
        raise KeyError(
            f"Agent '{name}' is not registered for interface {interface.__name__}. "
            f"Available options: {available}."
        )

    return cls(**kwargs)


def available_agents(interface: Type[Any]) -> Iterable[str]:
    """Return the registered names for the supplied interface."""

    registry = _REGISTRY.get(interface, {})
    return sorted(registry.keys())


__all__ = [
    "BaseCrmAgent",
    "BaseExtractionAgent",
    "BaseHumanAgent",
    "BasePollingAgent",
    "BaseTriggerAgent",
    "available_agents",
    "create_agent",
    "register_agent",
]
