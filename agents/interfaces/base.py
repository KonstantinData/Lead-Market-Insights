"""Abstract base classes for agent extension points."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Mapping


class BasePollingAgent(ABC):
    """Contract for agents that retrieve events from external systems."""

    @abstractmethod
    def poll(self) -> Iterable[Mapping[str, Any]]:
        """Yield event payloads that should be processed by the workflow."""

    @abstractmethod
    def poll_contacts(self) -> Iterable[Mapping[str, Any]]:
        """Optionally yield contact payloads associated with the events."""


class BaseTriggerAgent(ABC):
    """Contract for agents that detect triggers on events."""

    @abstractmethod
    def check(self, event: Mapping[str, Any]) -> Dict[str, Any]:
        """Return structured trigger detection information for an event."""


class BaseExtractionAgent(ABC):
    """Contract for agents that extract structured information from events."""

    @abstractmethod
    def extract(self, event: Mapping[str, Any]) -> Dict[str, Any]:
        """Return structured information extracted from an event payload."""


class BaseHumanAgent(ABC):
    """Contract for human-in-the-loop escalation and confirmation flows."""

    @abstractmethod
    def request_info(self, event: Mapping[str, Any], extracted: Dict[str, Any]) -> Dict[str, Any]:
        """Request missing information from a human collaborator."""

    @abstractmethod
    def request_dossier_confirmation(self, event: Mapping[str, Any], info: Mapping[str, Any]) -> Dict[str, Any]:
        """Ask whether a dossier should be produced for the supplied event."""


class BaseCrmAgent(ABC):
    """Contract for agents that persist qualified events into a CRM system."""

    @abstractmethod
    def send(self, event: Mapping[str, Any], info: Mapping[str, Any]) -> None:
        """Persist the event with the extracted information into the CRM system."""


class BaseResearchAgent(ABC):
    """Contract for agents that perform internal research workflows."""

    @abstractmethod
    def run(self, trigger: Mapping[str, Any]) -> Mapping[str, Any]:
        """Execute a research workflow and return a normalized payload."""
