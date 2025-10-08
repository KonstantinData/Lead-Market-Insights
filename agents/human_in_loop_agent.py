import asyncio
import inspect
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from agents.factory import register_agent
from agents.interfaces import BaseHumanAgent
from config.config import settings
from logs.workflow_log_manager import WorkflowLogManager
from reminders.reminder_escalation import ReminderEscalation
from utils.audit_log import AuditLog
from utils.domain_resolution import resolve_company_domain
from utils.pii import mask_pii
from utils.email_agent import EmailAgent
from templates.loader import render_template

logger = logging.getLogger(__name__)


class _AsyncEmailAgentAdapter:
    """Wrap synchronous email clients to expose ``send_email_async``."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    async def send_email_async(self, recipient: str, subject: str, body: str) -> bool:
        loop = asyncio.get_running_loop()

        def _send() -> bool:
            result = self._delegate.send_email(recipient, subject, body)
            if isinstance(result, bool):
                return result
            return bool(result) if result is not None else True

        return await loop.run_in_executor(None, _send)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._delegate, item)


class DossierConfirmationBackendUnavailable(RuntimeError):
    """Raised when dossier confirmation is attempted without a configured backend."""


# Notes:
# HumanInLoopAgent manages human-in-the-loop steps for workflows. It optionally uses a communication backend,
# such as an EmailAgent or chat integration, to interact with event organizers. In production environments a
# backend is required for dossier confirmations; only missing-info flows fall back to deterministic behaviour
# for demos and tests.


@register_agent(BaseHumanAgent, "human_in_loop", "default", is_default=True)
class HumanInLoopAgent(BaseHumanAgent):
    @dataclass
    class DossierReminderPolicy:
        initial_delay: timedelta = timedelta(hours=4)
        follow_up_delays: Sequence[timedelta] = (timedelta(hours=24),)
        escalation_delay: Optional[timedelta] = timedelta(hours=48)
        escalation_recipient: Optional[str] = None
        max_reminders: Optional[int] = None

    def __init__(
        self,
        communication_backend: Optional[Any] = None,
        *,
        reminder_policy: Optional["HumanInLoopAgent.DossierReminderPolicy"] = None,
        settings_override: Optional[Any] = None,
    ) -> None:
        """
        Create the HITL agent.

        Parameters
        ----------
        communication_backend:
            A communication client (e.g. EmailAgent, Slack integration) responsible for
            contacting the event organizer. It should provide either a 'request_confirmation'
            or 'send_confirmation_request' method. When omitted, missing-info flows use a
            deterministic simulation for demos/tests, but dossier confirmations will raise
            an explicit error so production deployments cannot silently auto-approve.
        """
        self.communication_backend = communication_backend
        self.settings = settings if settings_override is None else settings_override
        self.audit_log: Optional[AuditLog] = None
        self.workflow_log_manager: Optional[WorkflowLogManager] = None
        self.run_id: Optional[str] = None
        self.reminder_policy = (
            reminder_policy or self._build_default_reminder_policy()
        )
        self.reminder_escalation: Optional[ReminderEscalation] = None
        self.reminder: Optional[ReminderEscalation] = None
        self._hitl_dir = Path(self.settings.workflow_log_dir)
        self._hitl_dir.mkdir(parents=True, exist_ok=True)
        self._run_directory: Optional[Path] = None
        self._ensure_reminder_escalation()

    def _hitl_path(self, run_id: str) -> Path:
        return self._hitl_dir / f"{run_id}_hitl.json"

    def _build_default_reminder_policy(
        self,
    ) -> "HumanInLoopAgent.DossierReminderPolicy":
        delay_hours = getattr(self.settings, "hitl_reminder_delay_hours", 4.0) or 0.0
        delay_hours = max(float(delay_hours), 0.0)
        base_delay = timedelta(hours=delay_hours)

        max_retries = getattr(self.settings, "hitl_max_retries", 3)
        try:
            reminder_count = int(max_retries)
        except (TypeError, ValueError):
            reminder_count = 3
        reminder_count = max(reminder_count, 0)

        follow_up_count = max(reminder_count - 1, 0)
        follow_up_delays: tuple[timedelta, ...] = tuple(
            base_delay for _ in range(follow_up_count)
        )

        escalation_multiplier = max(reminder_count + 1, 1)
        escalation_delay = base_delay * escalation_multiplier

        escalation_recipient = None
        hitl_settings = getattr(self.settings, "hitl", None)
        if hitl_settings is not None:
            escalation_recipient = getattr(hitl_settings, "escalation_email", None)
        if not escalation_recipient:
            escalation_recipient = getattr(self.settings, "hitl_escalation_email", None)
        if not escalation_recipient:
            escalation_recipient = getattr(self.settings, "hitl_admin_email", None)

        if escalation_recipient is None:
            escalation_delay_value: Optional[timedelta] = escalation_delay
        else:
            escalation_delay_value = escalation_delay

        return self.DossierReminderPolicy(
            initial_delay=base_delay,
            follow_up_delays=follow_up_delays,
            escalation_delay=escalation_delay_value,
            escalation_recipient=escalation_recipient,
            max_reminders=reminder_count,
        )

    def persist_pending_request(self, run_id: str, context: Dict[str, Any]) -> None:
        payload = {
            "run_id": run_id,
            "status": "pending",
            "context": context,
            "reminders_sent": 0,
            "escalated": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        target = self._hitl_path(run_id)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        tmp.replace(target)

    def apply_decision(
        self,
        run_id: str,
        decision: str,
        actor: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        path = self._hitl_path(run_id)
        if path.exists():
            data = json.loads(path.read_text())
        else:
            data = {"run_id": run_id}
        data.update(
            {
                "status": decision,
                "actor": actor,
                "decision_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if extra:
            data["extra"] = extra
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        tmp.replace(path)
        return data

    def dispatch_request_email(
        self,
        run_id: str,
        operator_email: str,
        context: Dict[str, Any],
        email_agent: EmailAgent,
    ) -> str:
        """Send a HITL approval request via email using templated content."""

        safe_context = mask_pii(context)
        template_context = {"run_id": run_id}
        template_context.update({f"context.{key}": value for key, value in safe_context.items()})
        subject = f"HITL Approval Request · {run_id}"
        body = render_template("hitl_request_email.txt", template_context)
        headers = {
            "X-Run-ID": run_id,
            "X-HITL": "1",
            "Reply-To": operator_email,
        }
        return email_agent.send_email(operator_email, subject, body, headers=headers)

    def schedule_reminders(self, run_id: str, operator_email: str, email_agent: Any) -> None:
        """Schedule reminder emails when a HITL request remains pending."""

        path = self._hitl_path(run_id)
        try:
            state = json.loads(path.read_text())
        except FileNotFoundError:
            logger.warning("HITL state missing for run %s; cannot schedule reminder", run_id)
            return
        except json.JSONDecodeError as exc:
            logger.error("Invalid HITL state for run %s: %s", run_id, exc)
            return

        if state.get("status") != "pending":
            return

        async_email_agent = self._ensure_async_email_agent(email_agent)
        self._ensure_reminder_escalation(email_agent=async_email_agent)
        if not self.reminder:
            logger.warning("Reminder service unavailable; skipping HITL reminder for %s", run_id)
            return
        self.reminder.schedule(operator_email, run_id)

    def set_audit_log(self, audit_log: AuditLog) -> None:
        """Attach an audit logger used to persist request/response metadata."""

        self.audit_log = audit_log

    def set_run_context(
        self,
        run_id: str,
        workflow_log_manager: WorkflowLogManager,
        *,
        run_directory: Optional[Path] = None,
    ) -> None:
        """Set the workflow run context used for reminder/escalation logging."""

        self.run_id = run_id
        self.workflow_log_manager = workflow_log_manager
        self._run_directory = Path(run_directory) if run_directory else None
        if self.reminder_escalation:
            self.reminder_escalation.run_id = run_id
            self.reminder_escalation.workflow_log_manager = workflow_log_manager
            if hasattr(self.reminder_escalation, "hitl_dir"):
                self.reminder_escalation.hitl_dir = self._hitl_dir
            if hasattr(self.reminder_escalation, "set_run_directory"):
                self.reminder_escalation.set_run_directory(self._run_directory)
            reminder_log_dir = self._resolve_reminder_log_dir()
            if reminder_log_dir is not None:
                self.reminder_escalation.set_reminder_log_dir(reminder_log_dir)
            self.reminder = self.reminder_escalation
        else:
            self._ensure_reminder_escalation()

    def request_info(
        self, event: Dict[str, Any], extracted: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Requests missing info from a human. This is a dummy implementation for demonstration.
        In a real scenario, this could send an email, Slack message, or open a web form.
        Here, it simulates a user providing the missing information.

        Parameters
        ----------
        event: dict
            The event dictionary (may include id, summary, etc.)
        extracted: dict
            The dictionary containing already extracted info, e.g. {'info': {...}, 'is_complete': False}

        Returns
        -------
        dict
            The extracted dictionary with all info fields completed.
        """
        contact = self._extract_organizer_contact(event)
        masked_event = self._mask_for_message(event)
        masked_initial_info = self._mask_for_message(extracted.get("info", {}))
        requested_fields = [
            key
            for key, value in extracted.get("info", {}).items()
            if value in (None, "")
        ]
        audit_id: Optional[str] = None
        if self.audit_log:
            audit_id = self.audit_log.record(
                event_id=masked_event.get("id"),
                request_type="missing_info",
                stage="request",
                responder=self._format_contact_label(self._mask_for_message(contact)),
                outcome="pending",
                payload={
                    "requested_fields": requested_fields,
                    "event": masked_event,
                    "info": masked_initial_info,
                },
            )

        logger.info(
            "Requesting missing info for event %s: %s",
            masked_event.get("id", "<unknown>"),
            masked_initial_info,
        )
        # Notes: Simulate human response for demo purposes.
        info_payload = dict(extracted.get("info", {}) or {})
        if not info_payload.get("company_name"):
            info_payload["company_name"] = "Example Corp"
        resolved_domain, _ = resolve_company_domain(info_payload, event)
        if not resolved_domain:
            slug = re.sub(r"[^a-z0-9]+", "", info_payload["company_name"].lower())
            slug = slug or "resolved-company"
            resolved_domain = f"{slug}.test"
        info_payload["web_domain"] = resolved_domain
        info_payload["company_domain"] = resolved_domain
        extracted["info"] = info_payload
        extracted["is_complete"] = True

        if self.audit_log:
            masked_completed_info = self._mask_for_message(extracted.get("info", {}))
            response_payload = {
                "info": masked_completed_info,
                "is_complete": extracted.get("is_complete"),
            }
            outcome = "completed" if extracted.get("is_complete") else "incomplete"
            audit_id = self.audit_log.record(
                event_id=masked_event.get("id"),
                request_type="missing_info",
                stage="response",
                responder="simulation",
                outcome=outcome,
                payload=response_payload,
                audit_id=audit_id,
            )
            if audit_id:
                extracted["audit_id"] = audit_id

        return extracted

    def request_dossier_confirmation(
        self,
        event: Dict[str, Any],
        info: Dict[str, Any],
        *,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ask the organizer whether a dossier should be created for the event.
        Orchestrates interaction with the configured communication backend and always
        returns a normalized dictionary with a boolean flag 'dossier_required' and a
        'details' payload with contextual information.

        Parameters
        ----------
        event: dict
            The event dictionary.
        info: dict
            The extracted info dictionary.

        Returns
        -------
        dict
            {
                "dossier_required": bool,
                "details": {
                    ...context info...
                }
            }

        Raises
        ------
        DossierConfirmationBackendUnavailable
            If no communication backend is configured for dossier confirmation requests.
        """
        context_payload: Dict[str, Any] = dict(context or {})
        contact = self._extract_organizer_contact(event)
        masked_event = self._mask_for_message(event)
        masked_info = self._mask_for_message(info)
        masked_context = self._mask_for_message(context_payload)
        subject = self._build_subject(masked_event, context=context_payload)
        message = self._build_message(
            masked_event, masked_info, context=context_payload
        )
        payload = {
            "event": masked_event,
            "info": masked_info,
            "context": masked_context,
        }

        backend_response: Optional[Any] = None
        handler = self._resolve_backend_handler()
        if handler is None:
            error_message = (
                "No communication backend configured for dossier confirmation; "
                "expected a 'request_confirmation' or 'send_confirmation_request' method."
            )
            logger.error(error_message)
            raise DossierConfirmationBackendUnavailable(error_message)

        responder_label = self._backend_label(handler)
        masked_contact = self._mask_for_message(contact)
        contact_label = self._format_contact_label(masked_contact)
        audit_id: Optional[str] = None
        if self.audit_log:
            audit_id = self.audit_log.record(
                event_id=masked_event.get("id"),
                request_type="dossier_confirmation",
                stage="request",
                responder=contact_label,
                outcome="sent",
                payload={
                    "subject": subject,
                    "message": message,
                    "contact": masked_contact,
                    "context": masked_context,
                },
            )
        logger.debug("Sending dossier confirmation request via backend %s", handler)
        backend_response = self._call_backend_handler(
            handler,
            contact=contact,
            subject=subject,
            message=message,
            event=event,
            info=info,
            context=context_payload,
            payload=payload,
        )

        normalized = self._normalize_response(backend_response)
        details = normalized.get("details", {})
        if not isinstance(details, dict):
            details = {"raw_response": details}
        details.setdefault("contact", masked_contact)
        details.setdefault("subject", subject)
        details.setdefault("message", message)
        if "context" not in details:
            details["context"] = masked_context
        normalized["details"] = details

        if self.audit_log:
            outcome = "approved" if normalized.get("dossier_required") else "declined"
            response_payload = {
                "details": normalized.get("details"),
                "response": backend_response,
            }
            audit_id = self.audit_log.record(
                event_id=masked_event.get("id"),
                request_type="dossier_confirmation",
                stage="response",
                responder=responder_label,
                outcome=outcome,
                payload=response_payload,
                audit_id=audit_id,
            )
            if audit_id:
                normalized["audit_id"] = audit_id
        self._post_process_decision(
            normalized,
            audit_id=audit_id,
            contact=contact,
            subject=subject,
            message=message,
            event=event,
            info=info,
        )
        return normalized

    def _resolve_backend_handler(self) -> Optional[Any]:
        """
        Resolves the backend handler for sending confirmation requests.
        Checks for 'request_confirmation' or 'send_confirmation_request'.
        Returns the handler method or None.
        """
        if not self.communication_backend:
            return None

        for attr in ("request_confirmation", "send_confirmation_request"):
            if hasattr(self.communication_backend, attr):
                return getattr(self.communication_backend, attr)
        return None

    def _backend_label(self, handler: Optional[Any]) -> str:
        if handler is None:
            return "unconfigured_backend"
        bound = getattr(handler, "__self__", None)
        if bound is not None:
            return bound.__class__.__name__
        return getattr(handler, "__qualname__", getattr(handler, "__name__", "backend"))

    def _format_contact_label(self, contact: Dict[str, Any]) -> str:
        email = contact.get("email") if isinstance(contact, dict) else None
        name = contact.get("name") if isinstance(contact, dict) else None
        if email and name:
            return f"{name} <{email}>"
        if email:
            return email
        if name:
            return name
        return "organizer"

    def _call_backend_handler(self, handler: Any, **kwargs: Any) -> Any:
        """
        Calls the backend handler with arguments. Supports handlers with **kwargs
        or only selected arguments.
        """
        signature = inspect.signature(handler)
        if any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        ):
            return handler(**kwargs)

        supported_kwargs = {
            name: value
            for name, value in kwargs.items()
            if name in signature.parameters
        }
        return handler(**supported_kwargs)

    def _extract_organizer_contact(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts organizer's contact info from the event dictionary.
        Returns a dict with email, name, phone, and raw organizer data.
        """
        organizer = event.get("organizer") or {}
        creator = event.get("creator") or {}
        email = (
            organizer.get("email")
            or event.get("organizer_email")
            or creator.get("email")
        )
        name = (
            organizer.get("displayName")
            or organizer.get("name")
            or creator.get("displayName")
            or creator.get("name")
        )
        phone = organizer.get("phone") or organizer.get("phoneNumber")
        return {"email": email, "name": name, "phone": phone, "raw": organizer or None}

    def _build_subject(
        self, event: Dict[str, Any], *, context: Optional[Mapping[str, Any]] = None
    ) -> str:
        """Build the subject line for dossier confirmation requests."""

        reason = (context or {}).get("reason") if context else None
        summary = event.get("summary") or "event"

        if reason == "attachments_review":
            return f"Review CRM attachments for {summary}"
        if reason == "soft_trigger_confirmation":
            return f"Confirm dossier requirement for {summary}"
        return f"Dossier confirmation required for {summary}"

    def _build_message(
        self,
        event: Dict[str, Any],
        info: Dict[str, Any],
        *,
        context: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Build the message body for dossier confirmation requests."""

        context = dict(context or {})
        reason = context.get("reason")
        summary = event.get("summary", "Unknown event")
        event_id = event.get("id", "<unknown>")
        lines = [f"Event: {summary} ({event_id})"]

        if context.get("event_start") or context.get("event_end"):
            start = context.get("event_start")
            end = context.get("event_end")
            window = " - ".join(
                [value for value in (str(start or ""), str(end or "")) if value]
            ).strip()
            if window:
                lines.append(f"Scheduled: {window}")

        if reason == "attachments_review":
            attachment_count = context.get("attachment_count")
            if attachment_count is None and isinstance(context.get("attachments"), list):
                attachment_count = len(context.get("attachments"))
            lines.append(
                "We found an existing HubSpot company record with stored attachments."
            )
            lines.append(
                f"Attachments available: {attachment_count or 0} file(s) in the CRM."
            )
        elif reason == "soft_trigger_confirmation":
            lines.append(
                "This meeting was flagged by a soft trigger. We are unsure if a dossier"
            )
            lines.append(
                "is required for preparation and would appreciate your guidance."
            )
        else:
            lines.append("We extracted the following information:")

        if info:
            for key, value in info.items():
                lines.append(f"- {key}: {value}")

        if reason != "attachments_review":
            attachments_flag = context.get("attachments_in_crm")
            if attachments_flag:
                attachment_count = context.get("attachment_count")
                lines.append(
                    f"Existing CRM attachments detected: {attachment_count or 'yes'}."
                )

        lines.append("")
        lines.append(
            "Should we prepare a dossier for this event? Reply yes or no."
        )
        return "\n".join(lines)

    def _normalize_response(self, response: Any) -> Dict[str, Any]:
        """
        Normalizes the response from a backend or simulation to a standard structure.
        """
        if isinstance(response, dict):
            status = response.get("status")
            status_decision_map = {
                "approved": True,
                "declined": False,
                "rejected": False,
                "denied": False,
                "pending": None,
            }
            normalized_status = (
                str(status).strip().lower() if isinstance(status, str) else None
            )

            if "dossier_required" in response:
                dossier_required = response.get("dossier_required")
            elif normalized_status in status_decision_map:
                dossier_required = status_decision_map[normalized_status]
            else:
                dossier_required = bool(response)
            details = response.get("details")
            if isinstance(details, dict):
                details = dict(details)
            elif details is None:
                details = {
                    key: value
                    for key, value in response.items()
                    if key != "dossier_required"
                }
            else:
                details = {"raw_response": details}
            status = response.get("status")
            resolved_status = self._status_from_decision(dossier_required)
            return {
                "dossier_required": dossier_required,
                "details": details,
                "status": status or resolved_status,
            }

        if isinstance(response, bool):
            decision = response
        elif response is None:
            decision = None
        else:
            decision = bool(response)
        return {
            "dossier_required": decision,
            "details": {"raw_response": response},
            "status": self._status_from_decision(decision),
        }

    def _mask_for_message(self, payload: Any) -> Any:
        if not getattr(settings, "mask_pii_in_messages", False):
            return payload
        return mask_pii(
            payload,
            whitelist=getattr(settings, "pii_field_whitelist", None),
            mode=getattr(settings, "compliance_mode", "standard"),
        )

    def shutdown(self) -> None:
        """Cancel any scheduled reminders when the agent is torn down."""

        if self.reminder_escalation:
            self.reminder_escalation.cancel_pending()

    # ------------------------------------------------------------------
    # Reminder orchestration helpers
    # ------------------------------------------------------------------
    def _ensure_reminder_escalation(self, email_agent: Optional[Any] = None) -> None:
        resolved_agent = email_agent or self._resolve_email_agent_for_reminders()
        reminder_log_dir = self._resolve_reminder_log_dir()

        if self.reminder_escalation:
            if resolved_agent is not None:
                self.reminder_escalation.email_agent = resolved_agent
            self.reminder_escalation.workflow_log_manager = self.workflow_log_manager
            self.reminder_escalation.run_id = self.run_id
            if getattr(self.reminder_escalation, "hitl_dir", None) is None:
                self.reminder_escalation.hitl_dir = self._hitl_dir
            elif self.reminder_escalation.hitl_dir != self._hitl_dir:
                self.reminder_escalation.hitl_dir = self._hitl_dir
            if hasattr(self.reminder_escalation, "set_run_directory"):
                self.reminder_escalation.set_run_directory(self._run_directory)
            if reminder_log_dir is not None:
                self.reminder_escalation.set_reminder_log_dir(reminder_log_dir)
            self.reminder = self.reminder_escalation
            return

        self.reminder_escalation = ReminderEscalation(
            resolved_agent,
            workflow_log_manager=self.workflow_log_manager,
            run_id=self.run_id,
            hitl_dir=self._hitl_dir,
            reminder_log_dir=reminder_log_dir,
            run_directory=self._run_directory,
        )
        self.reminder = self.reminder_escalation

    def _resolve_reminder_log_dir(self) -> Optional[Path]:
        hitl_settings = getattr(self.settings, "hitl", None)
        candidate = None
        if hitl_settings is not None:
            candidate = getattr(hitl_settings, "reminder_log_dir", None)
        if not candidate:
            candidate = getattr(self.settings, "hitl_reminder_log_dir", None)
        if not candidate and hasattr(self.settings, "log_storage_dir"):
            candidate = Path(self.settings.log_storage_dir) / "reminders"
        if not candidate:
            return None
        path = Path(candidate)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _resolve_email_agent_for_reminders(self) -> Optional[Any]:
        backend = self.communication_backend
        if backend is None:
            return None
        if hasattr(backend, "send_email_async"):
            return backend
        candidate = getattr(backend, "email_agent", None)
        if candidate is not None and hasattr(candidate, "send_email_async"):
            return candidate
        return None

    def _ensure_async_email_agent(self, email_agent: Any) -> Any:
        if hasattr(email_agent, "send_email_async"):
            return email_agent
        if hasattr(email_agent, "send_email"):
            return _AsyncEmailAgentAdapter(email_agent)
        raise ValueError(
            "email_agent must expose either 'send_email' or 'send_email_async'"
        )

    def _post_process_decision(
        self,
        normalized: Dict[str, Any],
        *,
        audit_id: Optional[str],
        contact: Dict[str, Any],
        subject: str,
        message: str,
        event: Dict[str, Any],
        info: Dict[str, Any],
    ) -> None:
        status = self._determine_status(normalized)
        if status != "pending":
            return

        pending_audit_id = audit_id or normalized.get("audit_id")
        self._log_workflow(
            "hitl_dossier_pending",
            f"Organizer decision pending; reminders initiated [audit_id={pending_audit_id or 'n/a'}]",
        )
        self._initiate_reminder_sequence(
            audit_id=pending_audit_id,
            contact=contact,
            subject=subject,
            message=message,
            event=event,
            info=info,
            details=normalized.get("details", {}),
        )

    def _determine_status(self, payload: Dict[str, Any]) -> str:
        status = payload.get("status")
        if status:
            return str(status)
        decision = payload.get("dossier_required")
        resolved = self._status_from_decision(decision)
        payload["status"] = resolved
        return resolved

    def _status_from_decision(self, decision: Any) -> str:
        if decision is True:
            return "approved"
        if decision is False:
            return "declined"
        return "pending"

    def _initiate_reminder_sequence(
        self,
        *,
        audit_id: Optional[str],
        contact: Dict[str, Any],
        subject: str,
        message: str,
        event: Dict[str, Any],
        info: Dict[str, Any],
        details: Dict[str, Any],
    ) -> None:
        if not contact:
            return
        contact_email = contact.get("email")
        if not contact_email:
            self._log_workflow(
                "hitl_dossier_reminder_skipped",
                f"No organizer email available for reminders [audit_id={audit_id or 'n/a'}]",
            )
            return

        self._ensure_reminder_escalation()
        if not self.reminder_escalation:
            self._log_workflow(
                "hitl_dossier_reminder_skipped",
                f"Reminder escalation not configured for {contact_email} [audit_id={audit_id or 'n/a'}]",
            )
            return

        policy = self.reminder_policy
        if not policy:
            return

        metadata = {
            "audit_id": audit_id or "n/a",
            "contact": contact_email,
            "event_id": event.get("id"),
            "workflow_step": "hitl_dossier",
            "run_id": self.run_id,
        }

        max_reminders = getattr(policy, "max_reminders", None)
        if max_reminders is None:
            follow_count = len(policy.follow_up_delays or ())
            max_reminders = 1 + follow_count
        try:
            max_reminders = int(max_reminders)
        except (TypeError, ValueError):
            max_reminders = 0

        if max_reminders <= 0:
            self._log_workflow(
                "hitl_dossier_reminder_disabled",
                "Reminder scheduling disabled by configuration",
            )
        else:
            cumulative_seconds = 0.0
            attempt_index = 0
            initial_seconds = max(policy.initial_delay.total_seconds(), 0)
            cumulative_seconds += initial_seconds
            attempt_index += 1
            reminder_metadata = {
                **metadata,
                "attempt": attempt_index,
                "max_reminders": max_reminders,
            }
            self.reminder_escalation.schedule_reminder(
                contact_email,
                self._build_reminder_subject(subject),
                self._build_reminder_message(
                    message,
                    attempt=attempt_index,
                    details=details,
                ),
                cumulative_seconds,
                metadata=reminder_metadata,
            )

            for delay in policy.follow_up_delays or ():
                if attempt_index >= max_reminders:
                    break
                cumulative_seconds += max(delay.total_seconds(), 0)
                attempt_index += 1
                reminder_metadata = {
                    **metadata,
                    "attempt": attempt_index,
                    "max_reminders": max_reminders,
                }
                self.reminder_escalation.schedule_reminder(
                    contact_email,
                    self._build_reminder_subject(subject),
                    self._build_reminder_message(
                        message,
                        attempt=attempt_index,
                        details=details,
                    ),
                    cumulative_seconds,
                    metadata=reminder_metadata,
                )

        if policy.escalation_delay is not None:
            escalation_seconds = max(policy.escalation_delay.total_seconds(), 0)
            escalation_recipient = policy.escalation_recipient or contact_email
            escalation_subject = self._build_escalation_subject(subject)
            escalation_body = self._build_escalation_message(
                message,
                contact,
                event,
                info,
                details,
                audit_id=audit_id,
            )
            escalation_metadata = {
                **metadata,
                "escalation_recipient": escalation_recipient,
                "max_reminders": max_reminders,
            }
            self.reminder_escalation.schedule_escalation(
                escalation_recipient,
                escalation_subject,
                escalation_body,
                escalation_seconds,
                metadata=escalation_metadata,
            )

            admin_email = getattr(self.settings, "hitl_admin_email", None)
            admin_interval = self._admin_reminder_interval_hours()
            if admin_email and admin_interval:
                admin_metadata = {
                    **escalation_metadata,
                    "admin_recipient": admin_email,
                }
                try:
                    self.reminder_escalation.schedule_admin_recurring_reminders(
                        admin_email,
                        escalation_subject,
                        escalation_body,
                        admin_interval,
                        metadata=admin_metadata,
                    )
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.exception(
                        "Failed to schedule admin recurring reminders for %s: %s",
                        admin_email,
                        exc,
                    )

    def _build_reminder_subject(self, original_subject: str) -> str:
        return f"Reminder: {original_subject}"

    def _build_reminder_message(
        self,
        original_message: str,
        *,
        attempt: int,
        details: Dict[str, Any],
    ) -> str:
        lines = [
            "Hello,",
            "",
            "This is a friendly reminder about the dossier confirmation request below.",
            f"Reminder attempt {attempt}.",
            "",
            original_message,
        ]
        note = details.get("note") or details.get("reason")
        if note:
            lines.extend(["", f"Previous context: {note}"])
        lines.append("")
        lines.append("Please respond at your earliest convenience.")
        return "\n".join(lines)

    def _admin_reminder_interval_hours(self) -> Optional[float]:
        intervals = getattr(self.settings, "hitl_admin_reminder_hours", ()) or ()
        for value in intervals:
            try:
                interval = float(value)
            except (TypeError, ValueError):  # pragma: no cover - defensive guard
                continue
            if interval > 0:
                return interval
        return None

    def _build_escalation_subject(self, original_subject: str) -> str:
        return f"Escalation: {original_subject}"

    def _build_escalation_message(
        self,
        original_message: str,
        contact: Dict[str, Any],
        event: Dict[str, Any],
        info: Dict[str, Any],
        details: Dict[str, Any],
        *,
        audit_id: Optional[str],
    ) -> str:
        event_id = event.get("id") or "<unknown>"
        company = info.get("company_name") or info.get("web_domain") or "the company"
        lines = [
            "Escalation notice:",
            "",
            "The organizer has not responded to the dossier confirmation request.",
            f"Event ID: {event_id}",
            f"Company: {company}",
            f"Audit trail reference: {audit_id or details.get('audit_id') or 'n/a'}",
            "",
            "Original request message:",
            original_message,
            "",
            "Please review and take the necessary action.",
        ]
        contact_label = self._format_contact_label(contact)
        lines.append(f"Organizer contact: {contact_label}")
        return "\n".join(lines)

    def _log_workflow(self, step: str, message: str) -> None:
        if not (self.workflow_log_manager and self.run_id):
            return
        self.workflow_log_manager.append_log(self.run_id, step, message)
