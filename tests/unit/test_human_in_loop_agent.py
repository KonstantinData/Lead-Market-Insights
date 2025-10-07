import asyncio
import json
from types import SimpleNamespace


class DummyEmailAgent:
    def __init__(self) -> None:
        self.calls = []

    def send_email(self, recipient, subject, body, headers=None):
        self.calls.append(
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "headers": headers or {},
            }
        )
        return "msg-123"


class AsyncDummyEmailAgent:
    def __init__(self) -> None:
        self.calls = []

    async def send_email_async(self, recipient, subject, body):
        self.calls.append(
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
            }
        )
        return True


def test_hitl_persistence(tmp_path):
    from agents.human_in_loop_agent import HumanInLoopAgent

    settings = SimpleNamespace(workflow_log_dir=str(tmp_path))
    agent = HumanInLoopAgent(settings_override=settings)

    run_id = "run-test-123"
    agent.persist_pending_request(run_id, {"company": "ACME"})
    file_path = tmp_path / f"{run_id}_hitl.json"
    assert file_path.exists()
    data = json.loads(file_path.read_text())
    assert data["status"] == "pending"
    assert data["context"] == {"company": "ACME"}

    result = agent.apply_decision(run_id, "approved", "ops@example.com", {"note": "ok"})
    assert result["status"] == "approved"
    assert result["actor"] == "ops@example.com"
    assert result["extra"] == {"note": "ok"}


def test_dispatch_request_email_masks_pii(tmp_path):
    from agents.human_in_loop_agent import HumanInLoopAgent

    dummy_email_agent = DummyEmailAgent()
    settings = SimpleNamespace(workflow_log_dir=str(tmp_path))
    agent = HumanInLoopAgent(settings_override=settings)

    run_id = "run-42"
    context = {
        "company_name": "Acme Corp",
        "company_domain": "acme.test",
        "contact_email": "owner@example.com",
        "missing_fields": ["phone", "address"],
    }

    message_id = agent.dispatch_request_email(
        run_id,
        "operator@example.com",
        context,
        dummy_email_agent,
    )

    assert message_id == "msg-123"
    assert dummy_email_agent.calls, "Expected the email agent to be invoked"

    call = dummy_email_agent.calls[0]
    assert call["recipient"] == "operator@example.com"
    assert call["subject"].endswith(run_id)
    assert call["headers"]["X-Run-ID"] == run_id
    assert call["headers"]["X-HITL"] == "1"
    assert "owner@example.com" not in call["body"], "PII should be masked"
    assert "<redacted-email>" in call["body"], "Masked email marker expected"


def test_schedule_reminders_increments_counter(tmp_path):
    from agents.human_in_loop_agent import HumanInLoopAgent

    settings = SimpleNamespace(workflow_log_dir=str(tmp_path))
    agent = HumanInLoopAgent(settings_override=settings)

    run_id = "run-reminder-1"
    agent.persist_pending_request(run_id, {"company_name": "Acme"})

    email_agent = AsyncDummyEmailAgent()

    async def _trigger() -> None:
        agent.schedule_reminders(run_id, "ops@example.com", email_agent)
        await asyncio.sleep(0)

    asyncio.run(_trigger())

    state = json.loads((tmp_path / f"{run_id}_hitl.json").read_text())
    assert state["reminders_sent"] == 1
    assert email_agent.calls
    assert email_agent.calls[0]["recipient"] == "ops@example.com"


def test_schedule_reminders_skips_when_not_pending(tmp_path):
    from agents.human_in_loop_agent import HumanInLoopAgent

    settings = SimpleNamespace(workflow_log_dir=str(tmp_path))
    agent = HumanInLoopAgent(settings_override=settings)

    run_id = "run-reminder-2"
    agent.persist_pending_request(run_id, {"company_name": "Acme"})

    state_path = tmp_path / f"{run_id}_hitl.json"
    state = json.loads(state_path.read_text())
    state["status"] = "approved"
    state_path.write_text(json.dumps(state))

    email_agent = AsyncDummyEmailAgent()

    async def _trigger() -> None:
        agent.schedule_reminders(run_id, "ops@example.com", email_agent)
        await asyncio.sleep(0)

    asyncio.run(_trigger())

    updated = json.loads(state_path.read_text())
    assert updated["reminders_sent"] == 0
    assert not email_agent.calls
