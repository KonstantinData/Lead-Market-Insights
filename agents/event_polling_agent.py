import logging
from integration.google_calendar_integration import GoogleCalendarIntegration
from integration.google_contacts_integration import GoogleContactsIntegration

logger = logging.getLogger(__name__)


class EventPollingAgent:
    def __init__(self, config=None):
        self.config = config
        self.calendar = GoogleCalendarIntegration()
        # Access token wird per Calendar-Integration gemanaged
        self.contacts = None

    @staticmethod
    def _is_birthday_event(event: dict) -> bool:
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

    def poll(self):
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

    def poll_contacts(self):
        """
        Polls contacts (read-only) and logs them.
        """
        # Stelle sicher, dass Access Token gültig ist
        self.calendar._ensure_access_token()
        if not self.contacts:
            self.contacts = GoogleContactsIntegration(self.calendar._access_token)
        try:
            contacts = self.contacts.list_contacts(page_size=10)
            for contact in contacts:
                logger.info(f"Polled contact: {contact}")
                yield contact
        except Exception as e:
            logger.error(f"Google Contacts polling failed: {e}")
            raise
