"""Shared abstract base classes for workflow agents."""

from .base import (
    BaseCrmAgent,
    BaseExtractionAgent,
    BaseHumanAgent,
    BasePollingAgent,
    BaseResearchAgent,
    BaseTriggerAgent,
)

__all__ = [
    "BaseCrmAgent",
    "BaseExtractionAgent",
    "BaseHumanAgent",
    "BasePollingAgent",
    "BaseResearchAgent",
    "BaseTriggerAgent",
]
