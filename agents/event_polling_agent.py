# Notes: Agent responsible for polling events from an
# external source (e.g. Google Calendar, API, database).
class EventPollingAgent:
    def __init__(self, config=None):
        # Notes: Store configuration for later use (API keys, time frame, etc.)
        self.config = config

    def poll(self):
        """
        Notes:
        - Polls events from the intended data source.
        - Replace the dummy events below with actual API/database calls.
        - Yields each event as a dictionary.
        """
        dummy_events = [
            {"id": 1, "summary": "Customer meeting with trigger word"},
            {"id": 2, "summary": "Team call with no trigger"},
        ]
        for event in dummy_events:
            yield event
