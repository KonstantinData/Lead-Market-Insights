"""Level 1 similar company discovery agent implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
)

from agents.factory import register_agent
from agents.interfaces import BaseResearchAgent
from config.config import settings
from integration.hubspot_integration import HubSpotIntegration
from utils.datetime_formatting import format_report_datetime
from utils.persistence import atomic_write_json
from utils.text_normalization import normalize_text
from utils.validation import normalize_similar_companies


def _tokenize(text: str) -> List[str]:
    """Tokenise *text* into alphanumeric words for loose similarity checks."""

    tokens: List[str] = []
    current = []
    for character in text:
        if character.isalnum():
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tokens


@dataclass(frozen=True)
class _MatchConfig:
    """Criteria configuration used by :class:`IntLvl1SimilarCompaniesAgent`."""

    fields: Sequence[str] = ("segment", "product", "description")
    weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "name": 4.0,
            "segment": 3.0,
            "product": 2.0,
            "description": 1.5,
        }
    )


@register_agent(
    BaseResearchAgent,
    "similar_companies_level1",
    "int_level_1",
)
class IntLvl1SimilarCompaniesAgent(BaseResearchAgent):
    """Discover and persist level 1 similar companies using HubSpot data."""

    #: Default HubSpot properties requested for candidate companies.
    HUBSPOT_PROPERTIES: Sequence[str] = (
        "name",
        "domain",
        "website",
        "segment",
        "product",
        "description",
    )

    #: Default limit applied to persisted level 1 results.
    DEFAULT_RESULT_LIMIT: int = 10

    def __init__(
        self,
        *,
        config: Any = settings,
        hubspot_integration: Optional[HubSpotIntegration] = None,
        result_limit: Optional[int] = None,
        match_config: _MatchConfig = _MatchConfig(),
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )
        self._integration = hubspot_integration or HubSpotIntegration(settings=config)
        self._match_config = match_config

        self._result_limit = max(1, result_limit or self.DEFAULT_RESULT_LIMIT)

        self._artifact_root = Path(config.research_artifact_dir) / (
            "similar_companies_level1"
        )
        self._artifact_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # BaseResearchAgent API
    # ------------------------------------------------------------------
    async def run(self, trigger: Mapping[str, Any]) -> MutableMapping[str, Any]:  # type: ignore[override]
        payload = self._extract_payload(trigger)
        company_name = self._normalise_company_name(payload)
        if not company_name:
            raise ValueError(
                "IntLvl1SimilarCompaniesAgent requires 'company_name' in the payload."
            )

        target_context = self._build_target_context(payload)
        run_id = str(trigger.get("run_id") or payload.get("run_id") or "")
        event_id = str(
            trigger.get("event_id")
            or trigger.get("id")
            or payload.get("event_id")
            or payload.get("id")
            or ""
        )

        candidates = await self._fetch_candidates(company_name)
        ranked_results = self._rank_candidates(candidates, target_context)

        limited_results = ranked_results[: self._result_limit]
        artifact_payload = normalize_similar_companies(
            {
                "company_name": target_context["company_name"],
                "run_id": run_id or None,
                "event_id": event_id or None,
                "generated_at": format_report_datetime(datetime.now(timezone.utc)),
                "results": limited_results,
            }
        )

        artifact_path = self._persist_artifact(
            artifact_payload,
            run_id=run_id or None,
            event_id=event_id or None,
        )

        result_payload = dict(artifact_payload)
        result_payload["artifact_path"] = artifact_path.as_posix()
        status = result_payload.get("status", "completed")

        return {
            "source": "similar_companies_level1",
            "status": status,
            "agent": "similar_companies_level1",
            "payload": result_payload,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _extract_payload(self, trigger: Mapping[str, Any]) -> Mapping[str, Any]:
        payload = trigger.get("payload") if isinstance(trigger, Mapping) else None
        if not isinstance(payload, Mapping):
            raise ValueError(
                "IntLvl1SimilarCompaniesAgent requires a mapping payload in the trigger."
            )
        return payload

    def _normalise_company_name(self, payload: Mapping[str, Any]) -> str:
        candidate = payload.get("company_name") or payload.get("name")
        return normalize_text(candidate)

    def _build_target_context(self, payload: Mapping[str, Any]) -> Dict[str, str]:
        context: Dict[str, str] = {}
        context["company_name"] = (
            payload.get("company_name") or payload.get("name") or ""
        )
        context["company_name_normalised"] = normalize_text(context["company_name"])

        domain = (
            payload.get("domain")
            or payload.get("company_domain")
            or payload.get("website")
            or payload.get("company_website")
        )
        context["domain"] = domain or ""
        context["domain_normalised"] = normalize_text(domain)
        for criteria_field in self._match_config.fields:
            raw_value = payload.get(criteria_field) or payload.get(
                f"company_{criteria_field}"
            )
            context[criteria_field] = raw_value or ""
            context[f"{criteria_field}_normalised"] = normalize_text(raw_value)
        description_tokens = _tokenize(context.get("description_normalised", ""))
        context["description_tokens"] = description_tokens
        return context

    async def _fetch_candidates(self, company_name: str) -> List[Mapping[str, Any]]:
        return await self._integration.list_similar_companies(
            company_name,
            limit=max(self._result_limit * 3, self._result_limit),
            properties=self.HUBSPOT_PROPERTIES,
        )

    def _rank_candidates(
        self,
        candidates: Iterable[Mapping[str, Any]],
        target_context: Mapping[str, str],
    ) -> List[Dict[str, Any]]:
        ranked: List[Dict[str, Any]] = []
        for candidate in candidates:
            prepared = self._prepare_candidate(candidate, target_context)
            if prepared is None:
                continue
            ranked.append(prepared)

        ranked.sort(
            key=lambda item: (
                -item["score"],
                item["sort_key"],
            )
        )

        for item in ranked:
            item.pop("sort_key", None)

        return ranked

    def _prepare_candidate(
        self,
        candidate: Mapping[str, Any],
        target_context: Mapping[str, str],
    ) -> Optional[Dict[str, Any]]:
        properties = (
            candidate.get("properties") if isinstance(candidate, Mapping) else None
        )
        if not isinstance(properties, Mapping):
            return None

        candidate_name = properties.get("name")
        normalised_name = normalize_text(candidate_name)
        if not normalised_name:
            return None

        target_name = target_context.get("company_name_normalised", "")
        candidate_domain_value = properties.get("domain") or properties.get("website")
        candidate_domain_normalised = normalize_text(candidate_domain_value)
        target_domain = target_context.get("domain_normalised", "")

        if target_name and normalised_name == target_name:
            if target_domain and candidate_domain_normalised:
                if candidate_domain_normalised == target_domain:
                    return None
            else:
                return None

        match_score, matched_fields = self._calculate_score(
            properties, target_context, normalised_name
        )

        sort_key = (
            normalize_text(candidate_name),
            normalize_text(candidate.get("id")),
        )

        domain = candidate_domain_value or ""

        return {
            "id": candidate.get("id"),
            "name": candidate_name,
            "domain": domain,
            "score": round(match_score, 6),
            "matching_fields": matched_fields,
            "properties": dict(properties),
            "sort_key": sort_key,
        }

    def _calculate_score(
        self,
        properties: Mapping[str, Any],
        target_context: Mapping[str, str],
        candidate_name_normalised: str,
    ) -> Tuple[float, List[str]]:
        score = 0.0
        matched_fields: List[str] = []

        target_name = target_context.get("company_name_normalised", "")
        if target_name and candidate_name_normalised == target_name:
            score += self._match_config.weights.get("name", 0.0)
            matched_fields.append("name")

        for criteria_field in self._match_config.fields:
            candidate_value = properties.get(criteria_field)
            normalised_candidate_value = normalize_text(candidate_value)
            target_value = target_context.get(f"{criteria_field}_normalised", "")
            weight = self._match_config.weights.get(criteria_field, 1.0)

            if not target_value or not normalised_candidate_value:
                continue

            if criteria_field == "description":
                overlap_score = self._description_overlap(
                    normalised_candidate_value,
                    target_context.get("description_tokens", []),
                )
                if overlap_score > 0:
                    score += weight * overlap_score
                    matched_fields.append(criteria_field)
            elif normalised_candidate_value == target_value:
                score += weight
                matched_fields.append(criteria_field)

        matched_fields = sorted(set(matched_fields))

        return score, matched_fields

    def _description_overlap(
        self,
        candidate_description: str,
        target_tokens: Sequence[str],
    ) -> float:
        candidate_tokens = _tokenize(candidate_description)
        if not candidate_tokens or not target_tokens:
            return 0.0

        candidate_set = set(candidate_tokens)
        target_set = set(target_tokens)
        overlap = candidate_set & target_set
        if not overlap:
            return 0.0

        denominator = max(len(target_set), 1)
        return len(overlap) / denominator

    def _persist_artifact(
        self,
        payload: Mapping[str, Any],
        *,
        run_id: Optional[str],
        event_id: Optional[str],
    ) -> Path:
        run_identifier = self._normalise_identifier(run_id)
        if not run_identifier:
            run_identifier = self._timestamp_token(prefix="run")

        run_dir = self._artifact_root / run_identifier
        run_dir.mkdir(parents=True, exist_ok=True)

        event_identifier = self._normalise_identifier(event_id)
        if not event_identifier:
            event_identifier = self._timestamp_token(prefix="event")

        filename = f"similar_companies_level1_{event_identifier}.json"
        artifact_path = run_dir / filename

        atomic_write_json(artifact_path, payload)

        return artifact_path

    @staticmethod
    def _normalise_identifier(value: Optional[str]) -> str:
        if not value:
            return ""

        allowed = {"-", "_"}
        sanitised = "".join(
            character for character in value if character.isalnum() or character in allowed
        )
        return sanitised.strip("._")

    @staticmethod
    def _timestamp_token(*, prefix: str) -> str:
        return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"


__all__ = ["IntLvl1SimilarCompaniesAgent"]
