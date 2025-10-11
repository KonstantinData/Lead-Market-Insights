"""Utilities for parsing organiser HITL replies."""

from __future__ import annotations

import re
from typing import Any, Dict

from .contracts import HitlDecision


CMD = re.compile(r"^(APPROVE|APPROVED|DECLINE|DECLINED|CHANGE)", re.IGNORECASE)
KV = re.compile(r"^([A-Za-z0-9_.\-]+)\s*=\s*(.+)$")


def parse_hitl_reply(run_id: str, actor: str, body: str) -> HitlDecision:
    """Convert a plain-text organiser reply into a :class:`HitlDecision`."""

    lines = [line.strip() for line in (body or "").splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty reply body")

    command_match = CMD.match(lines[0])
    if not command_match:
        raise ValueError("missing decision keyword")

    command = command_match.group(1).upper()
    if command.startswith("APPROVE"):
        decision = "APPROVED"
    elif command.startswith("DECLINE"):
        decision = "DECLINED"
    else:
        decision = "CHANGE_REQUESTED"

    kv: Dict[str, Any] = {}
    for line in lines[1:]:
        match = KV.match(line)
        if match:
            key, value = match.groups()
            kv[key] = value

    return HitlDecision(run_id=run_id, decision=decision, actor=actor, kv=kv)