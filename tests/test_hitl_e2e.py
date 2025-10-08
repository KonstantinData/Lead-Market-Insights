# Notes: High-level E2E of HITL path with mocked email I/O
import json
from pathlib import Path
from types import SimpleNamespace


def test_hitl_e2e(tmp_path, monkeypatch):
    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    log_storage_dir = tmp_path / "logs"
    log_storage_dir.mkdir(parents=True, exist_ok=True)
    reminder_dir = log_storage_dir / "reminders"
    reminder_dir.mkdir(parents=True, exist_ok=True)

    smtp = SimpleNamespace(host="h", port=587, username="u", password="p", use_tls=True)
    settings = SimpleNamespace(
        workflow_log_dir=str(workflow_dir),
        log_storage_dir=log_storage_dir,
        hitl_admin_email="ops@example.com",
        hitl_admin_reminder_hours=(24.0,),
        hitl_reminder_delay_hours=0.0,
        hitl_max_retries=1,
        hitl_escalation_email="lead@example.com",
        hitl_reminder_log_dir=reminder_dir,
        smtp=smtp,
    )

    settings.hitl = SimpleNamespace(
        operator_email="ops@example.com",
        admin_email="ops@example.com",
        workflow_log_dir=str(workflow_dir),
        escalation_email="lead@example.com",
        reminder_delay_hours=0.0,
        max_retries=1,
        reminder_log_dir=str(reminder_dir),
    )

    sent = {}

    def fake_send(self, recipient, subject, body, headers=None):
        sent.update({"to": recipient, "subject": subject, "body": body, "headers": headers})
        return "<msg-id>"

    from agents.human_in_loop_agent import HumanInLoopAgent
    from utils.email_agent import EmailAgent

    monkeypatch.setattr(EmailAgent, "send_email", fake_send)

    human_agent = HumanInLoopAgent(settings_override=settings)
    email_agent = EmailAgent("h", 587, "u", "p")

    run_id = "run-e2e-1"
    context = {
        "company_name": "ACME",
        "company_domain": "acme.test",
        "missing_fields": ["web_domain"],
    }

    human_agent.persist_pending_request(run_id, context)
    message_id = human_agent.dispatch_request_email(
        run_id, "ops@example.com", context, email_agent=email_agent
    )

    from human_in_the_loop.reply_parsers import parse_hitl_reply

    decision, extra = parse_hitl_reply("approve")
    state = human_agent.apply_decision(run_id, decision, "ops@example.com", extra)

    hitl_file = Path(settings.workflow_log_dir) / f"{run_id}_hitl.json"
    file_state = json.loads(hitl_file.read_text())

    assert message_id == "<msg-id>"
    assert sent["to"] == "ops@example.com"
    assert file_state["status"] == "approved"
    assert state["status"] == "approved"
    assert state["actor"] == "ops@example.com"
