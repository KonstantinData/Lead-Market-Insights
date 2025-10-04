from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.internal_research_agent import InternalResearchAgent


class DummyWorkflowLogManager:
    def __init__(self):
        self.records = []

    def append_log(self, run_id, step, message, *, event_id=None, error=None):
        self.records.append(
            {
                "run_id": run_id,
                "step": step,
                "message": message,
                "event_id": event_id,
                "error": error,
            }
        )


@pytest.fixture
def config(tmp_path):
    return SimpleNamespace(
        workflow_log_dir=tmp_path / "workflow",
        research_artifact_dir=tmp_path / "research",
        agent_log_dir=tmp_path / "agent_logs",
        crm_attachment_base_url="https://crm.example.com/base",
    )


@pytest.fixture
def workflow_logs():
    return DummyWorkflowLogManager()


@pytest.fixture
def agent(config, workflow_logs):
    return InternalResearchAgent(
        config=config,
        workflow_log_manager=workflow_logs,
        email_agent=MagicMock(),
        internal_search_runner=lambda trigger: {"payload": {}},
    )


@pytest.mark.asyncio
async def test_handle_missing_fields_logs_and_returns_payload(agent, workflow_logs):
    agent._dispatch_missing_field_reminder = AsyncMock(return_value=True)

    trigger = {"creator": "alice", "recipient": "ops"}
    payload = {"company_name": "ACME", "creator_email": "alice@example.com"}

    result = await agent._handle_missing_fields(
        trigger,
        payload,
        "run-123",
        "evt-9",
        ["company_domain"],
        ["industry"],
    )

    assert result["status"] == "AWAIT_REQUESTOR_DETAILS"
    assert result["payload"]["missing_required"] == ["company_domain"]

    reminder_logs = [
        entry for entry in workflow_logs.records if entry["step"].startswith("reminder")
    ]
    assert {entry["step"] for entry in reminder_logs} == {"reminder_sent"}


@pytest.mark.asyncio
async def test_handle_missing_fields_logs_when_reminder_not_sent(agent, workflow_logs):
    agent._dispatch_missing_field_reminder = AsyncMock(return_value=False)

    trigger = {"creator": "bob"}
    payload = {"company_name": "Globex"}

    await agent._handle_missing_fields(
        trigger,
        payload,
        "run-456",
        None,
        ["company_domain"],
        [],
    )

    reminder_log = workflow_logs.records[-1]
    assert reminder_log["step"] == "reminder_not_sent"
    assert reminder_log["error"] == "email_not_configured"


@pytest.mark.asyncio
async def test_dispatch_missing_field_reminder_uses_escalation(
    agent, monkeypatch, workflow_logs
):
    captured = {}

    class FakeReminder:
        def __init__(self, email_agent, workflow_log_manager, run_id):
            captured["init"] = {
                "email_agent": email_agent,
                "workflow_log_manager": workflow_log_manager,
                "run_id": run_id,
            }

        async def send_reminder(self, recipient, subject, body):
            captured["payload"] = {
                "recipient": recipient,
                "subject": subject,
                "body": body,
            }
            return True

    monkeypatch.setattr(
        "agents.internal_research_agent.ReminderEscalation", FakeReminder
    )

    payload = {
        "creator_email": "owner@example.com",
        "company_name": "Example Corp",
    }

    result = await agent._dispatch_missing_field_reminder(
        payload,
        "run-789",
        "evt-1",
        ["company_domain"],
        ["industry"],
    )

    assert result is True
    assert captured["init"]["workflow_log_manager"] is workflow_logs
    assert "creator_email" not in captured["payload"]["subject"].lower()


@pytest.mark.asyncio
async def test_dispatch_missing_field_reminder_requires_email(agent):
    agent.email_agent = None
    result = await agent._dispatch_missing_field_reminder({}, "run", None, [], [])
    assert result is False


@pytest.mark.asyncio
async def test_determine_next_action_sends_existing_report(agent, workflow_logs):
    agent._send_existing_report_email = AsyncMock(return_value=False)

    payload = {"creator_email": "analyst@example.com"}
    payload_result = {"exists": True, "last_report_date": "2024-01-01T00:00:00Z"}

    action, email_status = await agent._determine_next_action(
        {},
        payload,
        payload_result,
        "run-1",
        "evt-2",
    )

    assert action == "AWAIT_REQUESTOR_DECISION"
    assert email_status is False
    agent._send_existing_report_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_determine_next_action_reports_required(agent, workflow_logs):
    payload_result = {"exists": False}

    action, email_status = await agent._determine_next_action(
        {},
        {},
        payload_result,
        "run-2",
        None,
    )

    assert action == "REPORT_REQUIRED"
    assert email_status is None

    assert any(entry["step"] == "report_required" for entry in workflow_logs.records)


def test_build_crm_portal_link_prefers_nested_payload(agent):
    nested = {
        "payload": {
            "portal_path": "reports/doc.pdf",
        }
    }

    link = agent._build_crm_portal_link({}, nested)
    assert link == "https://crm.example.com/base/reports/doc.pdf"


