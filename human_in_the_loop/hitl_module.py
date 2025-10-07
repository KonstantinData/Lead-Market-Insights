from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging


@dataclass
class HitlDecision:
    # Notes: None means pending; else "approved" | "declined" | "change_requested"
    status: Optional[str]  # None | "approved" | "declined" | "change_requested"
    payload: Dict[str, Any]


class HumanInTheLoop:
    """
    Module for Human-in-the-Loop (HITL) interactions.
    Use this to implement manual approval or validation steps.
    """

    def request_approval(self, data: Dict[str, Any]) -> HitlDecision:
        # Notes: No implicit approval; force pending
        logging.info("HITL: awaiting human approval for payload.")
        return HitlDecision(status=None, payload=data)

    def request_info(self, event: Dict[str, Any], missing_info: Dict[str, Any]) -> HitlDecision:
        # Notes: No auto-fill; request remains pending until human reply arrives
        logging.info("HITL: awaiting human-provided missing information.")
        return HitlDecision(status=None, payload={"event": event, "missing": missing_info})
