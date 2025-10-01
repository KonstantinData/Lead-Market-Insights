# Notes:
# ExtractionAgent is responsible for extracting core business information
# (such as company name and web domain) from event dictionaries.
# This version implements basic logic and can be extended to use NLP or regex.

import logging
import re
from typing import Any, Dict

from agents.factory import register_agent
from agents.interfaces import BaseExtractionAgent


@register_agent(BaseExtractionAgent, "extraction", "default", is_default=True)
class ExtractionAgent(BaseExtractionAgent):
    """
    Agent for extracting required information (e.g., company name, web domain)
    from an event dictionary.
    """

    def __init__(self):
        pass

    async def extract(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Asynchronously extract company metadata from the event payload."""
        try:
            # Notes:
            # Try to find company name in a dedicated field first, fallback to searching in summary or description.
            company_name = event.get("company_name")
            if not company_name:
                # Simple heuristic: look for a capitalized word in the summary (could be improved).
                summary = event.get("summary", "")
                match = re.search(r"\b[A-Z][a-zA-Z0-9&.-]{2,}\b", summary)
                if match:
                    company_name = match.group(0)
                else:
                    # Try description as fallback.
                    description = event.get("description", "")
                    match = re.search(r"\b[A-Z][a-zA-Z0-9&.-]{2,}\b", description)
                    if match:
                        company_name = match.group(0)

            # Try to find web domain in a dedicated field or extract from description.
            web_domain = event.get("web_domain")
            if not web_domain:
                # Simple regex for finding domains in text.
                text = event.get("description", "") + " " + event.get("summary", "")
                match = re.search(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", text)
                if match:
                    web_domain = match.group(0)

            info = {
                "company_name": company_name,
                "web_domain": web_domain,
            }
            is_complete = all(info.values())

            # Notes:
            # You can extend this logic to extract more fields, or to use more advanced NLP if needed.

            return {"info": info, "is_complete": is_complete}
        except Exception as e:
            logging.error(f"Error during info extraction: {e}")
            raise
