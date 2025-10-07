# Notes: High-level E2E of HITL path with mocked email I/O
import json
from types import SimpleNamespace


def test_hitl_e2e(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        workflow_log_dir=str(tmp_path),
        smtp=SimpleNamespace(host="h", port=587, username="u", password="p", use_tls=True),
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

    hitl_file = tmp_path / f"{run_id}_hitl.json"
    file_state = json.loads(hitl_file.read_text())

    assert message_id == "<msg-id>"
    assert sent["to"] == "ops@example.com"
    assert file_state["status"] == "approved"
    assert state["status"] == "approved"
    assert state["actor"] == "ops@example.com"
