"""Simple CRM agent implementation used as the default workflow sink."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from agents.factory import register_agent
from agents.interfaces import BaseCrmAgent

logger = logging.getLogger(__name__)


@register_agent(BaseCrmAgent, "logging_crm", "default", is_default=True)
class LoggingCrmAgent(BaseCrmAgent):
    """Default CRM agent that logs outgoing payloads locally."""

    def send(self, event: Mapping[str, Any], info: Mapping[str, Any]) -> None:
        event_id = event.get("id") if isinstance(event, Mapping) else None
        logger.info("Sending event %s to CRM with info: %s", event_id, dict(info))
