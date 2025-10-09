# ===================================================================
# File: config/config.py
# Purpose: Central configuration and environment normalization layer
# for the Lead-Market-Insights system. It unifies all runtime
# variables (from .env, YAML, or JSON) into one structured interface
# and provides validation, alias mapping, and type coercion.
#
# This file is fully compatible with ADR-0001 (HITL IMAP/SMTP
# Integration) and adds complete support for HITL, IMAP, SMTP,
# Google OAuth, HubSpot, and Observability.
# ===================================================================

import json
import os
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------
# Environment Access Helpers
# ---------------------------------------------------------------


def _get_env_var(
    key: str, default: Optional[str] = None, aliases: Optional[List[str]] = None
) -> Optional[str]:
    """
    Retrieve an environment variable with alias support.
    The first non-empty alias found will be returned.
    """
    aliases = aliases or []
    for name in [key, *aliases]:
        value = os.getenv(name)
        if value is not None:
            return value.strip()
    return default


def _get_bool_env(
    key: str, default: bool = False, aliases: Optional[List[str]] = None
) -> bool:
    """
    Convert an environment variable to a boolean.
    Accepts variations such as "1", "true", "yes", "on".
    """
    val = _get_env_var(key, None, aliases)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(
    key: str, default: int = 0, aliases: Optional[List[str]] = None
) -> int:
    """
    Convert an environment variable to an integer.
    Returns a default value if conversion fails.
    """
    val = _get_env_var(key, None, aliases)
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _get_float_env(
    key: str, default: float = 0.0, aliases: Optional[List[str]] = None
) -> float:
    """
    Convert an environment variable to a float.
    Returns a default value if conversion fails.
    """
    val = _get_env_var(key, None, aliases)
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _get_path_env(
    key: str, default: Optional[Path] = None, aliases: Optional[List[str]] = None
) -> Path:
    """
    Retrieve a Path-type environment variable and ensure expansion of "~".
    """
    val = _get_env_var(key, None, aliases)
    if val is None:
        return default or Path()
    return Path(os.path.expanduser(val))


# ---------------------------------------------------------------
# Structured Settings Sections (Dataclasses)
# ---------------------------------------------------------------


@dataclass
class SmtpSettings:
    """SMTP email transport configuration."""

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
    """IMAP mailbox polling configuration."""

    host: str = field(default_factory=lambda: _get_env_var("IMAP_HOST"))
    port: int = field(default_factory=lambda: _get_int_env("IMAP_PORT", 993))
    user: str = field(default_factory=lambda: _get_env_var("IMAP_USER"))
    password: str = field(default_factory=lambda: _get_env_var("IMAP_PASS"))
    folder: str = field(default_factory=lambda: _get_env_var("IMAP_FOLDER", "INBOX"))


@dataclass
class HitlSettings:
    """Human-in-the-Loop configuration and scheduling."""

    enabled: bool = field(
        default_factory=lambda: _get_bool_env("HITL_INBOX_ENABLED", False)
    )
    poll_seconds: float = field(
        default_factory=lambda: _get_float_env("HITL_INBOX_POLL_SECONDS", 60.0)
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
    """OpenTelemetry and monitoring configuration."""

    enable_otel: bool = field(
        default_factory=lambda: _get_bool_env("ENABLE_OTEL", True)
    )
    otlp_endpoint: str = field(
        default_factory=lambda: _get_env_var(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"
        )
    )


# ---------------------------------------------------------------
# Main Settings Class
# ---------------------------------------------------------------


class Settings:
    """
    Global configuration container that aggregates all sections.
    Provides YAML/JSON override support and a consistent programmatic interface.
    """

    def __init__(self):
        # Load sub-config sections
        self.smtp = SmtpSettings()
        self.imap = ImapSettings()
        self.hitl = HitlSettings()
        self.observability = ObservabilitySettings()

        # Additional integrations
        self.hubspot_access_token: str = _get_env_var("HUBSPOT_ACCESS_TOKEN")
        self.hubspot_client_secret: str = _get_env_var("HUBSPOT_CLIENT_SECRET")
        self.hubspot_scopes: str = _get_env_var("HUBSPOT_SCOPES")

        self.google_client_id: str = _get_env_var("GOOGLE_CLIENT_ID")
        self.google_project_id: str = _get_env_var("GOOGLE_PROJECT_ID")
        self.google_client_secret: str = _get_env_var("GOOGLE_CLIENT_SECRET")
        self.google_refresh_token: str = _get_env_var("GOOGLE_REFRESH_TOKEN")
        self.google_auth_uri: str = _get_env_var(
            "GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"
        )
        self.google_token_uri: str = _get_env_var(
            "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"
        )
        self.google_auth_provider_cert_url: str = _get_env_var(
            "GOOGLE_AUTH_PROVIDER_X509_CERT_URL",
            "https://www.googleapis.com/oauth2/v1/certs",
        )
        self.google_redirect_uri: str = _get_env_var(
            "GOOGLE_REDIRECT_URI", "http://localhost"
        )
        self.google_calendar_id: str = _get_env_var("GOOGLE_CALENDAR_ID")

        # Load any YAML/JSON overrides from ./config/local_settings.yaml or .json
        self._load_local_overrides()

    # -----------------------------------------------------------
    # Local Config Loader
    # -----------------------------------------------------------
    def _load_local_overrides(self):
        """
        Load YAML or JSON overrides from the config/ directory if present.
        These files can override any environment variable-based defaults.
        """
        override_files = [
            Path("config/local_settings.yaml"),
            Path("config/local_settings.json"),
        ]
        for f in override_files:
            if f.exists():
                try:
                    logging.info(f"[Config] Loading local override file: {f}")
                    if f.suffix == ".yaml":
                        with open(f, "r", encoding="utf-8") as stream:
                            overrides = yaml.safe_load(stream) or {}
                    else:
                        overrides = json.loads(f.read_text(encoding="utf-8"))
                    for k, v in overrides.items():
                        setattr(self, k, v)
                    logging.info("[Config] Local configuration overrides applied.")
                except Exception as e:
                    logging.warning(f"[Config] Failed to load local config {f}: {e}")

    # -----------------------------------------------------------
    # Representation
    # -----------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        """Return a redacted summary of critical settings for debugging."""
        return {
            "smtp": {
                "host": self.smtp.host,
                "port": self.smtp.port,
                "sender": self.smtp.sender,
            },
            "imap": {
                "host": self.imap.host,
                "folder": self.imap.folder,
            },
            "hitl": {
                "enabled": self.hitl.enabled,
                "operator_email": self.hitl.operator_email,
                "poll_seconds": self.hitl.poll_seconds,
            },
            "observability": {
                "enable_otel": self.observability.enable_otel,
                "otlp_endpoint": self.observability.otlp_endpoint,
            },
        }


# ---------------------------------------------------------------
# Global Singleton Instance
# ---------------------------------------------------------------
settings = Settings()


if __name__ == "__main__":
    print("[Config] Current configuration summary:")
    print(json.dumps(settings.summary(), indent=2))
