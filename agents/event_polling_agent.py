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

    def poll(self):
        """Polls calendar events (read-only) and logs them."""
        try:
            events = self.calendar.list_events(max_results=100)
            for event in events:
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
