"""Trigger detection workflow implementation."""

from __future__ import annotations

import inspect
import json
import logging
import os
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from collections import Counter

from agents.factory import register_agent
from agents.interfaces import BaseTriggerAgent
from agents.soft_trigger_validator import (
    SoftTriggerValidator,
    load_synonym_phrases,
)
from config.config import settings
from utils.async_http import AsyncHTTP
from utils.text_normalization import normalize_text

logger = logging.getLogger(__name__)


SoftTriggerDetector = Callable[
    [str, str, Sequence[str]],
    Union[Sequence[Mapping[str, Any]], Awaitable[Sequence[Mapping[str, Any]]]],
]


class _OpenAiSoftTriggerDetector:
    """Wrapper around the OpenAI Responses API for soft trigger detection."""

    _DEFAULT_BASE = settings.openai_api_base or os.getenv(
        "OPENAI_API_BASE", "https://api.openai.com"
    )
    _ENDPOINT = "/v1/chat/completions"

    def __init__(self, api_key: str, *, model: str = "gpt-4o-mini", timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._http = AsyncHTTP(base_url=self._DEFAULT_BASE, timeout=timeout)

    async def __call__(
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

        response = await self._http.post(
            self._ENDPOINT, headers=headers, json=payload
        )
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
Deine Aufgabe ist es, zwei spezifische Textfelder aus Google Calendar-Einträgen
auf sogenannte weiche Trigger (Soft-Trigger) zu untersuchen,
die sinngemäß dieselbe Bedeutung haben wie sogenannte harte Trigger
(Hard-Trigger).
Die Hard-Trigger sind eine Liste fester Schlüsselwörter oder -phrasen, die in der Datei `config/trigger_words.txt` definiert sind.

### Eingabedaten:
- `summary`: Textinhalt des Kalendereintrags (z. B. Titel des Events)
- `description`: Beschreibungstext des Kalendereintrags
- `hard_triggers`: Liste von Hard-Triggern aus der Datei `config/trigger_words.txt`

### Anforderungen:
1. Untersuche die Felder `summary` und `description` auf Begriffe oder Phrasen
   (Soft-Trigger), die semantisch einem Eintrag aus `hard_triggers` entsprechen.
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
        soft_trigger_validator: Optional[SoftTriggerValidator] = None,
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
        self._soft_trigger_validator: Optional[SoftTriggerValidator]
        if soft_trigger_validator is not None:
            self._soft_trigger_validator = soft_trigger_validator
        elif settings.soft_trigger_validator_enabled:
            try:
                synonyms = load_synonym_phrases(settings.synonym_trigger_path)
                self._soft_trigger_validator = SoftTriggerValidator(
                    synonyms=synonyms,
                    require_evidence_substring=settings.validator_require_evidence_substring,
                    fuzzy_evidence_threshold=settings.validator_fuzzy_evidence_threshold,
                    similarity_method=settings.validator_similarity_method,
                    similarity_threshold=settings.validator_similarity_threshold,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.warning(
                    "Initialising soft trigger validator failed: %s. Soft matches will bypass validation.",
                    exc,
                )
                self._soft_trigger_validator = None
        else:
            self._soft_trigger_validator = None

        self._soft_validator_write_artifacts = settings.soft_validator_write_artifacts

    async def check(self, event: Dict[str, Any]) -> Dict[str, Any]:
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

        soft_matches = await self._detect_soft_triggers(event)
        logger.info(
            "Event %s: Soft trigger candidates after initial sanitisation: %d",
            event_id,
            len(soft_matches),
        )

        validated_matches: List[Dict[str, Any]] = list(soft_matches)

        if soft_matches and self._soft_trigger_validator is not None:
            try:
                accepted, rejected = self._soft_trigger_validator.validate(
                    summary=event.get("summary") or "",
                    description=event.get("description") or "",
                    matches=soft_matches,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.warning(
                    "Event %s: Soft trigger validation failed (%s); using raw LLM candidates.",
                    event_id,
                    exc,
                )
                accepted = list(soft_matches)
                rejected = []
            else:
                logger.info(
                    "Event %s: Soft validator accepted=%d rejected=%d",
                    event_id,
                    len(accepted),
                    len(rejected),
                )
                if rejected:
                    breakdown = Counter(
                        entry.get("reject_reason", "unknown") for entry in rejected
                    )
                    logger.info(
                        "Event %s: Soft validator reject breakdown=%s",
                        event_id,
                        dict(breakdown),
                    )
                if self._soft_validator_write_artifacts:
                    self._persist_soft_validator_artifact(
                        event,
                        llm_candidates=soft_matches,
                        accepted=accepted,
                        rejected=rejected,
                    )

            validated_matches = list(accepted)
        elif soft_matches and self._soft_trigger_validator is None:
            logger.info(
                "Event %s: Soft trigger validator disabled; using LLM candidates without validation.",
                event_id,
            )

        if validated_matches:
            first_match = validated_matches[0]
            logger.info(
                "Event %s: Soft trigger(s) detected after validation (matched hard trigger '%s')",
                event_id,
                first_match.get("matched_hard_trigger"),
            )
            extraction_context = {
                "summary": event.get("summary"),
                "description": event.get("description"),
                "soft_trigger_matches": validated_matches,
                "hard_triggers": list(self.original_trigger_words),
            }
            return {
                "trigger": True,
                "type": "soft",
                "matched_word": first_match.get("soft_trigger"),
                "matched_field": first_match.get("source_field"),
                "soft_trigger_matches": validated_matches,
                "hard_triggers": list(self.original_trigger_words),
                "extraction_context": extraction_context,
            }

        logger.info(
            "Event %s: No valid soft triggers detected after validation", event_id
        )
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

    async def _detect_soft_triggers(self, event: Mapping[str, Any]) -> List[Dict[str, Any]]:
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
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning(
                    "Event %s: OPENAI_API_KEY not available; skipping soft trigger detection",
                    event_id,
                )
                return []
            detector = _OpenAiSoftTriggerDetector(api_key)

        try:
            raw_matches = detector(summary, description, self.original_trigger_words)
            if inspect.isawaitable(raw_matches):
                raw_matches = await raw_matches
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Event %s: Soft trigger detection failed: %s", event_id, exc)
            return []

        if raw_matches is None:
            candidates: List[Mapping[str, Any]] = []
        else:
            try:
                candidates = list(raw_matches)
            except TypeError:
                logger.warning(
                    "Event %s: Soft trigger detector returned a non-iterable response; ignoring.",
                    event_id,
                )
                candidates = []

        logger.info(
            "Event %s: Soft trigger LLM produced %d candidate(s)",
            event_id,
            len(candidates),
        )

        validated = self._validate_soft_trigger_matches(candidates)
        if not validated and candidates:
            logger.info(
                "Event %s: LLM candidates discarded due to invalid structure", event_id
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

    def _persist_soft_validator_artifact(
        self,
        event: Mapping[str, Any],
        *,
        llm_candidates: Sequence[Mapping[str, Any]],
        accepted: Sequence[Mapping[str, Any]],
        rejected: Sequence[Mapping[str, Any]],
    ) -> None:
        if not self._soft_validator_write_artifacts:
            return

        run_id = self._resolve_run_id(event)
        event_identifier = self._safe_identifier(event.get("id"), default="event")
        run_identifier = self._safe_identifier(run_id, default="run")

        target_dir = (
            settings.research_artifact_dir
            / "soft_trigger_validation"
            / run_identifier
        )
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - filesystem issues
            logger.warning(
                "Failed to create validator artifact directory %s: %s",
                target_dir,
                exc,
            )
            return

        payload = {
            "llm_candidates": list(llm_candidates),
            "accepted": list(accepted),
            "rejected": list(rejected),
        }
        artifact_path = target_dir / f"{event_identifier}.json"
        try:
            artifact_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:  # pragma: no cover - filesystem issues
            logger.warning(
                "Failed to write validator artifact for event %s: %s",
                event_identifier,
                exc,
            )

    def _resolve_run_id(self, event: Mapping[str, Any]) -> str:
        candidates = [
            event.get("run_id"),
            event.get("runId"),
        ]
        metadata = event.get("metadata")
        if isinstance(metadata, Mapping):
            candidates.extend([
                metadata.get("run_id"),
                metadata.get("runId"),
            ])
        context = event.get("context")
        if isinstance(context, Mapping):
            candidates.extend([
                context.get("run_id"),
                context.get("runId"),
            ])

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return "default"

    @staticmethod
    def _safe_identifier(value: Any, *, default: str) -> str:
        text = str(value).strip() if value is not None else ""
        if not text:
            return default
        sanitized = "".join(
            ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text
        ).strip("_")
        return sanitized or default
