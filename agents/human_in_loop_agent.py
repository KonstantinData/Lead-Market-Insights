import inspect
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Notes:
# HumanInLoopAgent manages human-in-the-loop steps for workflows. It optionally uses a communication backend,
# such as an EmailAgent or chat integration, to interact with event organizers. If no backend is provided,
# the agent falls back to a deterministic simulation for demo/testing.


class HumanInLoopAgent:
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
        print(
            f"Please provide missing info for event {event.get('id', '<unknown>')}: {extracted['info']}"
        )
        # Notes: Simulate human response for demo purposes.
        extracted["info"]["company_name"] = (
            extracted["info"].get("company_name") or "Example Corp"
        )
        extracted["info"]["web_domain"] = (
            extracted["info"].get("web_domain") or "example.com"
        )
        extracted["is_complete"] = True
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
        subject = self._build_subject(event)
        message = self._build_message(event, info)
        payload = {"event": event, "info": info}

        backend_response: Optional[Any] = None
        handler = self._resolve_backend_handler()
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
        details.setdefault("contact", contact)
        details.setdefault("subject", subject)
        details.setdefault("message", message)
        normalized["details"] = details
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
