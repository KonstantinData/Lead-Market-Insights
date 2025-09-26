"""Shared abstract base classes for workflow agents."""

from .base import (
    BaseCrmAgent,
    BaseExtractionAgent,
    BaseHumanAgent,
    BasePollingAgent,
    BaseTriggerAgent,
)

__all__ = [
    "BaseCrmAgent",
    "BaseExtractionAgent",
    "BaseHumanAgent",
    "BasePollingAgent",
    "BaseTriggerAgent",
]
