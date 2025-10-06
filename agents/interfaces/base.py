"""Abstract base classes for agent extension points."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Mapping, Optional


class BasePollingAgent(ABC):
    """Contract for agents that retrieve events from external systems."""

    @abstractmethod
    async def poll(self) -> Iterable[Mapping[str, Any]]:
        """Yield event payloads that should be processed by the workflow."""

    @abstractmethod
    async def poll_contacts(self) -> Iterable[Mapping[str, Any]]:
        """Optionally yield contact payloads associated with the events."""


class BaseTriggerAgent(ABC):
    """Contract for agents that detect triggers on events."""

    @abstractmethod
    async def check(self, event: Mapping[str, Any]) -> Dict[str, Any]:
        """Return structured trigger detection information for an event."""


class BaseExtractionAgent(ABC):
    """Contract for agents that extract structured information from events."""

    @abstractmethod
    async def extract(self, event: Mapping[str, Any]) -> Dict[str, Any]:
        """Return structured information extracted from an event payload.

        Implementations must be defined as async coroutines so callers can
        `await` extraction even when the underlying work is synchronous.
        """


class BaseHumanAgent(ABC):
    """Contract for human-in-the-loop escalation and confirmation flows."""

    @abstractmethod
    # NOTE: Diese Methoden bleiben vorerst synchron, da aktuelle Implementierungen
    #       keine asynchronen Nebenwirkungen besitzen. Netzwerk-Hooks werden bei
    #       Bedarf in einem späteren Schritt auf async angehoben.
    def request_info(
        self, event: Mapping[str, Any], extracted: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request missing information from a human collaborator."""

    @abstractmethod
    def request_dossier_confirmation(
        self,
        event: Mapping[str, Any],
        info: Mapping[str, Any],
        *,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ask whether a dossier should be produced for the supplied event."""


class BaseCrmAgent(ABC):
    """Contract for agents that persist qualified events into a CRM system."""

    @abstractmethod
    async def send(self, event: Mapping[str, Any], info: Mapping[str, Any]) -> None:
        """Persist the event with the extracted information into the CRM system."""


class BaseResearchAgent(ABC):
    """Contract for agents that perform internal research workflows."""

    @abstractmethod
    async def run(self, trigger: Mapping[str, Any]) -> Mapping[str, Any]:
        """Execute a research workflow and return a normalized payload."""
