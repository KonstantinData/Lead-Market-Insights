import re
from typing import List, Optional, Dict, Any


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    # Umlaute ersetzen
    return (
        text.replace("ü", "ue").replace("ä", "ae").replace("ö", "oe").replace("ß", "ss")
    )


class TriggerDetectionAgent:
    def __init__(self, trigger_words: Optional[List[str]] = None):
        if trigger_words:
            self.trigger_words = tuple(normalize_text(word) for word in trigger_words)
        else:
            # Default trigger words, falls keine übergeben wurden
            self.trigger_words = ("trigger word",)

    def check(self, event: Dict[str, Any]) -> bool:
        """
        Prüft, ob eines der Trigger-Wörter im Event-Summary vorkommt.

        Gibt True zurück, wenn ein Treffer gefunden wurde, sonst False.
        """
        summary = event.get("summary")
        if not summary:
            return False
        normalized_summary = normalize_text(summary)
        for word in self.trigger_words:
            # Optional: auch einfache Wortgrenzen prüfen (z.B. "Küche" innerhalb "Die KUCHE ist bereit")
            if re.search(rf"\b{re.escape(word)}\b", normalized_summary):
                return True
            # Oder als Substring (wie bisher)
            if word in normalized_summary:
                return True
        return False
