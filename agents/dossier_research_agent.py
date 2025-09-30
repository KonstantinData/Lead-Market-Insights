"""Agent implementation for producing company dossier research artefacts."""

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional, Sequence
from uuid import uuid4

from agents.factory import register_agent
from agents.interfaces import BaseResearchAgent
from config.config import settings
from utils.datetime_formatting import format_report_datetime


class DossierResearchAgent(BaseResearchAgent):
    """Generate structured research artefacts for company dossiers."""

    #: Required fields expected in the incoming payload to build the dossier.
    REQUIRED_PAYLOAD_FIELDS: Sequence[str] = ("company_name", "company_domain")

    #: Ordered schema definition for the persisted JSON output.
    OUTPUT_FIELD_ORDER: Sequence[str] = (
        "report_type",
        "run_id",
        "event_id",
        "generated_at",
        "company",
        "summary",
        "insights",
        "sources",
        "raw_input",
    )

    #: Ordered schema for the ``company`` section in the output JSON.
    COMPANY_FIELD_ORDER: Sequence[str] = (
        "name",
        "domain",
        "location",
        "industry",
        "description",
    )

    def __init__(
        self,
        *,
        config: Any = settings,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )
        self.output_dir = Path(config.research_artifact_dir) / "dossier_research"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # BaseResearchAgent API
    # ------------------------------------------------------------------
    async def run(self, trigger: Mapping[str, Any]) -> MutableMapping[str, Any]:  # type: ignore[override]
        payload = self._extract_payload(trigger)
        self._validate_payload(payload)

        run_id = self._resolve_run_id(trigger, payload)
        event_id = self._resolve_event_id(trigger, payload, run_id)

        dossier_payload = self._build_dossier_payload(payload, run_id, event_id)
        artifact_path = self._persist_output(run_id, event_id, dossier_payload)

        return OrderedDict(
            (
                ("source", "dossier_research"),
                ("status", "completed"),
                ("agent", "dossier_research"),
                ("artifact_path", str(artifact_path)),
                ("payload", dossier_payload),
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _extract_payload(self, trigger: Mapping[str, Any]) -> MutableMapping[str, Any]:
        candidate = trigger.get("payload") if isinstance(trigger, Mapping) else None
        if not isinstance(candidate, Mapping):
            raise ValueError(
                "DossierResearchAgent requires a mapping payload in the trigger."
            )
        return dict(candidate)

    def _validate_payload(self, payload: Mapping[str, Any]) -> None:
        missing = [field for field in self.REQUIRED_PAYLOAD_FIELDS if field not in payload]
        if missing:
            raise ValueError(
                "Missing required company fields for dossier research: "
                + ", ".join(missing)
            )

    def _resolve_run_id(
        self, trigger: Mapping[str, Any], payload: Mapping[str, Any]
    ) -> str:
        run_id = trigger.get("run_id") or payload.get("run_id")
        if not run_id:
            run_id = uuid4().hex
        return str(run_id)

    def _resolve_event_id(
        self, trigger: Mapping[str, Any], payload: Mapping[str, Any], run_id: str
    ) -> str:
        event_id = (
            trigger.get("event_id")
            or trigger.get("id")
            or payload.get("event_id")
            or payload.get("id")
        )
        if not event_id:
            event_id = run_id
        return str(event_id)

    def _build_dossier_payload(
        self, payload: Mapping[str, Any], run_id: str, event_id: str
    ) -> OrderedDict[str, Any]:
        generated_at = format_report_datetime(datetime.now(timezone.utc))

        company_section = OrderedDict()
        company_values = {
            "name": payload.get("company_name"),
            "domain": payload.get("company_domain"),
            "location": payload.get("company_location") or payload.get("location"),
            "industry": payload.get("company_industry") or payload.get("industry"),
            "description": payload.get("company_description")
            or payload.get("description"),
        }
        for key in self.COMPANY_FIELD_ORDER:
            company_section[key] = company_values.get(key)

        insights = self._normalise_sequence(payload.get("insights"))
        sources = self._normalise_sequence(payload.get("sources"))
        summary = self._normalise_text(
            payload.get("summary")
            or payload.get("company_summary")
            or payload.get("description")
        )

        dossier_payload: "OrderedDict[str, Any]" = OrderedDict()
        for field in self.OUTPUT_FIELD_ORDER:
            if field == "report_type":
                dossier_payload[field] = "Company Detail Research"
            elif field == "run_id":
                dossier_payload[field] = run_id
            elif field == "event_id":
                dossier_payload[field] = event_id
            elif field == "generated_at":
                dossier_payload[field] = generated_at
            elif field == "company":
                dossier_payload[field] = company_section
            elif field == "summary":
                dossier_payload[field] = summary
            elif field == "insights":
                dossier_payload[field] = insights
            elif field == "sources":
                dossier_payload[field] = sources
            elif field == "raw_input":
                dossier_payload[field] = dict(payload)

        return dossier_payload

    def _normalise_sequence(self, values: Optional[Any]) -> list[str]:
        if not values:
            return []
        if isinstance(values, str):
            return [values]
        result: list[str] = []
        for item in values:  # type: ignore[assignment]
            if item is None:
                continue
            result.append(str(item))
        return result

    def _normalise_text(self, value: Optional[Any]) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text

    def _persist_output(
        self, run_id: str, event_id: str, dossier_payload: Mapping[str, Any]
    ) -> Path:
        run_dir = self.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{event_id}_company_detail_research.json"
        artifact_path = run_dir / filename
        artifact_path.write_text(
            json.dumps(dossier_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return artifact_path


register_agent(BaseResearchAgent, "dossier_research")(DossierResearchAgent)

__all__ = ["DossierResearchAgent"]