def test_build_crm_portal_link_accepts_full_url(agent):
    payload_result = {"portal_link": "https://crm.example.com/report"}
    link = agent._build_crm_portal_link(payload_result)
    assert link == "https://crm.example.com/report"


def test_normalise_payload_populates_optional_aliases(agent):
    payload = {
        "company": "ACME Corp",
        "domain": "acme.example",
        "email": "owner@example.com",
        "company_industry_group": "Technology Services",
        "company_industry": "Information Technology",
        "company_description": "Provider of sample solutions.",
    }

    agent._normalise_payload(payload)

    assert payload["company_name"] == "ACME Corp"
    assert payload["company_domain"] == "acme.example"
    assert payload["creator_email"] == "owner@example.com"
    assert payload["industry_group"] == "Technology Services"
    assert payload["industry"] == "Information Technology"
    assert payload["description"] == "Provider of sample solutions."


def test_normalise_payload_supports_additional_aliases(agent):
    payload = {
        "company_name": "Globex",
        "company_domain": "globex.test",
        "company_sector": "Manufacturing",
        "company_overview": "Leading producer of widgets.",
    }

    agent._normalise_payload(payload)

    assert payload["industry"] == "Manufacturing"
    assert payload["description"] == "Leading producer of widgets."


def test_validate_required_fields_with_aliases(agent):
    payload = {
        "company_name": "Initech",
        "company_domain": "initech.io",
        "company_industry_group": "Business Services",
        "company_sector": "Software",
        "company_overview": "Enterprise software solutions.",
    }

    agent._normalise_payload(payload)
    missing_required, missing_optional = agent._validate_required_fields(
        payload, "unit-test"
    )

    assert not missing_required
    assert not missing_optional


def test_build_crm_matching_payload_includes_normalised_fields(agent):
    payload = {
        "company_name": "Hooli",
        "company_domain": "hooli.com",
        "company_industry_group": "Technology",
        "company_industry": "Software",
        "company_description": "Innovative technology conglomerate.",
    }

    agent._normalise_payload(payload)
    crm_payload = agent._build_crm_matching_payload(payload)

    assert crm_payload == [
        {
            "company_name": "Hooli",
            "company_domain": "hooli.com",
            "industry_group": "Technology",
            "industry": "Software",
            "description": "Innovative technology conglomerate.",
        }
    ]


@pytest.mark.asyncio
async def test_run_handles_missing_fields_without_lookup(agent, monkeypatch):
    agent._dispatch_missing_field_reminder = AsyncMock(return_value=True)
    lookup = MagicMock(side_effect=AssertionError("should not be called"))
    agent._internal_search_runner = lookup

    trigger = {"payload": {"company_name": "ACME"}, "creator": "ops"}

    result = await agent.run(trigger)

    assert result["status"] == "AWAIT_REQUESTOR_DETAILS"
    lookup.assert_not_called()


@pytest.mark.asyncio
async def test_run_existing_report_records_artifacts(agent, tmp_path, workflow_logs):
    neighbor_payload = {
        "payload": {
            "exists": True,
            "last_report_date": "2024-01-01T00:00:00Z",
            "neighbors": [{"company_name": "Neighbor Inc", "description": "Match"}],
            "crm_attachment_link": "https://crm.example.com/doc",
        }
    }

    agent._internal_search_runner = MagicMock(return_value=neighbor_payload)
    agent._send_existing_report_email = AsyncMock(return_value=True)

    trigger = {
        "payload": {
            "company_name": "ACME",
            "company_domain": "acme.example",
            "creator_email": "owner@example.com",
        }
    }

    result = await agent.run(trigger)

    artifacts = result["payload"]["artifacts"]
    assert Path(artifacts["neighbor_samples"]).exists()
    assert Path(artifacts["crm_match"]).exists()
    agent._send_existing_report_email.assert_awaited_once()
    assert any(
        entry["step"] == "neighbor_samples_recorded" for entry in workflow_logs.records
    )


@pytest.mark.asyncio
async def test_send_existing_report_email_success(agent, workflow_logs):
    send_email = AsyncMock(return_value=True)
    agent.email_agent = MagicMock(send_email_async=send_email)

    payload = {"creator_email": "owner@example.com", "company_name": "ACME"}
    payload_result = {"crm_attachment_link": "https://crm.example.com/doc"}

    status = await agent._send_existing_report_email(
        payload,
        payload_result,
        "run-77",
        "evt-88",
        "2024-01-01T00:00:00Z",
    )

    assert status is True
    send_email.assert_awaited_once()
    assert any(
        entry["step"] == "existing_report_email_sent" for entry in workflow_logs.records
    )


@pytest.mark.asyncio
async def test_send_existing_report_email_skips_without_recipient(agent, workflow_logs):
    agent.email_agent = MagicMock(send_email_async=AsyncMock())

    status = await agent._send_existing_report_email(
        {},
        {},
        "run-1",
        None,
        "2024-01-01T00:00:00Z",
    )

    assert status is None
    assert any(
        entry["step"] == "existing_report_email_skipped" and entry["error"]
        for entry in workflow_logs.records
    )
