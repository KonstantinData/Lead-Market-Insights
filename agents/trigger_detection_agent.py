from typing import Any, Dict, List, Optional

from agents.factory import register_agent
from agents.interfaces import BaseTriggerAgent
from utils.text_normalization import normalize_text


@register_agent(BaseTriggerAgent, "trigger_detection", "default", is_default=True)
class TriggerDetectionAgent(BaseTriggerAgent):
    def __init__(self, trigger_words: Optional[List[str]] = None):
        if trigger_words:
            normalised = [normalize_text(word) for word in trigger_words]
            # Remove duplicates while preserving order
            self.trigger_words = tuple(dict.fromkeys(normalised))
        else:
            # Default trigger words, falls keine übergeben wurden
            self.trigger_words = (normalize_text("trigger word"),)

    def check(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prüft, ob eines der Trigger-Wörter im Event-Summary oder in der
        Event-Beschreibung vorkommt und liefert strukturierte Informationen
        zum Treffer zurück.
        """

        for field_name in ("summary", "description"):
            text = event.get(field_name)
            result = self._check_text_field(text, field_name)
            if result["trigger"]:
                return result

        return self._default_response()

    def check_field(self, text: Optional[str], field_name: str) -> Dict[str, Any]:
        """Öffentliche Hilfsmethode für Einzel-Feld-Prüfungen."""

        return self._check_text_field(text, field_name)

    def _check_text_field(self, text: Optional[str], field_name: str) -> Dict[str, Any]:
        if not text:
            return self._default_response()

        normalized_text = normalize_text(text)

        for word in self.trigger_words:
            if word in normalized_text:
                trigger_type = "hard" if field_name == "summary" else "soft"
                return {
                    "trigger": True,
                    "type": trigger_type,
                    "matched_word": word,
                    "matched_field": field_name,
                }

        return self._default_response()

    def _default_response(self) -> Dict[str, Any]:
        return {
            "trigger": False,
            "type": None,
            "matched_word": None,
            "matched_field": None,
        }
