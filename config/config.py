import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from dotenv import load_dotenv

_ORIGINAL_ENV = os.environ.copy()
_SKIP_DOTENV = os.getenv("SETTINGS_SKIP_DOTENV") == "1"
if not _SKIP_DOTENV:
    load_dotenv()


_YAML_MODULE = None
_yaml_spec = importlib.util.find_spec("yaml")
if _yaml_spec and _yaml_spec.loader:
    _YAML_MODULE = importlib.util.module_from_spec(_yaml_spec)
    _yaml_spec.loader.exec_module(_YAML_MODULE)


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


def _read_agent_config_file(path: Path) -> Mapping[str, Any]:
    """Load agent configuration overrides from a JSON or YAML file."""

    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        if _YAML_MODULE is None:
            raise RuntimeError("PyYAML is required to load YAML agent configuration files.")
        data = _YAML_MODULE.safe_load(text) or {}
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(
            f"Unsupported agent configuration format '{suffix}'. Use JSON or YAML."
        )

    if not isinstance(data, Mapping):
        raise ValueError("Agent configuration file must contain a mapping at the top level.")

    return data


def _extract_agent_overrides(config_data: Mapping[str, Any]) -> Dict[str, str]:
    """Normalise agent override names from structured configuration data."""

    candidates = config_data
    agents_section = config_data.get("agents") if isinstance(config_data, Mapping) else None
    if isinstance(agents_section, Mapping):
        candidates = agents_section

    overrides: Dict[str, str] = {}
    for key in ("polling", "trigger", "extraction", "human", "crm"):
        direct_value = candidates.get(key)
        alt_value = candidates.get(f"{key}_agent")
        chosen = direct_value or alt_value
        if isinstance(chosen, str) and chosen.strip():
            overrides[key] = chosen.strip()

    return overrides


class Settings:
    """Application configuration loaded from environment variables or defaults."""

    def __init__(self) -> None:
        self.cal_lookahead_days: int = _get_int_env("CAL_LOOKAHEAD_DAYS", 14)
        self.cal_lookback_days: int = _get_int_env("CAL_LOOKBACK_DAYS", 1)

        project_root = Path(__file__).resolve().parents[1]
        default_log_root = project_root / "log_storage" / "run_history"

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

        self.agent_config_file: Optional[Path] = None
        self.agent_overrides: Dict[str, str] = {}

        agent_config_path = _get_env_var("AGENT_CONFIG_FILE")
        if agent_config_path:
            candidate = Path(agent_config_path).expanduser().resolve()
            if candidate.exists():
                try:
                    data = _read_agent_config_file(candidate)
                    self.agent_overrides.update(_extract_agent_overrides(data))
                    self.agent_config_file = candidate
                except Exception as exc:  # pragma: no cover - configuration error surface
                    raise EnvironmentError(
                        f"Failed to read agent configuration from {candidate}: {exc}"
                    ) from exc

        env_overrides = {
            "polling": _get_env_var("POLLING_AGENT"),
            "trigger": _get_env_var("TRIGGER_AGENT"),
            "extraction": _get_env_var("EXTRACTION_AGENT"),
            "human": _get_env_var("HUMAN_AGENT"),
            "crm": _get_env_var("CRM_AGENT"),
        }
        self.agent_overrides.update(
            {key: value for key, value in env_overrides.items() if value}
        )


# Notes: Singleton instance for importing settings in other modules
settings = Settings()
