import logging
from typing import Any, Dict, Iterable, Optional

from agents.factory import register_agent
from agents.interfaces import BasePollingAgent
from integration.google_calendar_integration import GoogleCalendarIntegration
from integration.google_contacts_integration import GoogleContactsIntegration

logger = logging.getLogger(__name__)


@register_agent(BasePollingAgent, "event_polling", "default", is_default=True)
class EventPollingAgent(BasePollingAgent):
    def __init__(
        self,
        config: Any = None,
        *,
        calendar_integration: Optional[GoogleCalendarIntegration] = None,
        contacts_integration: Optional[GoogleContactsIntegration] = None,
    ):
        self.config = config
        self.calendar = calendar_integration or GoogleCalendarIntegration()
        # Access token wird per Calendar-Integration gemanaged
        self.contacts = contacts_integration

    @staticmethod
    def _is_birthday_event(event: Dict[str, Any]) -> bool:
        """Return ``True`` if the given event represents a birthday entry."""

        if not isinstance(event, dict):
            return False

        event_type = (event.get("eventType") or "").lower()
        if event_type == "birthday":
            return True

        keywords = ("birthday", "geburtstag")
        for key in ("summary", "description", "summaryOverride"):
            value = event.get(key)
            if isinstance(value, str) and any(keyword in value.lower() for keyword in keywords):
                return True

        direct_flag = event.get("isBirthday")
        if isinstance(direct_flag, bool) and direct_flag:
            return True
        if isinstance(direct_flag, str) and direct_flag.lower() == "true":
            return True

        metadata = event.get("metadata")
        if isinstance(metadata, dict):
            meta_flag = metadata.get("isBirthday")
            if isinstance(meta_flag, bool) and meta_flag:
                return True
            if isinstance(meta_flag, str) and meta_flag.lower() == "true":
                return True

        return False

    def poll(self) -> Iterable[Dict[str, Any]]:
        """Polls calendar events (read-only) and logs them, skipping birthday entries."""
        try:
            events = self.calendar.list_events(max_results=100)
            for event in events:
                if self._is_birthday_event(event):
                    logger.debug(
                        "Skipping birthday event: %s (%s)",
                        event.get("summary", ""),
                        event.get("id", ""),
                    )
                    continue  # Geburtstage überspringen!
                logger.info(f"Polled calendar event: {event}")
                yield event
        except Exception as e:
            logger.error(f"Google Calendar polling failed: {e}")
            raise

    def poll_events(
        self,
        start_time,
        end_time,
        *,
        max_results: Optional[int] = None,
        query: Optional[str] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Return events using the calendar integration's public facade."""

        return self.calendar.fetch_events(
            start_time=start_time,
            end_time=end_time,
            max_results=max_results,
            query=query,
        )

    def poll_contacts(self) -> Iterable[Dict[str, Any]]:
        """
        Polls contacts (read-only) and logs them.
        """
        access_token = self.calendar.get_access_token()
        if not self.contacts:
            self.contacts = GoogleContactsIntegration(access_token)
        else:
            self.contacts.access_token = access_token
        try:
            contacts = self.contacts.list_contacts(page_size=10)
            for contact in contacts:
                logger.info(f"Polled contact: {contact}")
                yield contact
        except Exception as e:
            logger.error(f"Google Contacts polling failed: {e}")
            raise
