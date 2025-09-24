# Notes: Agent responsible for extracting required information from an event.
class ExtractionAgent:
    def extract(self, event):
        """
        Notes:
        - Extracts required information (e.g., company name, web domain)
        from the event.
        - Returns a dictionary with extracted info and a completeness flag.
        """
        info = {
            "company_name": event.get("company_name"),
            "web_domain": event.get("web_domain"),
        }
        is_complete = all(info.values())
        return {"info": info, "is_complete": is_complete}
