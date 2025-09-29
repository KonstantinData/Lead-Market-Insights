"""Trigger detection workflow implementation."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import httpx

from agents.factory import register_agent
from agents.interfaces import BaseTriggerAgent
from utils.text_normalization import normalize_text

logger = logging.getLogger(__name__)


SoftTriggerDetector = Callable[[str, str, Sequence[str]], Sequence[Mapping[str, Any]]]


class _OpenAiSoftTriggerDetector:
    """Wrapper around the OpenAI Responses API for soft trigger detection."""

    _ENDPOINT = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, *, model: str = "gpt-4o-mini", timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def __call__(
        self, summary: str, description: str, hard_triggers: Sequence[str]
    ) -> Sequence[Mapping[str, Any]]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": TriggerDetectionAgent.SOFT_TRIGGER_PROMPT.strip()
                    + "\n\n"
                    + json.dumps(
                        {
                            "summary": summary,
                            "description": description,
                            "hard_triggers": list(hard_triggers),
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            "temperature": 0.0,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self._ENDPOINT, headers=headers, json=payload)
            response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return []
        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            return []
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return parsed
        return []


@register_agent(BaseTriggerAgent, "trigger_detection", "default", is_default=True)
class TriggerDetectionAgent(BaseTriggerAgent):
    """Agent responsible for hard and soft trigger detection."""

    SOFT_TRIGGER_PROMPT = """
Du bist ein Trigger-Erkennungs-Agent, der Kalendereinträge analysiert.
Deine Aufgabe ist es, zwei spezifische Textfelder aus Google Calendar-Einträgen auf sogenannte weiche Trigger (Soft-Trigger) zu untersuchen, die sinngemäß dieselbe Bedeutung haben wie sogenannte harte Trigger (Hard-Trigger).
Die Hard-Trigger sind eine Liste fester Schlüsselwörter oder -phrasen, die in der Datei `config/trigger_words.txt` definiert sind.

### Eingabedaten:
- `summary`: Textinhalt des Kalendereintrags (z. B. Titel des Events)
- `description`: Beschreibungstext des Kalendereintrags
- `hard_triggers`: Liste von Hard-Triggern aus der Datei `config/trigger_words.txt`

### Anforderungen:
1. Untersuche die Felder `summary` und `description` auf Begriffe oder Phrasen (Soft-Trigger), die semantisch einem Eintrag aus `hard_triggers` entsprechen.
2. Gib für jeden gefundenen Soft-Trigger folgendes zurück:
    - `soft_trigger`: Das gefundene Wort bzw. die Phrase
    - `matched_hard_trigger`: Der zugehörige Hard-Trigger
    - `source_field`: `"summary"` oder `"description"`
    - `reason`: Kurze Begründung für die Zuordnung (optional)

### Beispiel-Ausgabe (JSON):
[
  {
    "soft_trigger": "Meeting mit Kunde Müller",
    "matched_hard_trigger": "Kundentermin",
    "source_field": "summary",
    "reason": "Bedeutet sinngemäß dasselbe wie Kundentermin"
  },
  {
    "soft_trigger": "Onboarding Session",
    "matched_hard_trigger": "Mitarbeitereinführung",
    "source_field": "description",
    "reason": "Onboarding ist ein Synonym für Mitarbeitereinführung"
  }
]

