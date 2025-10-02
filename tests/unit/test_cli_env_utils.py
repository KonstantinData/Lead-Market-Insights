import asyncio
import sys
from types import ModuleType

import pytest

from utils import cli_runner, env_compat, env_validation, google_auth
from utils.duplicate_checker import DuplicateChecker


@pytest.mark.asyncio
async def test_run_cli_executes_entrypoint():
    called = {}

    async def entrypoint():
        called["done"] = True

    result = await asyncio.to_thread(cli_runner.run_cli, lambda: entrypoint())
    assert result is None
    assert called["done"] is True


def test_resolve_entrypoint_returns_async_callable(monkeypatch):
    module = ModuleType("dummy_module")

    async def sample():
        return "ok"

    module.sample = sample
    monkeypatch.setitem(sys.modules, module.__name__, module)

    resolved = cli_runner._resolve_entrypoint("dummy_module:sample")
    assert resolved is sample


def test_resolve_entrypoint_validates_format():
    with pytest.raises(ValueError):
        cli_runner._resolve_entrypoint("missing_separator")

    module = ModuleType("sync_module")

    def sync_func():
        return None

    module.fn = sync_func
    sys.modules[module.__name__] = module

    with pytest.raises(TypeError):
        cli_runner._resolve_entrypoint("sync_module:fn")


def test_parse_args_and_main(monkeypatch):
    captured = {}

    async def entrypoint():
        captured["ran"] = True

    monkeypatch.setitem(sys.modules, "cli_entry", ModuleType("cli_entry"))
    sys.modules["cli_entry"].main = entrypoint

    monkeypatch.setattr(cli_runner, "run_cli", lambda func: asyncio.run(func()))

    cli_runner.main(["cli_entry:main"])
    assert captured["ran"] is True


def test_env_compat_promotes_and_backfills(monkeypatch, caplog):
    caplog.set_level("DEBUG")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPEN_AI_KEY", "legacy-key")

    env_compat.apply_env_compat()
    assert env_validation.os.getenv("OPENAI_API_KEY") == "legacy-key"
    assert "promoted" in caplog.text

    monkeypatch.delenv("OPEN_AI_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "canonical")
    env_compat.apply_env_compat()
    assert env_validation.os.getenv("OPEN_AI_KEY") == "canonical"
    assert "backfilled" in caplog.text


def test_validate_environment_strict(monkeypatch, caplog):
    caplog.set_level("ERROR")
    for key in env_validation.REQUIRED:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_AI_KEY", raising=False)

    assert env_validation.validate_environment(strict=True) is False
    assert "Missing required environment variables" in caplog.text


def test_validate_environment_relaxed(monkeypatch, caplog):
    caplog.set_level("INFO")
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    for key in env_validation.REQUIRED:
        if key != "__OPENAI_KEY__":
            monkeypatch.setenv(key, "value")

    assert env_validation.validate_environment(strict=False) is True
    assert "Environment validation passed" in caplog.text


def test_duplicate_checker_detection():
    checker = DuplicateChecker()
    assert checker.is_duplicate("evt", {"evt", "other"}) is True
    assert checker.is_duplicate("missing", {"evt"}) is False


def test_duplicate_checker_errors(caplog):
    caplog.set_level("ERROR")
    checker = DuplicateChecker()
    with pytest.raises(TypeError):
        checker.is_duplicate("evt", None)
    assert "Error during duplicate check" in caplog.text


def test_google_auth_ensure_access_token_refresh(monkeypatch):
    refreshed = {}

    class FakeCreds:
        def __init__(self, valid, token=None, refresh_token=None):
            self.valid = valid
            self.token = token
            self.refresh_token = refresh_token

        def refresh(self, request):
            refreshed["called"] = True
            self.token = "new-token"

    monkeypatch.setattr(google_auth, "Request", lambda: object())
    creds = FakeCreds(valid=False, token=None, refresh_token="refresh")
    token = google_auth.ensure_access_token(creds)
    assert token == "new-token"
    assert refreshed["called"] is True


def test_google_auth_ensure_access_token_requires_token():
    class FakeCreds:
        def __init__(self):
            self.valid = True
            self.refresh_token = None
            self.token = None

    creds = FakeCreds()
    with pytest.raises(RuntimeError):
        google_auth.ensure_access_token(creds)


def test_google_auth_auth_header():
    assert google_auth.auth_header("abc") == {"Authorization": "Bearer abc"}
