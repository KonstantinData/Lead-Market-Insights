"""
E2E test for HITL flow: request → inbound decision → state+audit.
Uses local files and no external services. SMTP is monkeypatched.
"""
from __future__ import annotations
import os
from src.hitl.human_in_loop_agent import HumanInLoopAgent
from src.hitl.orchestrator import Orchestrator


class DummySMTP:
# Explanation: deterministic Message-ID for tests
def send(self, to: str, subject: str, body: str, in_reply_to=None) -> str:
return "<dummy@local>"




def test_hitl_approve_flow(tmp_path, monkeypatch):
# Explanation: bind data and logs to tmp; ensure no cloud
monkeypatch.chdir(tmp_path)
os.makedirs("log_storage", exist_ok=True)
os.makedirs("templates", exist_ok=True)
with open("templates/hitl_request_email.j2", "w", encoding="utf-8") as f:
f.write("Subject: Test\nBody")


hia = HumanInLoopAgent(smtp=DummySMTP())
orch = Orchestrator()


run_id = "r-1"
hia.request_approval(run_id, to="ops@example.com", subject="Check", context={"email": "a@b.com"})
assert orch.status(run_id) == "pending"


dec = orch.apply_inbound(run_id, actor="ops@example.com", raw_body="APPROVE\nfoo=bar")
assert dec.decision == "APPROVED"
assert orch.status(run_id) == "APPROVED"