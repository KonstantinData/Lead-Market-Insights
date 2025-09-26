import logging
from datetime import datetime

# Notes:
# This Extractor class is responsible for extracting relevant fields from raw event data.
# This includes typical event fields like summary/title, start time, and end time.
# This can be extended to extract more complex data from event dictionaries or JSON objects.


class Extractor:
    """
    Module for data extraction (e.g., extracting meeting details from event data).
    Implements field extraction logic for event dictionaries.
    """

    def __init__(self):
        pass

    def extract_fields(self, raw_data):
        """
        Extract relevant fields from a raw event dictionary.
        Returns a dictionary with the extracted fields.
        """
        try:
            # Notes:
            # We assume raw_data is a dict with possible keys: "summary", "start", "end", "description", etc.
            summary = raw_data.get("summary", "")
            description = raw_data.get("description", "")

            # Extract start and end times if available, and try to parse them as datetime objects.
            start_raw = raw_data.get("start")
            end_raw = raw_data.get("end")
            start = self._parse_datetime(start_raw)
            end = self._parse_datetime(end_raw)

            extracted = {
                "summary": summary,
                "description": description,
                "start": start,
                "end": end,
            }
            return extracted
        except Exception as e:
            logging.error(f"Error during extraction: {e}")
            raise

    @staticmethod
    def _parse_datetime(value):
        """
        Tries to parse a value as a datetime object.
        Accepts ISO-8601 strings or returns None if not parseable.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            # Most APIs deliver ISO 8601 strings for datetime fields.
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            # Notes: If parsing fails, just return the raw value (could be improved further).
            return value
