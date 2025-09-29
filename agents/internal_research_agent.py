"""Internal research agent implementation registered with the agent factory."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from agents.factory import register_agent
from agents.interfaces import BaseResearchAgent
from agents.internal_company.run import run as internal_company_run
from agents.email_agent import EmailAgent
from config.config import settings
from logs.workflow_log_manager import WorkflowLogManager
from reminders.reminder_escalation import ReminderEscalation

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
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.workflow_log_manager = workflow_log_manager or WorkflowLogManager(
            config.workflow_log_dir
        )
        self._internal_search_runner = internal_search_runner
        self.logger = logger or logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )

        self.research_artifact_dir = Path(config.research_artifact_dir) / "internal_research"
        self.research_artifact_dir.mkdir(parents=True, exist_ok=True)

        self.agent_log_dir = Path(config.agent_log_dir) / "internal_research"
        self.agent_log_dir.mkdir(parents=True, exist_ok=True)
        self._configure_file_logger()

        self.email_agent = email_agent or self._build_email_agent_from_env()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, trigger: Mapping[str, Any]) -> NormalizedPayload:  # type: ignore[override]
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
            return self._handle_missing_fields(
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
        neighbor_artifact = self._write_artifact(
            run_id, "level1_samples.json", samples
        )
        if samples and neighbor_artifact:
            self._log_workflow(
                run_id,
                "neighbor_samples_recorded",
                f"Captured {len(samples)} neighbor samples at {neighbor_artifact}.",
                event_id,
            )

        crm_artifact = self._write_artifact(
            run_id,
            "crm_matching_company.json",
            self._build_crm_matching_payload(payload),
        )
        if crm_artifact:
            self._log_workflow(
                run_id,
                "crm_matching_recorded",
                f"Stored CRM matching details at {crm_artifact}.",
                event_id,
            )

        action, email_status = self._determine_next_action(
            trigger, payload, payload_result, run_id, event_id
        )

        self._log_workflow(
            run_id,
            "completed",
            f"Internal research completed with status {action}.",
            event_id,
            error=None if email_status else "email_delivery_failed"
            if email_status is False
            else None,
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
                "existing_report": bool(payload_result.get("exists")),
                "last_report_date": payload_result.get("last_report_date"),
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
        host = os.getenv("SMTP_HOST")
        port = os.getenv("SMTP_PORT")
        username = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASS")
        sender = os.getenv("SMTP_SENDER") or os.getenv("SMTP_FROM") or username

        if not (host and port and username and password and sender):
            self.logger.info(
                "EmailAgent configuration missing; reminder emails will be skipped."
            )
            return None

        try:
            port_number = int(port)
        except ValueError:
            self.logger.warning("Invalid SMTP_PORT value '%s'; skipping email setup.", port)
            return None

        return EmailAgent(host, port_number, username, password, sender)

    def _clone_payload(self, payload: Optional[Mapping[str, Any]]) -> MutableMapping[str, Any]:
        return dict(payload or {})

    def _normalise_payload(self, payload: MutableMapping[str, Any]) -> None:
        if payload.get("company") and not payload.get("company_name"):
            payload["company_name"] = payload["company"]
        if payload.get("domain") and not payload.get("company_domain"):
            payload["company_domain"] = payload["domain"]
        if not payload.get("creator_email"):
            payload["creator_email"] = payload.get("email")

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

    def _handle_missing_fields(
        self,
        trigger: Mapping[str, Any],
        payload: Mapping[str, Any],
        run_id: str,
        event_id: Optional[str],
        missing_required: Sequence[str],
        missing_optional: Sequence[str],
    ) -> NormalizedPayload:
        company = (
            payload.get("company_name")
            or payload.get("company")
            or "Unknown Company"
        )
        message = (
            f"Missing required fields for {company}: {', '.join(missing_required)}."
        )
        self._log_workflow(run_id, "missing_required_fields", message, event_id)
        self.logger.info(message)

        reminder_sent = self._dispatch_missing_field_reminder(
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

    def _dispatch_missing_field_reminder(
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
        company = payload.get("company_name") or payload.get("company") or "your company"
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
            return bool(reminder.send_reminder(recipient, subject, body))
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

    def _write_artifact(
        self, run_id: str, filename: str, data: Any
    ) -> Optional[str]:
        if not data:
            return None

        run_dir = self.research_artifact_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = run_dir / filename
        with artifact_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        return artifact_path.as_posix()

    def _build_crm_matching_payload(
        self, payload: Mapping[str, Any]
    ) -> List[Dict[str, Any]]:
        company_name = payload.get("company_name") or ""
        company_domain = payload.get("company_domain") or ""
        if not company_name and not company_domain:
            return []

        return [
            {
                "company_name": company_name,
                "company_domain": company_domain,
                "industry_group": payload.get("industry_group"),
                "industry": payload.get("industry"),
                "description": payload.get("description"),
            }
        ]

    def _determine_next_action(
        self,
        trigger: Mapping[str, Any],
        payload: Mapping[str, Any],
        payload_result: Mapping[str, Any],
        run_id: str,
        event_id: Optional[str],
    ) -> tuple[str, Optional[bool]]:
        exists = payload_result.get("exists")
        last_report_date = payload_result.get("last_report_date")

        if exists and last_report_date:
            email_status = self._send_existing_report_email(
                payload,
                run_id,
                event_id,
                last_report_date,
            )
            action = "AWAIT_REQUESTOR_DECISION"
            return action, email_status

        action = "REPORT_REQUIRED"
        self._log_workflow(
            run_id,
            "report_required",
            "No existing dossier found; report creation required.",
            event_id,
        )
        return action, None

    def _send_existing_report_email(
        self,
        payload: Mapping[str, Any],
        run_id: str,
        event_id: Optional[str],
        last_report_date: str,
    ) -> Optional[bool]:
        recipient = payload.get("creator_email")
        if not recipient or not self.email_agent:
            self._log_workflow(
                run_id,
                "existing_report_email_skipped",
                "Existing report email skipped due to configuration.",
                event_id,
                error="email_not_configured" if not self.email_agent else "missing_recipient",
            )
            return None

        company_name = payload.get("company_name") or "the requested company"
        try:
            parsed_last = datetime.fromisoformat(
                str(last_report_date).replace("Z", "+00:00")
            )
            display_date = parsed_last.strftime("%Y-%m-%d")
        except Exception:  # pragma: no cover - defensive formatting
            display_date = str(last_report_date)

        subject = f"Existing research available for {company_name}"
        first_name = recipient.split("@", 1)[0]
        body = (
            f"Hi {first_name},\n\n"
            f"We already have a report for {company_name}.\n"
            f"The latest version is from {display_date}.\n\n"
            "Reply with I USE THE EXISTING to receive the PDF and reference in HubSpot.\n"
            "Reply with NEW REPORT if you need an updated dossier.\n\n"
            "Best regards,\nInternal Research Agent"
        )

        try:
            sent = self.email_agent.send_email(recipient, subject, body)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._log_workflow(
                run_id,
                "existing_report_email_failed",
                "Failed to send existing report notification.",
                event_id,
                error=str(exc),
            )
            return False

        if sent:
            self._log_workflow(
                run_id,
                "existing_report_email_sent",
                f"Existing report email sent to {recipient}.",
                event_id,
            )
        else:
            self._log_workflow(
                run_id,
                "existing_report_email_failed",
                f"Existing report email failed for {recipient}.",
                event_id,
                error="send_failed",
            )
        return bool(sent)

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
