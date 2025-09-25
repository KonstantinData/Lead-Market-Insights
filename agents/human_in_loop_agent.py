import inspect
import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class HumanInLoopAgent:
    def __init__(self, communication_backend: Optional[Any] = None) -> None:
        """Create the HITL agent.

        Parameters
        ----------
        communication_backend:
            A concrete communication client (e.g. ``EmailAgent`` or a Slack
            integration) responsible for contacting the event organiser.  The
            backend is expected to expose either a ``request_confirmation`` or
            ``send_confirmation_request`` method.  When no backend is supplied
            the agent falls back to a deterministic simulation which keeps the
            previous behaviour used in tests and demos.
        """

        self.communication_backend = communication_backend

    def request_info(self, event, extracted):
        """
        Notes:
        - Requests missing info from a human (this is a dummy
        implementation for demonstration).
        - In a real scenario, this could send an email, Slack
        message, or open a web form.
        - Here, it simulates a user providing the missing
        information.
        """
        print(
            f"Please provide missing info for event {event.get('id', '<unknown>')}: {extracted['info']}"
        )
        # Simulate human response for demo purposes:
        extracted["info"]["company_name"] = (
            extracted["info"].get("company_name") or "Example Corp"
        )
        extracted["info"]["web_domain"] = (
            extracted["info"].get("web_domain") or "example.com"
        )
        extracted["is_complete"] = True
        return extracted

    def request_dossier_confirmation(self, event: Dict[str, Any], info: Dict[str, Any]) -> Dict[str, Any]:
        """Ask the organiser whether a dossier should be created for the event.

        The method orchestrates the interaction with the configured
        communication backend and always returns a normalised dictionary that
        the workflow can rely on.  The dictionary contains a boolean flag under
        ``dossier_required`` and a ``details`` payload with contextual
        information (contact details, rendered message, and any backend
        response).
        """

        contact = self._extract_organizer_contact(event)
        subject = self._build_subject(event)
        message = self._build_message(event, info)
        payload = {"event": event, "info": info}

        backend_response: Optional[Any] = None
        handler = self._resolve_backend_handler()
        if handler:
            logger.debug(
                "Sending dossier confirmation request via backend %s", handler
            )
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
        details.setdefault("contact", contact)
        details.setdefault("subject", subject)
        details.setdefault("message", message)
        normalized["details"] = details
        return normalized

    def _resolve_backend_handler(self) -> Optional[Any]:
        if not self.communication_backend:
            return None

        for attr in ("request_confirmation", "send_confirmation_request"):
            if hasattr(self.communication_backend, attr):
                return getattr(self.communication_backend, attr)
        return None

    def _call_backend_handler(self, handler: Any, **kwargs: Any) -> Any:
        signature = inspect.signature(handler)
        if any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        ):
            return handler(**kwargs)

        supported_kwargs = {
            name: value for name, value in kwargs.items() if name in signature.parameters
        }
        return handler(**supported_kwargs)

    def _extract_organizer_contact(self, event: Dict[str, Any]) -> Dict[str, Any]:
        organizer = event.get("organizer") or {}
        creator = event.get("creator") or {}
        email = organizer.get("email") or event.get("organizer_email") or creator.get("email")
        name = (
            organizer.get("displayName")
            or organizer.get("name")
            or creator.get("displayName")
            or creator.get("name")
        )
        phone = organizer.get("phone") or organizer.get("phoneNumber")
        return {"email": email, "name": name, "phone": phone, "raw": organizer or None}

    def _build_subject(self, event: Dict[str, Any]) -> str:
        summary = event.get("summary") or "event"
        return f"Dossier confirmation required for {summary}"

    def _build_message(self, event: Dict[str, Any], info: Dict[str, Any]) -> str:
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

    def _simulate_confirmation(self, contact: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(
            "Simulating dossier confirmation for organiser %s", contact.get("email")
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
        if isinstance(response, dict):
            dossier_required = response.get("dossier_required")
            if dossier_required is None:
                dossier_required = bool(response)
            details = response.get("details")
            if isinstance(details, dict):
                details = dict(details)
            elif details is None:
                details = {
                    key: value for key, value in response.items() if key != "dossier_required"
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
