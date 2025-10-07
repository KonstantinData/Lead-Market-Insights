import json
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
def hubspot_stub():
    return SimpleNamespace(
        lookup_company_with_attachments=AsyncMock(
            return_value={"company": None, "attachments": []}
        )
    )


@pytest.fixture
def agent(config, workflow_logs, hubspot_stub):
    return InternalResearchAgent(
        config=config,
        workflow_log_manager=workflow_logs,
        email_agent=MagicMock(),
        internal_search_runner=lambda trigger: {"payload": {}},
        hubspot_integration=hubspot_stub,
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
async def test_run_includes_crm_lookup(agent, hubspot_stub, workflow_logs):
    hubspot_stub.lookup_company_with_attachments.return_value = {
        "company": {"id": "123"},
        "attachments": [{"id": "a1"}],
    }

    trigger = {
        "payload": {
            "company_name": "ACME",
            "company_domain": "acme.example",
        }
    }

    result = await agent.run(trigger)
    lookup = result["payload"]["crm_lookup"]

    assert lookup["company_in_crm"] is True
    assert lookup["attachments_in_crm"] is True
    assert lookup["requires_dossier"] is False
    assert lookup["attachment_count"] == 1

    assert any(entry["step"] == "crm_lookup_completed" for entry in workflow_logs.records)


@pytest.mark.asyncio
async def test_lookup_crm_company_handles_missing_domain(agent, workflow_logs):
    summary = await agent._lookup_crm_company({}, "run-x", "evt-x")

    assert summary["company_in_crm"] is False
    assert summary["attachments_in_crm"] is False
    assert summary["requires_dossier"] is True
    assert any(entry["step"] == "crm_lookup_skipped" for entry in workflow_logs.records)


@pytest.mark.asyncio
async def test_lookup_crm_company_handles_integration_failure(
    agent, hubspot_stub, workflow_logs
):
    hubspot_stub.lookup_company_with_attachments.side_effect = RuntimeError("boom")

    summary = await agent._lookup_crm_company(
        {"company_domain": "example.com"}, "run-y", "evt-y"
    )

    assert summary["company_in_crm"] is False
    assert summary["attachments_in_crm"] is False
    assert summary["requires_dossier"] is True
    assert any(entry["step"] == "crm_lookup_failed" for entry in workflow_logs.records)


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


def test_persist_crm_match_artifact_writes_full_payload(agent):
    payload = {
        "company_name": "Hooli",
        "company_domain": "hooli.com",
    }
    crm_lookup = {
        "company_in_crm": True,
        "attachments_in_crm": False,
        "requires_dossier": True,
        "attachments": [],
        "attachment_count": 0,
        "company": {"id": "123"},
    }

    artifact_path = agent._persist_crm_match_artifact(
        "run-xyz",
        "evt-123",
        payload,
        crm_lookup,
    )

    assert artifact_path
    path_obj = Path(artifact_path)
    assert path_obj.name == "crm_match_evt-123.json"
    contents = json.loads(path_obj.read_text(encoding="utf-8"))
    assert contents["run_id"] == "run-xyz"
    assert contents["event_id"] == "evt-123"
    assert contents["crm_payload"]["company_name"] == "Hooli"
    assert contents["crm_payload"]["company_domain"] == "hooli.com"
    assert contents["crm_payload"]["crm_lookup"] == crm_lookup
    assert contents["crm_payload"]["request_payload"] == payload
    assert "written_at" in contents


def test_persist_crm_match_artifact_handles_missing_event(agent):
    payload = {
        "company_name": "Umbrella",
        "web_domain": "umbrella.example",
    }
    crm_lookup = {"company_in_crm": False, "attachments": []}

    artifact_path = agent._persist_crm_match_artifact(
        "run-xyz",
        None,
        payload,
        crm_lookup,
    )

    assert artifact_path
    path_obj = Path(artifact_path)
    assert path_obj.name.startswith("crm_match_run-xyz_")
    contents = json.loads(path_obj.read_text(encoding="utf-8"))
    assert contents["event_id"] is None
    assert contents["crm_payload"]["company_domain"] == "umbrella.example"


@pytest.mark.asyncio
async def test_run_handles_missing_fields_without_lookup(agent, monkeypatch):
    agent._dispatch_missing_field_reminder = AsyncMock(return_value=True)
    lookup = MagicMock(side_effect=AssertionError("should not be called"))
    agent._internal_search_runner = lookup

    trigger = {"payload": {"company_name": "ACME"}, "creator": "ops"}

    result = await agent.run(trigger)

    assert result["status"] == "AWAIT_REQUESTOR_DETAILS"
    lookup.assert_not_called()
