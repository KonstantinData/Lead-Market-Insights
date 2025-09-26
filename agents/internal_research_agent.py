"""
Internal Research Agent for Agentic-Intelligence-Research

This agent checks if a company already exists in HubSpot using the provided credentials.
It also performs internal similarity search for related companies and handles missing field reminders.

# Notes:
# - This script must NEVER use fake or placeholder data.
# - All actions, reminders, and searches are logged for audit and traceability.
# - The agent is async-ready and can be called in an asynchronous workflow.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.internal_company.run import (
    run as internal_run,
)  # Internal company search logic
from integrations import email_sender  # Email sender integration for reminders
from core.utils import log_step, optional_fields, required_fields

import importlib.util as _ilu

# Load append_jsonl from the logging sink
_JSONL_PATH = Path(__file__).resolve().parent.parent / "a2a_logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

from config.settings import SETTINGS

Normalized = Dict[str, Any]


def _log_agent(
    action: str, domain: str, user_email: str, artifacts: Optional[str] = None
) -> None:
    """Write a log line for this agent."""
    date = datetime.now(timezone.utc)
    path = (
        SETTINGS.logs_dir
        / "agent_internal_research"
        / f"{date:%Y}"
        / f"{date:%m}"
        / f"{date:%d}.jsonl"
    )
    record = {
        "ts_utc": date.isoformat().replace("+00:00", "Z"),
        "agent": "agent_internal_research",
        "action": action,
        "company_domain": domain,
        "user_email": user_email,
    }
    if artifacts:
        record["artifacts"] = artifacts
    path.parent.mkdir(parents=True, exist_ok=True)
    append_jsonl(path, record)


def _log_workflow(record: Dict[str, Any]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = SETTINGS.workflows_dir / f"{ts}_workflow.jsonl"
    data = dict(record)
    data.setdefault(
        "timestamp",
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    )
    SETTINGS.workflows_dir.mkdir(parents=True, exist_ok=True)
    append_jsonl(path, data)


def validate_required_fields(data: dict, context: str) -> tuple[List[str], List[str]]:
    req = required_fields(context)
    opt = optional_fields()
    missing_req = [f for f in req if not data.get(f)]
    missing_opt = [f for f in opt if not data.get(f)]
    return missing_req, missing_opt


def run(trigger: Normalized) -> Normalized:
    """
    Run internal research workflow with missing-field handling.

    # Notes:
    # - Checks for required fields (company_name, company_domain).
    # - If missing, sends reminder to creator via email.
    # - If present, runs internal similarity search and checks HubSpot.
    """
    payload = trigger.get("payload", {})
    context = trigger.get("source", "")

    # Map expected keys for downstream integrations (preserve existing values)
    if not payload.get("company_name") and payload.get("company"):
        payload["company_name"] = payload.get("company")
    if not payload.get("company_domain") and payload.get("domain"):
        payload["company_domain"] = payload.get("domain")
    payload.setdefault("creator_email", payload.get("email") or trigger.get("creator"))

    missing_required, missing_optional = validate_required_fields(payload, context)
    creator_email = payload.get("creator_email") or ""
    creator_name = trigger.get("creator_name")
    company = payload.get("company") or payload.get("company_name") or "Unknown"

    if missing_required:
        log_step(
            "agent_internal_research_skipped",
            "agent_internal_research_skipped",
            {"reason": "missing_company_or_domain", "event": trigger},
        )
        event_title = payload.get("title") or company
        start_raw = payload.get("start")
        end_raw = payload.get("end")
        try:
            start_dt = datetime.fromisoformat(start_raw) if start_raw else None
        except Exception:
            start_dt = None
        try:
            end_dt = datetime.fromisoformat(end_raw) if end_raw else None
        except Exception:
            end_dt = None
        missing = missing_required + missing_optional
        # Create a task in the system for missing fields
        # (Assumed tasks.create_task is available in core.tasks)
        from core import tasks

        task = tasks.create_task(
            trigger=str(payload.get("event_id") or event_title),
            missing_fields=missing,
            employee_email=creator_email or "",
        )
        # Send a reminder email to the creator
        email_sender.send_reminder(
            to=creator_email,
            creator_email=creator_email,
            creator_name=creator_name,
            event_id=payload.get("event_id"),
            event_title=event_title,
            event_start=start_dt,
            event_end=end_dt,
            missing_fields=missing,
            task_id=task.get("id"),
        )
        _log_workflow(
            {
                "status": "missing_fields",
                "agent": "internal_company_research",
                "creator": creator_email,
                "missing": missing_required,
            }
        )
        _log_workflow(
            {
                "status": "reminder_sent",
                "agent": "internal_company_research",
                "to": creator_email,
                "missing": missing_required,
            }
        )
        return {
            "status": "missing_fields",
            "agent": "internal_company_research",
            "creator": trigger.get("creator"),
            "missing": missing_required,
        }

    if missing_optional:
        _log_workflow(
            {
                "status": "missing_optional_fields",
                "agent": "internal_company_research",
                "creator": creator_email,
                "missing": missing_optional,
            }
        )

    company_name = payload.get("company_name") or ""
    company_domain = payload.get("company_domain") or ""

    # Run internal search and HubSpot check
    result = internal_run(trigger)
    payload_res = result.get("payload", {}) or {}

    exists = payload_res.get("exists")
    last_report_date = payload_res.get("last_report_date")
    last_dt: Optional[datetime] = None
    if last_report_date:
        try:
            lr = last_report_date.replace("Z", "+00:00")
            last_dt = datetime.fromisoformat(str(lr))
        except Exception:
            last_dt = None

    samples: List[Dict[str, Any]] = []
    for n in payload_res.get("neighbors", []) or []:
        samples.append(
            {
                "company_name": n.get("company_name") or n.get("name") or "",
                "domain": n.get("company_domain") or n.get("domain") or "",
                "description": n.get("description"),
                "reason_for_match": "internal industry/description similarity",
            }
        )
    if samples:
        SETTINGS.artifacts_dir.mkdir(parents=True, exist_ok=True)
        sample_path = SETTINGS.artifacts_dir / "internal_level1_samples.json"
        with sample_path.open("w", encoding="utf-8") as fh:
            json.dump(samples, fh)
        _log_workflow(
            {
                "event_id": payload.get("event_id"),
                "status": "neighbor_level1_found",
                "details": {"companies": samples},
            }
        )

    if exists and last_report_date:
        action = "AWAIT_REQUESTOR_DECISION"
        first_name = creator_email.split("@", 1)[0]
        if last_dt:
            try:
                date_display = last_dt.strftime("%Y-%m-%d")
            except Exception:
                date_display = last_report_date
        else:
            date_display = last_report_date or "unknown"
        subject = f"Quick check: report for {company_name}"
        body = (
            f"Hi {first_name},\n\n"
            f"Good news — we already have a report for {company_name}.\n"
            f"The latest version is from {date_display}.\n\n"
            f"What should I do next?\n\n"
            f"Reply with I USE THE EXISTING — I'll send you the PDF, and you'll also find it in HubSpot under Company → Attachments.\n\n"
            f"Reply with NEW REPORT — I'll refresh the report, add new findings, and highlight changes.\n\n"
            "Best regards,\nYour Internal Research Agent"
        )
        email_sender.send_email(to=creator_email, subject=subject, body=body)
        _log_workflow(
            {
                "event_id": payload.get("event_id"),
                "status": "email_sent",
                "details": {"to": creator_email},
            }
        )
    else:
        action = "REPORT_REQUIRED"

    artifacts_path: Optional[str] = None
    if any(payload.get(k) for k in ("industry_group", "industry", "description")):
        SETTINGS.artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifacts_file = SETTINGS.artifacts_dir / "matching_crm_companies.json"
        with artifacts_file.open("w", encoding="utf-8") as fh:
            json.dump(
                [
                    {
                        "company_name": company_name,
                        "company_domain": company_domain,
                        "industry_group": payload.get("industry_group"),
                        "industry": payload.get("industry"),
                    }
                ],
                fh,
            )
        artifacts_path = str(artifacts_file)

    _log_agent(action, company_domain, creator_email, artifacts_path)

    return {
        "source": "internal_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {"action": action, "level1_samples": samples},
    }
