"""
Parser for HITL replies: first line command + optional key=value lines.
"""
from __future__ import annotations
import re
from typing import Dict, Any
from .contracts import HitlDecision


CMD = re.compile(r"^(APPROVE|APPROVE[D]?|DECLINE[D]?|CHANGE)", re.I)
KV = re.compile(r"^([A-Za-z0-9_\-\.]+)\s*=\s*(.+)$")


# Explanation: parse inbound body to HitlDecision


def parse_hitl_reply(run_id: str, actor: str, body: str) -> HitlDecision:
lines = [l.strip() for l in body.splitlines() if l.strip()]
if not lines:
raise ValueError("Empty reply body")
m = CMD.match(lines[0])
if not m:
raise ValueError("No decision keyword found")
cmd = m.group(1).upper()
canon = "APPROVED" if cmd.startswith("APPROVE") else ("DECLINED" if cmd.startswith("DECLINE") else "CHANGE_REQUESTED")
kv: Dict[str, Any] = {}
for line in lines[1:]:
m2 = KV.match(line)
if m2:
k, v = m2.group(1), m2.group(2)
kv[k] = v
return HitlDecision(run_id=run_id, decision=canon, actor=actor, kv=kv)