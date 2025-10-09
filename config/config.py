# ===================================================================
# File: config/config.py
# Purpose: Central configuration for Lead-Market-Insights.
# Implements normalized, typed environment access and directory
# management across all workflow agents.
#
# Architecture:
#   • ADR-0001 – HITL IMAP/SMTP Integration
#   • ADR-0002 – OpenAI Compatibility Shim
#   • ADR-0003 – FileSystem Path Normalization
# ===================================================================

import json
import os
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------
# Environment Access Helpers
# ---------------------------------------------------------------


def _get_env_var(
    key: str, default: Optional[str] = None, aliases: Optional[List[str]] = None
) -> Optional[str]:
    aliases = aliases or []
    for name in [key, *aliases]:
        value = os.getenv(name)
        if value is not None:
            return value.strip()
    return default


def _get_bool_env(
    key: str, default: bool = False, aliases: Optional[List[str]] = None
) -> bool:
    val = _get_env_var(key, None, aliases)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(
    key: str, default: int = 0, aliases: Optional[List[str]] = None
) -> int:
    val = _get_env_var(key, None, aliases)
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _get_path_env(
    key: str, default: Optional[Path] = None, aliases: Optional[List[str]] = None
) -> Path:
    val = _get_env_var(key, None, aliases)
    if val is None:
        return default or Path()
    return Path(os.path.expanduser(val))


# ---------------------------------------------------------------
# Structured Settings Sections
# ---------------------------------------------------------------


@dataclass
class SmtpSettings:
    host: str = field(default_factory=lambda: _get_env_var("SMTP_HOST"))
    port: int = field(default_factory=lambda: _get_int_env("SMTP_PORT", 465))
    username: str = field(
        default_factory=lambda: _get_env_var("SMTP_USER", aliases=["SMTP_USERNAME"])
    )
    password: str = field(
        default_factory=lambda: _get_env_var("SMTP_PASS", aliases=["SMTP_PASSWORD"])
    )
    sender: str = field(
        default_factory=lambda: _get_env_var(
            "SMTP_SENDER", aliases=["MAIL_FROM", "SENDER_EMAIL"]
        )
    )
    secure: bool = field(
        default_factory=lambda: _get_bool_env(
            "SMTP_SMTP_SSL", aliases=["SMTP_SECURE"], default=True
        )
    )
    starttls: bool = field(
        default_factory=lambda: _get_bool_env("SMTP_TLS", default=False)
    )


@dataclass
class ImapSettings:
    host: str = field(default_factory=lambda: _get_env_var("IMAP_HOST"))
    port: int = field(default_factory=lambda: _get_int_env("IMAP_PORT", 993))
    user: str = field(default_factory=lambda: _get_env_var("IMAP_USER"))
    password: str = field(default_factory=lambda: _get_env_var("IMAP_PASS"))
    folder: str = field(default_factory=lambda: _get_env_var("IMAP_FOLDER", "INBOX"))


@dataclass
class HitlSettings:
    enabled: bool = field(
        default_factory=lambda: _get_bool_env("HITL_INBOX_ENABLED", False)
    )
    poll_seconds: float = field(
        default_factory=lambda: float(_get_int_env("HITL_INBOX_POLL_SECONDS", 60))
    )
    timezone: str = field(
        default_factory=lambda: _get_env_var("HITL_TIMEZONE", "Europe/Berlin")
    )
    working_days: str = field(
        default_factory=lambda: _get_env_var("HITL_WORKING_DAYS", "0,1,2,3,4")
    )
    first_deadline: str = field(
        default_factory=lambda: _get_env_var("HITL_FIRST_DEADLINE", "10:00")
    )
    reminder_time: str = field(
        default_factory=lambda: _get_env_var("HITL_REMINDER_TIME", "10:01")
    )
    second_deadline: str = field(
        default_factory=lambda: _get_env_var("HITL_SECOND_DEADLINE", "14:00")
    )
    admin_email: str = field(default_factory=lambda: _get_env_var("HITL_ADMIN_EMAIL"))
    operator_email: str = field(
        default_factory=lambda: _get_env_var("HITL_OPERATOR_EMAIL")
    )
    admin_reminder_period_hours: int = field(
        default_factory=lambda: _get_int_env("HITL_ADMIN_REMINDER_PERIOD_HOURS", 24)
    )
    holidays_region: str = field(
        default_factory=lambda: _get_env_var("HOLIDAYS_REGION", "DE-BW")
    )


@dataclass
class ObservabilitySettings:
    enable_otel: bool = field(
        default_factory=lambda: _get_bool_env("ENABLE_OTEL", True)
    )
    otlp_endpoint: str = field(
        default_factory=lambda: _get_env_var(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"
        )
    )


@dataclass
class OpenAISettings:
    api_key: Optional[str] = field(
        default_factory=lambda: _get_env_var("OPENAI_API_KEY")
    )
    api_base: str = field(
        default_factory=lambda: _get_env_var(
            "OPENAI_API_BASE",
            default="https://api.openai.com/v1",
            aliases=["OPENAI_API_URL"],
        )
    )


@dataclass
class FileSystemSettings:
    """Normalized local storage directories for run history and research artifacts."""

    base_dir: Path = field(default_factory=lambda: Path("log_storage").resolve())
    research_dir: Path = field(init=False)
    artifact_dir: Path = field(init=False)
    workflow_runs_dir: Path = field(init=False)

    def __post_init__(self):
        self.research_dir = self.base_dir / "run_history" / "research"
        self.artifact_dir = self.research_dir / "artifacts"
        self.workflow_runs_dir = self.artifact_dir / "workflow_runs"
        # Ensure directories exist
        for path in [self.research_dir, self.artifact_dir, self.workflow_runs_dir]:
            path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------
# Main Settings Class
# ---------------------------------------------------------------


class Settings:
    def __init__(self):
        self.smtp = SmtpSettings()
        self.imap = ImapSettings()
        self.hitl = HitlSettings()
        self.openai = OpenAISettings()
        self.observability = ObservabilitySettings()
        self.fs = FileSystemSettings()

        # Legacy compatibility shims
        self.openai_api_base = self.openai.api_base
        self.openai_api_key = self.openai.api_key
        self.research_artifact_dir = str(self.fs.artifact_dir)

        # External integrations
        self.hubspot_access_token = _get_env_var("HUBSPOT_ACCESS_TOKEN")
        self.google_calendar_id = _get_env_var("GOOGLE_CALENDAR_ID")
        self.google_token_uri = _get_env_var(
            "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"
        )

    def summary(self) -> Dict[str, Any]:
        return {
            "smtp": {"host": self.smtp.host, "sender": self.smtp.sender},
            "imap": {"host": self.imap.host, "folder": self.imap.folder},
            "fs": {"artifact_dir": str(self.fs.artifact_dir)},
            "openai": {
                "base": self.openai.api_base,
                "key_set": bool(self.openai.api_key),
            },
        }


# ---------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------
settings = Settings()

if __name__ == "__main__":
    print(json.dumps(settings.summary(), indent=2))
