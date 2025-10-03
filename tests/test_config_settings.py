"""Tests for configuration settings loading."""

import importlib
from pathlib import Path

import pytest


def reload_settings():
    config_module = importlib.import_module("config.config")
    importlib.reload(config_module)
    return config_module.settings


def test_google_calendar_id_required(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

    with pytest.raises(EnvironmentError):
        reload_settings()


def test_log_storage_dir_defaults(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
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
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    target = tmp_path / "custom-root"
    monkeypatch.setenv("LOG_STORAGE_DIR", str(target))
    monkeypatch.setenv("EVENT_LOG_DIR", str(target / "events"))

    settings = reload_settings()

    assert settings.log_storage_dir == target.resolve()
    assert settings.event_log_dir == (target / "events").resolve()


def test_research_and_agent_paths_default(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
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
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
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
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.delenv("CRM_ATTACHMENT_BASE_URL", raising=False)

    settings = reload_settings()
    assert settings.crm_attachment_base_url == ""

    monkeypatch.setenv(
        "CRM_ATTACHMENT_BASE_URL", "https://crm.example.com/attachments/"
    )
    settings = reload_settings()
    assert settings.crm_attachment_base_url == "https://crm.example.com/attachments/"


def test_compliance_defaults(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.delenv("COMPLIANCE_MODE", raising=False)
    monkeypatch.delenv("MASK_PII_IN_LOGS", raising=False)
    monkeypatch.delenv("MASK_PII_IN_MESSAGES", raising=False)

    settings = reload_settings()

    assert settings.compliance_mode == "standard"
    assert settings.mask_pii_in_logs is True
    assert settings.mask_pii_in_messages is False


def test_strict_compliance_overrides(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("COMPLIANCE_MODE", "strict")
    monkeypatch.delenv("MASK_PII_IN_LOGS", raising=False)
    monkeypatch.delenv("MASK_PII_IN_MESSAGES", raising=False)

    settings = reload_settings()

    assert settings.compliance_mode == "strict"
    assert settings.mask_pii_in_logs is True
    assert settings.mask_pii_in_messages is True


def test_explicit_mask_overrides(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("MASK_PII_IN_LOGS", "0")
    monkeypatch.setenv("MASK_PII_IN_MESSAGES", "1")

    settings = reload_settings()

    assert settings.mask_pii_in_logs is False
    assert settings.mask_pii_in_messages is True


def test_custom_whitelist(monkeypatch):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("PII_FIELD_WHITELIST", "custom_field,AnotherField")

    settings = reload_settings()

    assert "custom_field" in settings.pii_field_whitelist
    assert "anotherfield" in settings.pii_field_whitelist
