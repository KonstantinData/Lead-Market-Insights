import os
from typing import Optional, Tuple

from dotenv import load_dotenv


def _get_env_var(name: str, *, aliases: Tuple[str, ...] = ()) -> Optional[str]:
    """Return an environment variable using the conventional uppercase name.

    Parameters
    ----------
    name:
        The primary environment variable name to resolve.
    aliases:
        Optional alternative variable names evaluated when the primary value is
        unset. The first defined value is returned.
    """

    for candidate in (name, *aliases):
        value = os.getenv(candidate)
        if value is not None:
            return value

    return None


def _get_int_env(name: str, default: int) -> int:
    """Fetch an integer environment variable with fallback to a default value."""

    raw_value = _get_env_var(name)
    if raw_value is None or raw_value == "":
        return default

    try:
        return int(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive programming branch
        raise ValueError(f"Environment variable {name} must be an integer.") from exc


class Settings:
    """Application configuration loaded from environment variables or defaults."""

    def __init__(self) -> None:
        load_dotenv()

        self.cal_lookahead_days: int = _get_int_env("CAL_LOOKAHEAD_DAYS", 14)
        self.cal_lookback_days: int = _get_int_env("CAL_LOOKBACK_DAYS", 1)

        self.aws_access_key_id: Optional[str] = _get_env_var("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key: Optional[str] = _get_env_var("AWS_SECRET_ACCESS_KEY")
        self.aws_default_region: Optional[str] = _get_env_var("AWS_DEFAULT_REGION")
        self.s3_bucket: Optional[str] = _get_env_var(
            "S3_BUCKET_NAME", aliases=("S3_BUCKET",)
        )

        self.trigger_words: Optional[str] = _get_env_var("TRIGGER_WORDS")


# Notes: Singleton instance for importing settings in other modules
settings = Settings()
