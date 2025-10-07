"""Internal research agent implementation registered with the agent factory."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from agents.factory import register_agent
from agents.interfaces import BaseResearchAgent
from agents.internal_company.run import run as internal_company_run
from agents.email_agent import EmailAgent
from integration.hubspot_integration import HubSpotIntegration
from config.config import settings
from logs.workflow_log_manager import WorkflowLogManager
from reminders.reminder_escalation import ReminderEscalation
from utils.crm_artifacts import build_crm_match_payload, persist_crm_match
from utils.persistence import atomic_write_json

NormalizedPayload = Dict[str, Any]


@register_agent(BaseResearchAgent, "internal_research", "default", is_default=True)
class InternalResearchAgent(BaseResearchAgent):
    """Internal research agent coordinating CRM lookups and reminders."""

    DEFAULT_REQUIRED_FIELDS: Sequence[str] = ("company_name", "company_domain")
    DEFAULT_OPTIONAL_FIELDS: Sequence[str] = (
        "industry_group",
        "industry",
        "description",
    )

    def __init__(
        self,
        *,
        config: Any = settings,
        workflow_log_manager: Optional[WorkflowLogManager] = None,
        email_agent: Optional[EmailAgent] = None,
        internal_search_runner=internal_company_run,
        hubspot_integration: Optional[HubSpotIntegration] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.workflow_log_manager = workflow_log_manager or WorkflowLogManager(
            config.workflow_log_dir
        )
        self._internal_search_runner = internal_search_runner
        self._hubspot_integration = hubspot_integration
        self.logger = logger or logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )

        self.research_artifact_dir = (
            Path(config.research_artifact_dir) / "internal_research"
        )
        self.research_artifact_dir.mkdir(parents=True, exist_ok=True)

        self.agent_log_dir = Path(config.agent_log_dir) / "internal_research"
        self.agent_log_dir.mkdir(parents=True, exist_ok=True)
        self._configure_file_logger()

        self.email_agent = email_agent or self._build_email_agent_from_env()
        self._default_signature_text = "Best regards,\nInternal Research Agent"
        self._default_signature_html = "<p>Best regards,<br>Internal Research Agent</p>"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def run(self, trigger: Mapping[str, Any]) -> NormalizedPayload:  # type: ignore[override]
        payload = self._clone_payload(trigger.get("payload"))
        context = str(trigger.get("source") or "")
        self._normalise_payload(payload)

        run_id = self._resolve_run_id(trigger, payload)
        event_id = self._extract_event_id(trigger, payload)

        self._log_workflow(
            run_id,
            "start",
            "Internal research workflow received trigger.",
            event_id,
        )

        missing_required, missing_optional = self._validate_required_fields(
            payload, context
        )

        if missing_required:
            return await self._handle_missing_fields(
                trigger, payload, run_id, event_id, missing_required, missing_optional
            )

        if missing_optional:
            self._log_workflow(
                run_id,
                "missing_optional_fields",
                f"Optional fields missing: {', '.join(missing_optional)}.",
                event_id,
            )

        self._log_workflow(
            run_id,
            "fields_validated",
            "Required company fields present for research run.",
            event_id,
        )

        research_result = self._run_internal_lookup(trigger, run_id, event_id)
        payload_result = research_result.get("payload") or {}

        samples = self._collect_neighbor_samples(payload_result)
        neighbor_artifact = self._write_artifact(run_id, "level1_samples.json", samples)
        if samples and neighbor_artifact:
            self._log_workflow(
                run_id,
                "neighbor_samples_recorded",
                f"Captured {len(samples)} neighbor samples at {neighbor_artifact}.",
                event_id,
            )

        crm_summary = await self._lookup_crm_company(
            payload,
            run_id,
            event_id,
        )

        crm_artifact = self._persist_crm_match_artifact(
            run_id,
            event_id,
            payload,
            crm_summary,
        )
        if crm_artifact:
            self._log_workflow(
                run_id,
                "crm_matching_recorded",
                f"Stored CRM matching details at {crm_artifact}.",
                event_id,
            )

        action = "COMPANY_LOOKUP_COMPLETED"
        self._log_workflow(
            run_id,
            "completed",
            "Internal research completed with CRM lookup.",
            event_id,
        )

        normalized = {
            "source": "internal_research",
            "status": action,
            "agent": "internal_research",
            "creator": trigger.get("creator"),
            "recipient": trigger.get("recipient"),
            "payload": {
                "action": action,
                "level1_samples": samples,
                "crm_lookup": crm_summary,
                "artifacts": {
                    "neighbor_samples": neighbor_artifact,
                    "crm_match": crm_artifact,
                },
            },
        }

        return normalized

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _configure_file_logger(self) -> None:
        log_file = self.agent_log_dir / "internal_research.log"
        handler_exists = any(
            isinstance(handler, logging.FileHandler)
            and getattr(handler, "_internal_research_handler", False)
            for handler in self.logger.handlers
        )
        if not handler_exists:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            setattr(file_handler, "_internal_research_handler", True)
            self.logger.addHandler(file_handler)

        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def _build_email_agent_from_env(self) -> Optional[EmailAgent]:
        config = getattr(self, "config", settings)
        host = getattr(config, "smtp_host", None)
        port = getattr(config, "smtp_port", None)
        username = (
            getattr(config, "smtp_username", None)
            or getattr(config, "smtp_user", None)
        )
        password = getattr(config, "smtp_password", None)
        sender = getattr(config, "smtp_sender", None) or getattr(
            config, "smtp_from", None
        )

        if not (host and port and username and password and sender):
            self.logger.info(
                "EmailAgent configuration missing; reminder emails will be skipped."
            )
            return None

        try:
            port_number = int(port)
        except (TypeError, ValueError):
            self.logger.warning(
                "Invalid SMTP port value %r; skipping email setup.", port
            )
            return None

        return EmailAgent(host, port_number, username, password, sender)

    def _clone_payload(
        self, payload: Optional[Mapping[str, Any]]
    ) -> MutableMapping[str, Any]:
        return dict(payload or {})

    def _normalise_payload(self, payload: MutableMapping[str, Any]) -> None:
        alias_map = {
            "company_name": ("company",),
            "company_domain": ("domain",),
            "creator_email": ("email",),
            "industry_group": (
                "company_industry_group",
                "companyIndustryGroup",
                "industry_group_name",
                "industryGroup",
            ),
            "industry": (
                "company_industry",
                "companyIndustry",
                "industry_name",
                "industryName",
                "company_sector",
                "sector",
            ),
            "description": (
                "company_description",
                "companyDescription",
                "company_overview",
                "companyOverview",
                "overview",
            ),
        }

        for canonical_key, aliases in alias_map.items():
            if payload.get(canonical_key):
                continue
            for alias in aliases:
                value = payload.get(alias)
                if value not in (None, ""):
                    payload[canonical_key] = value
                    break

    def _resolve_run_id(
        self, trigger: Mapping[str, Any], payload: Mapping[str, Any]
    ) -> str:
        run_id = (
            trigger.get("run_id")
            or payload.get("event_id")
            or f"internal-research-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        )
        return str(run_id)

    def _extract_event_id(
        self, trigger: Mapping[str, Any], payload: Mapping[str, Any]
    ) -> Optional[str]:
        return (
            payload.get("event_id")
            or trigger.get("event_id")
            or trigger.get("id")
            or payload.get("id")
        )

    def _validate_required_fields(
        self, payload: Mapping[str, Any], context: str
    ) -> tuple[List[str], List[str]]:
        missing_required = [
            field for field in self.DEFAULT_REQUIRED_FIELDS if not payload.get(field)
        ]
        missing_optional = [
            field for field in self.DEFAULT_OPTIONAL_FIELDS if not payload.get(field)
        ]
        self.logger.info(
            "Validated payload context '%s'. Missing required: %s, missing optional: %s",
            context or "default",
            missing_required,
            missing_optional,
        )
        return missing_required, missing_optional

    async def _handle_missing_fields(
        self,
        trigger: Mapping[str, Any],
        payload: Mapping[str, Any],
        run_id: str,
        event_id: Optional[str],
        missing_required: Sequence[str],
        missing_optional: Sequence[str],
    ) -> NormalizedPayload:
        company = (
            payload.get("company_name") or payload.get("company") or "Unknown Company"
        )
        message = (
            f"Missing required fields for {company}: {', '.join(missing_required)}."
        )
        self._log_workflow(run_id, "missing_required_fields", message, event_id)
        self.logger.info(message)

        reminder_sent = await self._dispatch_missing_field_reminder(
            payload, run_id, event_id, missing_required, missing_optional
        )

        if reminder_sent:
            self._log_workflow(
                run_id,
                "reminder_sent",
                f"Reminder issued to {payload.get('creator_email')} for missing fields.",
                event_id,
            )
        else:
            self._log_workflow(
                run_id,
                "reminder_not_sent",
                "Reminder not sent due to unavailable email configuration.",
                event_id,
                error="email_not_configured",
            )

        return {
            "source": "internal_research",
            "status": "AWAIT_REQUESTOR_DETAILS",
            "agent": "internal_research",
            "creator": trigger.get("creator"),
            "recipient": trigger.get("recipient"),
            "payload": {
                "missing_required": list(missing_required),
                "missing_optional": list(missing_optional),
                "company": company,
            },
        }

    async def _dispatch_missing_field_reminder(
        self,
        payload: Mapping[str, Any],
        run_id: str,
        event_id: Optional[str],
        missing_required: Sequence[str],
        missing_optional: Sequence[str],
    ) -> bool:
        if not self.email_agent:
            return False

        recipient = payload.get("creator_email")
        if not recipient:
            return False

        subject = "Additional details required for research request"
        company = (
            payload.get("company_name") or payload.get("company") or "your company"
        )
        missing_all = list(missing_required) + list(missing_optional)
        formatted_missing = ", ".join(missing_all)
        body = (
            f"Hi,\n\nWe need a bit more information to research {company}."
            f" Please provide the following fields: {formatted_missing}.\n\n"
            "Thank you!"
        )

        reminder = ReminderEscalation(
            self.email_agent,
            workflow_log_manager=self.workflow_log_manager,
            run_id=run_id,
        )
        try:
            return bool(await reminder.send_reminder(recipient, subject, body))
        except Exception as exc:  # pragma: no cover - defensive logging
            self._log_workflow(
                run_id,
                "reminder_exception",
                "Exception occurred while sending reminder.",
                event_id,
                error=str(exc),
            )
            return False

    def _run_internal_lookup(
        self, trigger: Mapping[str, Any], run_id: str, event_id: Optional[str]
    ) -> Mapping[str, Any]:
        try:
            result = self._internal_search_runner(trigger)
            self._log_workflow(
                run_id,
                "internal_lookup_completed",
                "Internal company search completed successfully.",
                event_id,
            )
            return result
        except Exception as exc:  # pragma: no cover - defensive logging
            self._log_workflow(
                run_id,
                "internal_lookup_failed",
                "Internal company search failed.",
                event_id,
                error=str(exc),
            )
            raise

    def _collect_neighbor_samples(
        self, payload_result: Mapping[str, Any]
    ) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        for neighbor in payload_result.get("neighbors", []) or []:
            samples.append(
                {
                    "company_name": neighbor.get("company_name")
                    or neighbor.get("name")
                    or "",
                    "domain": neighbor.get("company_domain")
                    or neighbor.get("domain")
                    or "",
                    "description": neighbor.get("description"),
                    "reason_for_match": "internal industry/description similarity",
                }
            )
        return samples

    def _write_artifact(self, run_id: str, filename: str, data: Any) -> Optional[str]:
        if not data:
            return None

        run_dir = self.research_artifact_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = run_dir / filename
        atomic_write_json(artifact_path, data)
        return artifact_path.as_posix()

    def _persist_crm_match_artifact(
        self,
        run_id: str,
        event_id: Optional[str],
        payload: Mapping[str, Any],
        crm_lookup: Mapping[str, Any],
    ) -> Optional[str]:
        if not isinstance(crm_lookup, Mapping):
            return None

        company_name = str(payload.get("company_name") or "")
        company_domain = str(
            payload.get("company_domain")
            or payload.get("web_domain")
            or payload.get("domain")
            or ""
        )

        artifact_payload = build_crm_match_payload(
            run_id=run_id,
            event_id=event_id,
            company_name=company_name,
            company_domain=company_domain,
            crm_lookup=dict(crm_lookup),
        )

        self.logger.info(
            "Persisting CRM match artifact for run %s event %s: %s",
            run_id,
            event_id or "<missing>",
            json.dumps(artifact_payload, ensure_ascii=False, sort_keys=True),
        )

        artifact_path = persist_crm_match(
            self.research_artifact_dir,
            run_id,
            event_id,
            artifact_payload,
        )
        return artifact_path.as_posix()

    async def _lookup_crm_company(
        self,
        payload: Mapping[str, Any],
        run_id: str,
        event_id: Optional[str],
    ) -> Dict[str, Any]:
        domain = payload.get("company_domain") or payload.get("web_domain")
        if not domain:
            self._log_workflow(
                run_id,
                "crm_lookup_skipped",
                "CRM lookup skipped due to missing domain.",
                event_id,
            )
            return {
                "company_in_crm": False,
                "attachments_in_crm": False,
                "requires_dossier": True,
                "attachments": [],
                "company": None,
            }

        integration = self._ensure_hubspot_integration()
        if integration is None:
            self._log_workflow(
                run_id,
                "crm_lookup_skipped",
                "HubSpot integration not configured; skipping CRM lookup.",
                event_id,
                error="integration_unavailable",
            )
            return {
                "company_in_crm": False,
                "attachments_in_crm": False,
                "requires_dossier": True,
                "attachments": [],
                "company": None,
            }

        try:
            lookup = await integration.lookup_company_with_attachments(domain)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._log_workflow(
                run_id,
                "crm_lookup_failed",
                "HubSpot lookup failed.",
                event_id,
                error=str(exc),
            )
            self.logger.exception("HubSpot lookup failed for domain %s", domain)
            return {
                "company_in_crm": False,
                "attachments_in_crm": False,
                "requires_dossier": True,
                "attachments": [],
                "company": None,
            }

        company = lookup.get("company") if isinstance(lookup, Mapping) else None
        attachments = lookup.get("attachments") if isinstance(lookup, Mapping) else []
        if not isinstance(attachments, list):
            attachments = []

        company_in_crm = bool(company)
        attachments_in_crm = bool(attachments)
        requires_dossier = not (company_in_crm and attachments_in_crm)

        message = "Company found in CRM." if company_in_crm else "Company not in CRM."
        if attachments_in_crm:
            message += " Attachments detected."
        else:
            message += " No attachments available."

        self._log_workflow(
            run_id,
            "crm_lookup_completed",
            message,
            event_id,
        )

        return {
            "company_in_crm": company_in_crm,
            "attachments_in_crm": attachments_in_crm,
            "requires_dossier": requires_dossier,
            "attachments": attachments,
            "attachment_count": len(attachments),
            "company": company,
        }

    def _ensure_hubspot_integration(self) -> Optional[HubSpotIntegration]:
        if self._hubspot_integration is not None:
            return self._hubspot_integration

        try:
            self._hubspot_integration = HubSpotIntegration(settings=self.config)
        except EnvironmentError as exc:
            self.logger.info(
                "HubSpot integration unavailable: %s",
                exc,
            )
            self._hubspot_integration = None
        except Exception as exc:  # pragma: no cover - defensive safeguard
            self.logger.exception("Failed to initialise HubSpot integration: %s", exc)
            self._hubspot_integration = None
        return self._hubspot_integration

    def _log_workflow(
        self,
        run_id: str,
        step: str,
        message: str,
        event_id: Optional[str],
        error: Optional[str] = None,
    ) -> None:
        self.workflow_log_manager.append_log(
            run_id,
            step,
            message,
            event_id=event_id,
            error=error,
        )


__all__ = ["InternalResearchAgent"]
