"""
config/config.py

Purpose
-------
Centralized application settings for Lead-Market-Insights.
- Normalizes environment variable names across legacy and canonical variants.
- Provides strong typing and safe defaults for all subsystems (SMTP/IMAP, Google, HITL).
- Adds `agent_overrides` to avoid AttributeError in MasterWorkflowAgent initialization.

Notes for Maintainers
---------------------
- All code comments and docstrings are in English (repo policy).
- Backward compatibility: multiple env aliases are supported.
- `agent_overrides` can be provided as JSON or as a simple "k=v;k2=v2" string.

Examples
--------
# PowerShell:
$env:AGENT_OVERRIDES = '{"trigger_detection":"openai","email_sender":"smtp"}'

# Bash:
export AGENT_OVERRIDES='trigger_detection=openai;email_sender=smtp'
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Explanation:
# Pydantic v2: BaseSettings kommt aus pydantic_settings, validator → field_validator.
from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic_settings import BaseSettings


# -----------------------------
# Helper functions
# -----------------------------
def _coalesce_env(*names: str, default: Optional[str] = None) -> Optional[str]:
    """Return the first non-empty environment variable from *names* (case-insensitive)."""
    for name in names:
        val = os.getenv(name)
        if val is not None and str(val).strip() != "":
            return val
    return default


def _parse_bool(value: Optional[str], *, default: bool) -> bool:
    if value is None:
        return default
    v = str(value).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _parse_int(value: Optional[str], *, default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def _parse_agent_overrides(value: Optional[str]) -> Dict[str, str]:
    """
    Parse agent overrides from env.

    Supported formats:
      - JSON: {"trigger_detection": "openai", "email_sender": "smtp"}
      - Simple string: "trigger_detection=openai;email_sender=smtp"
    """
    if value is None or str(value).strip() == "":
        return {}

    raw = str(value).strip()
    # Try JSON first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except json.JSONDecodeError:
        pass

    # Fallback: semi-colon separated k=v list
    result: Dict[str, str] = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        if "=" in pair:
            k, v = pair.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                result[k] = v
    return result


# -----------------------------
# Nested SMTP model (optional)
# -----------------------------
class SmtpSettings(BaseModel):
    host: str
    port: int = 587
    username: str
    password: str
    sender: EmailStr
    starttls: bool = True
    ssl: bool = False


# -----------------------------
# Main Settings
# -----------------------------
class Settings(BaseSettings):
    # --- SMTP (canonical; supports legacy env aliases) ---
    smtp_host: str = Field(
        default_factory=lambda: _coalesce_env("SMTP_HOST") or "localhost"
    )
    smtp_port: int = Field(
        default_factory=lambda: _parse_int(_coalesce_env("SMTP_PORT"), default=587)
    )
    smtp_username: str = Field(
        default_factory=lambda: _coalesce_env("SMTP_USER", "SMTP_USERNAME") or ""
    )
    smtp_password: str = Field(
        default_factory=lambda: _coalesce_env("SMTP_PASS", "SMTP_PASSWORD") or ""
    )
    smtp_sender: EmailStr = Field(
        default_factory=lambda: (
            _coalesce_env("SMTP_SENDER", "MAIL_FROM", "SENDER_EMAIL")
            or "no-reply@example.com"
        )
    )
    smtp_starttls: bool = Field(
        default_factory=lambda: _parse_bool(_coalesce_env("SMTP_TLS"), default=True)
    )
    smtp_ssl: bool = Field(
        default_factory=lambda: _parse_bool(
            _coalesce_env("SMTP_SMTP_SSL", "SMTP_SECURE"), default=False
        )
    )

    # Optional nested SMTP block (for adapters expecting an object)
    smtp: Optional[SmtpSettings] = None

    # --- IMAP (optional) ---
    imap_host: Optional[str] = Field(default_factory=lambda: _coalesce_env("IMAP_HOST"))
    imap_port: int = Field(
        default_factory=lambda: _parse_int(_coalesce_env("IMAP_PORT"), default=993)
    )
    imap_user: Optional[str] = Field(default_factory=lambda: _coalesce_env("IMAP_USER"))
    imap_pass: Optional[str] = Field(default_factory=lambda: _coalesce_env("IMAP_PASS"))
    imap_folder: str = Field(
        default_factory=lambda: _coalesce_env("IMAP_FOLDER") or "INBOX"
    )

    # --- Google OAuth / Calendar ---
    google_client_id: Optional[str] = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_CLIENT_ID")
    )
    google_project_id: Optional[str] = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_PROJECT_ID")
    )
    google_client_secret: Optional[str] = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_CLIENT_SECRET")
    )
    google_refresh_token: Optional[str] = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_REFRESH_TOKEN")
    )
    google_auth_uri: str = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_AUTH_URI")
        or "https://accounts.google.com/o/oauth2/auth"
    )
    google_token_uri: str = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_TOKEN_URI", "TOKEN_URI")
        or "https://oauth2.googleapis.com/token"
    )
    google_auth_provider_x509_cert_url: str = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_AUTH_PROVIDER_X509_CERT_URL")
        or "https://www.googleapis.com/oauth2/v1/certs"
    )
    google_redirect_uri: str = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_REDIRECT_URI")
        or "http://localhost"
    )
    google_calendar_id: Optional[str] = Field(
        default_factory=lambda: _coalesce_env("GOOGLE_CALENDAR_ID")
    )

    cal_lookahead_days: int = Field(
        default_factory=lambda: _parse_int(
            _coalesce_env("CAL_LOOKAHEAD_DAYS"), default=14
        )
    )
    cal_lookback_days: int = Field(
        default_factory=lambda: _parse_int(
            _coalesce_env("CAL_LOOKBACK_DAYS"), default=1
        )
    )

    # --- OpenAI / LLM ---
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: _coalesce_env("OPENAI_API_KEY", "OPEN_AI_KEY")
    )
    openai_api_base: Optional[str] = Field(
        default_factory=lambda: _coalesce_env("OPENAI_API_BASE")
    )

    # --- HITL Policy / Scheduling ---
    hitl_timezone: str = Field(
        default_factory=lambda: _coalesce_env("HITL_TIMEZONE") or "Europe/Berlin"
    )
    hitl_working_days: List[int] = Field(
        default_factory=lambda: [
            int(x)
            for x in (_coalesce_env("HITL_WORKING_DAYS") or "0,1,2,3,4").split(",")
        ]
    )
    hitl_first_deadline: str = Field(
        default_factory=lambda: _coalesce_env("HITL_FIRST_DEADLINE") or "10:00"
    )
    hitl_reminder_time: str = Field(
        default_factory=lambda: _coalesce_env("HITL_REMINDER_TIME") or "10:01"
    )
    hitl_second_deadline: str = Field(
        default_factory=lambda: _coalesce_env("HITL_SECOND_DEADLINE") or "14:00"
    )
    hitl_admin_email: Optional[EmailStr] = Field(
        default_factory=lambda: _coalesce_env("HITL_ADMIN_EMAIL")
    )
    hitl_admin_reminder_period_hours: int = Field(
        default_factory=lambda: _parse_int(
            _coalesce_env("HITL_ADMIN_REMINDER_PERIOD_HOURS"), default=24
        )
    )
    holidays_region: str = Field(
        default_factory=lambda: _coalesce_env("HOLIDAYS_REGION") or "DE-BW"
    )
    hitl_operator_email: Optional[EmailStr] = Field(
        default_factory=lambda: _coalesce_env("HITL_OPERATOR_EMAIL")
    )

    # --- Feature flags (inbox polling) ---
    hitl_inbox_enabled: bool = Field(
        default_factory=lambda: _parse_bool(
            _coalesce_env("HITL_INBOX_ENABLED"), default=False
        )
    )
    hitl_inbox_poll_seconds: int = Field(
        default_factory=lambda: _parse_int(
            _coalesce_env("HITL_INBOX_POLL_SECONDS"), default=60
        )
    )

    # --- Observability ---
    enable_otel: bool = Field(
        default_factory=lambda: _parse_bool(_coalesce_env("ENABLE_OTEL"), default=False)
    )
    otel_exporter_otlp_endpoint: Optional[str] = Field(
        default_factory=lambda: _coalesce_env("OTEL_EXPORTER_OTLP_ENDPOINT")
    )

    # --- Artifacts / Storage ---
    research_artifact_dir: str = Field(
        default_factory=lambda: _coalesce_env("RESEARCH_ARTIFACT_DIR")
        or str(Path("log_storage") / "run_history" / "research" / "artifacts")
    )

    # --- Agent overrides (NEW) ---
    #   - Prevents AttributeError in MasterWorkflowAgent
    #   - JSON or "k=v;k2=v2" formats supported
    agent_overrides: Dict[str, str] = Field(default_factory=dict)

    class Config:
        case_sensitive = False

    # --- Post-init normalization (Pydantic v2) ---

    # Explanation:
    # Build/normalize `agent_overrides` from env if missing, before field parsing.
    @field_validator("agent_overrides", mode="before")
    def _parse_agent_overrides_env(cls, v: Any) -> Dict[str, str]:
        if isinstance(v, dict):
            # Ensure all keys/values are strings
            return {str(k): str(v2) for k, v2 in v.items()}

        # If not provided on input, derive from env
        env_val = _coalesce_env("AGENT_OVERRIDES")
        return _parse_agent_overrides(env_val)

    # Explanation:
    # Ensure nested `smtp` object exists AFTER all flat fields are loaded.
    # Using model-level validator allows access to all finalized field values.
    @model_validator(mode="after")
    def _ensure_nested_smtp(self) -> "Settings":
        if self.smtp is None:
            self.smtp = SmtpSettings(
                host=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                sender=self.smtp_sender,
                starttls=self.smtp_starttls,
                ssl=self.smtp_ssl,
            )
        return self


# Singleton settings instance
settings = Settings()

# Convenience alias for consumers importing old symbol names
AppSettings = Settings  # backward compatibility
