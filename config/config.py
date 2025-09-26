import os
from typing import Optional, Tuple

from dotenv import load_dotenv

_ORIGINAL_ENV = os.environ.copy()
_SKIP_DOTENV = os.getenv("SETTINGS_SKIP_DOTENV") == "1"
if not _SKIP_DOTENV:
    load_dotenv()


def _normalise(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    return value


def _get_env_var(name: str, *, aliases: Tuple[str, ...] = ()) -> Optional[str]:
    """Return an environment variable using the conventional uppercase name.

    When aliases are provided, values defined in the pre-dotenv environment take
    precedence. This ensures runtime overrides such as ``DATABASE_URL`` can win
    even if ``.env`` supplies the primary key.
    """

    if aliases:
        primary_original = _normalise(_ORIGINAL_ENV.get(name))
        for alias in aliases:
            alias_original = _normalise(_ORIGINAL_ENV.get(alias))
            if alias_original is not None and primary_original is None:
                alias_value = _normalise(os.getenv(alias))
                if alias_value is not None:
                    return alias_value

    value = _normalise(os.getenv(name))
    if value is not None:
        return value

    for alias in aliases:
        alias_value = _normalise(os.getenv(alias))
        if alias_value is not None:
            return alias_value

    return None


def _get_int_env(name: str, default: int) -> int:
    """Fetch an integer environment variable with fallback to a default value."""

    raw_value = _get_env_var(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive programming branch
        raise ValueError(f"Environment variable {name} must be an integer.") from exc


class Settings:
    """Application configuration loaded from environment variables or defaults."""

    def __init__(self) -> None:
        self.cal_lookahead_days: int = _get_int_env("CAL_LOOKAHEAD_DAYS", 14)
        self.cal_lookback_days: int = _get_int_env("CAL_LOOKBACK_DAYS", 1)

        self.aws_access_key_id: Optional[str] = _get_env_var("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key: Optional[str] = _get_env_var("AWS_SECRET_ACCESS_KEY")
        self.aws_default_region: Optional[str] = _get_env_var("AWS_DEFAULT_REGION")
        self.s3_bucket: Optional[str] = _get_env_var(
            "S3_BUCKET_NAME", aliases=("S3_BUCKET",)
        )

        self.postgres_dsn: Optional[str] = _get_env_var(
            "POSTGRES_DSN", aliases=("DATABASE_URL",)
        )
        self.postgres_event_log_table: str = _get_env_var(
            "POSTGRES_EVENT_LOG_TABLE"
        ) or "event_logs"
        self.postgres_workflow_log_table: str = _get_env_var(
            "POSTGRES_WORKFLOW_LOG_TABLE"
        ) or "workflow_logs"
        self.postgres_file_log_table: str = _get_env_var(
            "POSTGRES_FILE_LOG_TABLE"
        ) or "workflow_log_files"

        self.trigger_words: Optional[str] = _get_env_var("TRIGGER_WORDS")


# Notes: Singleton instance for importing settings in other modules
settings = Settings()
