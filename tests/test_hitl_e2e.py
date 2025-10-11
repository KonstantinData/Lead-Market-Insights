"""End-to-end validation of the standalone HITL toolkit."""

from __future__ import annotations

from pathlib import Path

from src.hitl.human_in_loop_agent import HumanInLoopAgent
from src.hitl.orchestrator import Orchestrator


class DummySMTP:
    """Collects send calls for assertions without contacting an SMTP server."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        self.sent.append((to, subject, body))
        return "<dummy@local>"


def _write_template(directory: Path, name: str, body: str) -> None:
    template = directory / name
    template.write_text(body, encoding="utf-8")


def test_hitl_approve_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "log_storage").mkdir(parents=True, exist_ok=True)
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    _write_template(
        templates_dir,
        "hitl_request_email.j2",
        "Subject: {{ context.email }}\nBody for {{ run_id }}",
    )
    _write_template(
        templates_dir,
        "hitl_reminder_email.j2",
        "Reminder for {{ run_id }}",
    )
    _write_template(
        templates_dir,
        "hitl_escalation_email.j2",
        "Escalation for {{ run_id }}",
    )

    smtp = DummySMTP()
    hia = HumanInLoopAgent(smtp=smtp)
    orch = Orchestrator()

    run_id = "run-001"
    context = {"email": "ops@example.com", "event": "Launch"}

    message_id = hia.request_approval(
        run_id,
        to="ops@example.com",
        subject="Check dossier",
        context=context,
    )
    assert message_id == "<dummy@local>"
    assert smtp.sent  # message recorded
    assert orch.status(run_id) == "pending"

    decision = orch.apply_inbound(
        run_id,
        actor="ops@example.com",
        raw_body="APPROVE\ncompany_name=ACME",
    )
    assert decision.decision == "APPROVED"
    assert decision.kv["company_name"] == "ACME"
    assert orch.status(run_id) == "APPROVED"

    # Ensure the human agent can persist the decision as part of the audit trail.
    hia.record_decision(decision)

    audit_path = Path("data") / "audit.jsonl"
    assert audit_path.exists()
    store_path = Path("data") / "hitl.jsonl"
    assert store_path.exists()
