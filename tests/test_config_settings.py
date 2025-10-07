"""Tests for configuration settings loading."""

import importlib
from pathlib import Path

import pytest


def reload_settings():
    config_module = importlib.import_module("config.config")
    importlib.reload(config_module)
    return config_module.settings


def ensure_base_env(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "calendar@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "mailer")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")


def test_google_calendar_id_required(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

    with pytest.raises(EnvironmentError):
        reload_settings()


def test_log_storage_dir_defaults(monkeypatch):
    ensure_base_env(monkeypatch)
    for key in [
        "LOG_STORAGE_DIR",
        "EVENT_LOG_DIR",
        "WORKFLOW_LOG_DIR",
        "RUN_LOG_DIR",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = reload_settings()

    expected = Path(__file__).resolve().parents[1] / "log_storage" / "run_history"
    assert settings.log_storage_dir == expected
    assert settings.event_log_dir == expected / "events"
    assert settings.workflow_log_dir == expected / "workflows"
    assert settings.run_log_dir == expected / "runs"


def test_log_storage_dir_respects_env(monkeypatch, tmp_path):
    ensure_base_env(monkeypatch)
    target = tmp_path / "custom-root"
    monkeypatch.setenv("LOG_STORAGE_DIR", str(target))
    monkeypatch.setenv("EVENT_LOG_DIR", str(target / "events"))

    settings = reload_settings()

    assert settings.log_storage_dir == target.resolve()
    assert settings.event_log_dir == (target / "events").resolve()


def test_research_and_agent_paths_default(monkeypatch):
    ensure_base_env(monkeypatch)
    for key in [
        "AGENT_LOG_DIR",
        "RESEARCH_ARTIFACT_DIR",
        "RESEARCH_PDF_DIR",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = reload_settings()

    base = Path(__file__).resolve().parents[1] / "log_storage" / "run_history"
    assert settings.agent_log_dir == base / "agents"
    assert settings.research_artifact_dir == base / "research" / "artifacts"
    assert settings.research_pdf_dir == base / "research" / "pdfs"


def test_research_and_agent_paths_override(monkeypatch, tmp_path):
    ensure_base_env(monkeypatch)
    monkeypatch.setenv("AGENT_LOG_DIR", str(tmp_path / "agents"))
    monkeypatch.setenv(
        "RESEARCH_ARTIFACT_DIR", str(tmp_path / "research" / "artifacts")
    )
    monkeypatch.setenv("RESEARCH_PDF_DIR", str(tmp_path / "research" / "pdfs"))

    settings = reload_settings()

    assert settings.agent_log_dir == (tmp_path / "agents").resolve()
    assert (
        settings.research_artifact_dir
        == (tmp_path / "research" / "artifacts").resolve()
    )
    assert settings.research_pdf_dir == (tmp_path / "research" / "pdfs").resolve()


def test_crm_attachment_base_url(monkeypatch):
    ensure_base_env(monkeypatch)
    monkeypatch.delenv("CRM_ATTACHMENT_BASE_URL", raising=False)

    settings = reload_settings()
    assert settings.crm_attachment_base_url == ""

    monkeypatch.setenv(
        "CRM_ATTACHMENT_BASE_URL", "https://crm.example.com/attachments/"
    )
    settings = reload_settings()
    assert settings.crm_attachment_base_url == "https://crm.example.com/attachments/"


def test_compliance_defaults(monkeypatch):
    ensure_base_env(monkeypatch)
    monkeypatch.delenv("COMPLIANCE_MODE", raising=False)
    monkeypatch.delenv("MASK_PII_IN_LOGS", raising=False)
    monkeypatch.delenv("MASK_PII_IN_MESSAGES", raising=False)

    settings = reload_settings()

    assert settings.compliance_mode == "standard"
    assert settings.mask_pii_in_logs is True
    assert settings.mask_pii_in_messages is False


def test_strict_compliance_overrides(monkeypatch):
    ensure_base_env(monkeypatch)
    monkeypatch.setenv("COMPLIANCE_MODE", "strict")
    monkeypatch.delenv("MASK_PII_IN_LOGS", raising=False)
    monkeypatch.delenv("MASK_PII_IN_MESSAGES", raising=False)

    settings = reload_settings()

    assert settings.compliance_mode == "strict"
    assert settings.mask_pii_in_logs is True
    assert settings.mask_pii_in_messages is True


def test_explicit_mask_overrides(monkeypatch):
    ensure_base_env(monkeypatch)
    monkeypatch.setenv("MASK_PII_IN_LOGS", "0")
    monkeypatch.setenv("MASK_PII_IN_MESSAGES", "1")

    settings = reload_settings()

    assert settings.mask_pii_in_logs is False
    assert settings.mask_pii_in_messages is True


def test_custom_whitelist(monkeypatch):
    ensure_base_env(monkeypatch)
    monkeypatch.setenv("PII_FIELD_WHITELIST", "custom_field,AnotherField")

    settings = reload_settings()

    assert "custom_field" in settings.pii_field_whitelist
    assert "anotherfield" in settings.pii_field_whitelist


def test_email_and_hitl_settings_from_env(monkeypatch):
    ensure_base_env(monkeypatch)
    env_values = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "2525",
        "SMTP_USERNAME": "mailer",
        "SMTP_PASSWORD": "secret",
        "SMTP_SENDER": "alerts@example.com",
        "SMTP_SECURE": "0",
        "IMAP_HOST": "imap.example.com",
        "IMAP_PORT": "1993",
        "IMAP_USERNAME": "imap-user",
        "IMAP_PASSWORD": "imap-pass",
        "IMAP_MAILBOX": "support",
        "IMAP_USE_SSL": "false",
        "HITL_OPERATOR_EMAIL": "operator@example.com",
        "HITL_INBOX_POLL_SECONDS": "42.5",
        "HITL_TIMEZONE": "UTC",
        "HITL_ADMIN_EMAIL": "admin@example.com",
        "HITL_ESCALATION_EMAIL": "escalations@example.com",
        "HITL_ADMIN_REMINDER_HOURS": "4, 12, 24",
    }
    for key, value in env_values.items():
        monkeypatch.setenv(key, value)

    settings = reload_settings()

    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_port == 2525
    assert settings.smtp_username == "mailer"
    assert settings.smtp_user == "mailer"
    assert settings.smtp_password == "secret"
    assert settings.smtp_sender == "alerts@example.com"
    assert settings.smtp_secure is False
    assert settings.smtp.host == "smtp.example.com"
    assert settings.smtp.port == 2525
    assert settings.smtp.username == "mailer"
    assert settings.smtp.password == "secret"
    assert settings.smtp.use_tls is False
    assert settings.smtp.sender == "alerts@example.com"

    assert settings.imap_host == "imap.example.com"
    assert settings.imap_port == 1993
    assert settings.imap_username == "imap-user"
    assert settings.imap_user == "imap-user"
    assert settings.imap_password == "imap-pass"
    assert settings.imap_mailbox == "support"
    assert settings.imap_use_ssl is False
    assert settings.imap_ssl is False
    assert settings.inbox.imap_host == "imap.example.com"
    assert settings.inbox.imap_user == "imap-user"
    assert settings.inbox.imap_password == "imap-pass"
    assert settings.inbox.folder == "support"
    assert settings.inbox.port == 1993
    assert settings.inbox.use_ssl is False

    assert settings.hitl_inbox_poll_seconds == pytest.approx(42.5)
    assert settings.hitl_timezone == "UTC"
    assert settings.hitl_admin_email == "admin@example.com"
    assert settings.hitl_escalation_email == "escalations@example.com"
    assert settings.hitl_admin_reminder_hours == (4.0, 12.0, 24.0)
    assert settings.hitl.operator_email == "operator@example.com"
    assert settings.hitl.admin_email == "admin@example.com"
    assert settings.hitl.workflow_log_dir == str(settings.workflow_log_dir)
    assert settings.hitl.escalation_email == "escalations@example.com"


def test_email_and_hitl_defaults(monkeypatch):
    ensure_base_env(monkeypatch)
    for key in [
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_PASS",
        "SMTP_SENDER",
        "SMTP_FROM",
        "SMTP_SECURE",
        "IMAP_HOST",
        "IMAP_PORT",
        "IMAP_USERNAME",
        "IMAP_USER",
        "IMAP_PASSWORD",
        "IMAP_PASS",
        "IMAP_MAILBOX",
        "IMAP_FOLDER",
        "IMAP_SSL",
        "IMAP_USE_SSL",
        "HITL_ADMIN_EMAIL",
        "HITL_ESCALATION_EMAIL",
        "HITL_ADMIN_REMINDER_HOURS",
        "HITL_INBOX_POLL_SECONDS",
        "HITL_TIMEZONE",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="SMTP misconfigured"):
        reload_settings()


def test_invalid_hitl_admin_reminder_hours(monkeypatch):
    ensure_base_env(monkeypatch)
    monkeypatch.setenv("HITL_ADMIN_REMINDER_HOURS", "four")

    with pytest.raises(ValueError):
        reload_settings()
