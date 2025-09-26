import inspect
import logging
from typing import Any, Dict, Optional

from agents.factory import register_agent
from agents.interfaces import BaseHumanAgent
from config.config import settings
from utils.audit_log import AuditLog
from utils.pii import mask_pii

logger = logging.getLogger(__name__)

# Notes:
# HumanInLoopAgent manages human-in-the-loop steps for workflows. It optionally uses a communication backend,
# such as an EmailAgent or chat integration, to interact with event organizers. If no backend is provided,
# the agent falls back to a deterministic simulation for demo/testing.


@register_agent(BaseHumanAgent, "human_in_loop", "default", is_default=True)
class HumanInLoopAgent(BaseHumanAgent):
    def __init__(self, communication_backend: Optional[Any] = None) -> None:
        """
        Create the HITL agent.

        Parameters
        ----------
        communication_backend:
            A communication client (e.g. EmailAgent, Slack integration) responsible for
            contacting the event organizer. It should provide either a 'request_confirmation'
            or 'send_confirmation_request' method. If not supplied, the agent uses a
            deterministic simulation (useful for demos and tests).
        """
        self.communication_backend = communication_backend
        self.audit_log: Optional[AuditLog] = None

    def set_audit_log(self, audit_log: AuditLog) -> None:
        """Attach an audit logger used to persist request/response metadata."""

        self.audit_log = audit_log

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

        print(
            "Please provide missing info for event {}: {}".format(
                masked_event.get("id", "<unknown>"), masked_initial_info
            )
        )
        # Notes: Simulate human response for demo purposes.
        extracted["info"]["company_name"] = (
            extracted["info"].get("company_name") or "Example Corp"
        )
        extracted["info"]["web_domain"] = (
            extracted["info"].get("web_domain") or "example.com"
        )
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
        self, event: Dict[str, Any], info: Dict[str, Any]
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
        """
        contact = self._extract_organizer_contact(event)
        masked_event = self._mask_for_message(event)
        masked_info = self._mask_for_message(info)
        subject = self._build_subject(masked_event)
        message = self._build_message(masked_event, masked_info)
        payload = {"event": masked_event, "info": masked_info}

        backend_response: Optional[Any] = None
        handler = self._resolve_backend_handler()
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
                },
            )
        if handler:
            logger.debug("Sending dossier confirmation request via backend %s", handler)
            backend_response = self._call_backend_handler(
                handler,
                contact=contact,
                subject=subject,
                message=message,
                event=event,
                info=info,
                payload=payload,
            )
        else:
            logger.debug(
                "No communication backend configured; using simulated response."
            )
            backend_response = self._simulate_confirmation(contact, payload)

        normalized = self._normalize_response(backend_response)
        details = normalized.get("details", {})
        if not isinstance(details, dict):
            details = {"raw_response": details}
        details.setdefault("contact", masked_contact)
        details.setdefault("subject", subject)
        details.setdefault("message", message)
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
            return "simulation"
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

    def _build_subject(self, event: Dict[str, Any]) -> str:
        """
        Builds the subject line for dossier confirmation requests.
        """
        summary = event.get("summary") or "event"
        return f"Dossier confirmation required for {summary}"

    def _build_message(self, event: Dict[str, Any], info: Dict[str, Any]) -> str:
        """
        Builds the message body for dossier confirmation requests.
        """
        summary = event.get("summary", "Unknown event")
        event_id = event.get("id", "<unknown>")
        lines = [
            f"Event: {summary} ({event_id})",
            "We extracted the following information:",
        ]
        for key, value in info.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("Should we prepare a dossier for this event? Reply yes or no.")
        return "\n".join(lines)

    def _simulate_confirmation(
        self, contact: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulates dossier confirmation (used for tests or when no backend is available).
        """
        logger.info(
            "Simulating dossier confirmation for organiser %s",
            self._mask_for_message(contact).get("email"),
        )
        return {
            "dossier_required": True,
            "details": {
                "simulation": True,
                "reason": "Default simulated approval",
                "contact": contact,
            },
        }

    def _normalize_response(self, response: Any) -> Dict[str, Any]:
        """
        Normalizes the response from a backend or simulation to a standard structure.
        """
        if isinstance(response, dict):
            dossier_required = response.get("dossier_required")
            if dossier_required is None:
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
            return {
                "dossier_required": bool(dossier_required),
                "details": details,
            }

        return {
            "dossier_required": bool(response),
            "details": {"raw_response": response},
        }

    def _mask_for_message(self, payload: Any) -> Any:
        if not getattr(settings, "mask_pii_in_messages", False):
            return payload
        return mask_pii(
            payload,
            whitelist=getattr(settings, "pii_field_whitelist", None),
            mode=getattr(settings, "compliance_mode", "standard"),
        )
