"""Domain validation helpers and HITL triggers."""

from __future__ import annotations

import os
import re
from typing import Optional

from utils.email_agent import send_mail

DOMAIN_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$")


def is_placeholder(domain: Optional[str]) -> bool:
    """Return True when a domain is missing, malformed, or a test domain."""

    if not domain or not isinstance(domain, str):
        return True
    cleaned = domain.strip().lower()
    if not cleaned:
        return True
    return not DOMAIN_RE.match(cleaned) or cleaned.endswith(".test")


def trigger_hitl_if_needed(event_id: str, company_name: str, company_domain: Optional[str]) -> bool:
    """Send a HITL notification when the domain looks like a placeholder."""

    if not is_placeholder(company_domain):
        return False

    operator = os.environ.get("HITL_OPERATOR_EMAIL")
    if not operator:
        raise RuntimeError("HITL_OPERATOR_EMAIL must be configured for HITL notifications")

    subject = f"[HITL] Clarify domain for {company_name or 'unknown company'}"
    body = (
        f"Event {event_id}: placeholder or missing domain ({company_domain}).\n"
        "Please reply with the correct domain."
    )
    send_mail(operator, subject, body)
    return True


__all__ = ["DOMAIN_RE", "is_placeholder", "trigger_hitl_if_needed"]
