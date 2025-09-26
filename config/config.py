import os
from pathlib import Path
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
    precedence. This ensures runtime overrides can win even if ``.env`` supplies
    the primary key.
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


def _get_path_env(name: str, default: Path) -> Path:
    """Return the path from an environment variable or a default."""

    raw_value = _get_env_var(name)
    if raw_value:
        return Path(raw_value).expanduser().resolve()
    return default


class Settings:
    """Application configuration loaded from environment variables or defaults."""

    def __init__(self) -> None:
        self.cal_lookahead_days: int = _get_int_env("CAL_LOOKAHEAD_DAYS", 14)
        self.cal_lookback_days: int = _get_int_env("CAL_LOOKBACK_DAYS", 1)

        project_root = Path(__file__).resolve().parents[1]
        default_log_root = project_root / "logs" / "run_history"

        self.log_storage_dir: Path = _get_path_env("LOG_STORAGE_DIR", default_log_root)
        self.event_log_dir: Path = _get_path_env(
            "EVENT_LOG_DIR", self.log_storage_dir / "events"
        )
        self.workflow_log_dir: Path = _get_path_env(
            "WORKFLOW_LOG_DIR", self.log_storage_dir / "workflows"
        )
        self.run_log_dir: Path = _get_path_env(
            "RUN_LOG_DIR", self.log_storage_dir / "runs"
        )

        self.trigger_words: Optional[str] = _get_env_var("TRIGGER_WORDS")


# Notes: Singleton instance for importing settings in other modules
settings = Settings()