Wenn keine Übereinstimmungen gefunden werden, gib ein leeres Array `[]` zurück.
Antworte ausschließlich mit der JSON-Struktur.
""".strip()

    def __init__(
        self,
        trigger_words: Optional[Sequence[str]] = None,
        *,
        soft_trigger_detector: Optional[SoftTriggerDetector] = None,
    ) -> None:
        provided = [str(word).strip() for word in (trigger_words or []) if str(word).strip()]
        self.hard_trigger_words: tuple[str, ...]
        if provided:
            deduplicated: List[str] = []
            seen = set()
            for word in provided:
                normalised = normalize_text(word)
                if normalised in seen:
                    continue
                seen.add(normalised)
                deduplicated.append(str(word))
            self.original_trigger_words = tuple(deduplicated)
            self.hard_trigger_words = tuple(normalize_text(word) for word in deduplicated)
        else:
            default_word = "trigger word"
            self.original_trigger_words = (default_word,)
            self.hard_trigger_words = (normalize_text(default_word),)

        self._soft_trigger_detector = soft_trigger_detector

    def check(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate an event for hard and soft triggers."""

        event_id = event.get("id")
        logger.info("Event %s: Starting trigger detection", event_id)

        hard_result = self._detect_hard_trigger(event)
        if hard_result:
            logger.info(
                "Event %s: Hard trigger matched '%s' in %s",
                event_id,
                hard_result["matched_word"],
                hard_result["matched_field"],
            )
            return hard_result

        logger.info("Event %s: No hard triggers found; evaluating soft triggers", event_id)

        soft_matches = self._detect_soft_triggers(event)
        if soft_matches:
            first_match = soft_matches[0]
            logger.info(
                "Event %s: Soft trigger(s) detected via LLM (matched hard trigger '%s')",
                event_id,
                first_match.get("matched_hard_trigger"),
            )
            extraction_context = {
                "summary": event.get("summary"),
                "description": event.get("description"),
                "soft_trigger_matches": soft_matches,
                "hard_triggers": list(self.original_trigger_words),
            }
            return {
                "trigger": True,
                "type": "soft",
                "matched_word": first_match.get("soft_trigger"),
                "matched_field": first_match.get("source_field"),
                "soft_trigger_matches": soft_matches,
                "hard_triggers": list(self.original_trigger_words),
                "extraction_context": extraction_context,
            }

        logger.info("Event %s: No hard or soft triggers detected", event_id)
        return self._default_response()

    def check_field(self, text: Optional[str], field_name: str) -> Dict[str, Any]:
        """Öffentliche Hilfsmethode für Einzel-Feld-Prüfungen."""

        return self._check_text_field(text, field_name)

    def _detect_hard_trigger(self, event: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        for field_name in ("summary", "description"):
            text = event.get(field_name)
            result = self._check_text_field(text, field_name)
            if result["trigger"]:
                return result
        return None

    def _detect_soft_triggers(self, event: Mapping[str, Any]) -> List[Dict[str, Any]]:
        summary = event.get("summary") or ""
        description = event.get("description") or ""
        event_id = event.get("id")

        if not summary and not description:
            logger.info(
                "Event %s: Skipping soft trigger detection due to missing summary and description",
                event_id,
            )
            return []

        detector = self._soft_trigger_detector
        if detector is None:
            api_key = os.getenv("OPEN_AI_KEY")
            if not api_key:
                logger.warning(
                    "Event %s: OPEN_AI_KEY not available; skipping soft trigger detection",
                    event_id,
                )
                return []
            detector = _OpenAiSoftTriggerDetector(api_key)

        try:
            raw_matches = detector(summary, description, self.original_trigger_words)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Event %s: Soft trigger detection failed: %s", event_id, exc)
            return []

        validated = self._validate_soft_trigger_matches(raw_matches)
        if not validated:
            logger.info(
                "Event %s: LLM returned no valid soft trigger matches", event_id
            )
        return validated

    def _check_text_field(self, text: Optional[str], field_name: str) -> Dict[str, Any]:
        if not text:
            return self._default_response()

        normalized_text = normalize_text(text)

        for word in self.hard_trigger_words:
            if word in normalized_text:
                return {
                    "trigger": True,
                    "type": "hard",
                    "matched_word": word,
                    "matched_field": field_name,
                    "soft_trigger_matches": [],
                    "hard_triggers": list(self.original_trigger_words),
                }

        return self._default_response()

    def _default_response(self) -> Dict[str, Any]:
        return {
            "trigger": False,
            "type": None,
            "matched_word": None,
            "matched_field": None,
            "soft_trigger_matches": [],
            "hard_triggers": list(self.original_trigger_words),
        }

    def _validate_soft_trigger_matches(
        self, raw_matches: Iterable[Mapping[str, Any]]
    ) -> List[Dict[str, Any]]:
        validated: List[Dict[str, Any]] = []

        for candidate in raw_matches:
            if not isinstance(candidate, Mapping):
                continue
            soft_trigger = str(candidate.get("soft_trigger", "")).strip()
            matched = str(candidate.get("matched_hard_trigger", "")).strip()
            source_field = str(candidate.get("source_field", "")).strip()
            if not soft_trigger or not matched or source_field not in {"summary", "description"}:
                continue
            reason_value = candidate.get("reason")
            reason = str(reason_value).strip() if reason_value is not None else None
            validated.append(
                {
                    "soft_trigger": soft_trigger,
                    "matched_hard_trigger": matched,
                    "source_field": source_field,
                    "reason": reason,
                }
            )

        return validated
