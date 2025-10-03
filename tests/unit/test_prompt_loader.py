import pytest

from config.config import settings
from utils import prompt_loader


@pytest.fixture(autouse=True)
def reset_prompt_loader(monkeypatch):
    original_versions = dict(settings.prompt_versions)
    original_directory = settings.prompt_directory

    prompt_loader.clear_prompt_cache()
    yield

    monkeypatch.setattr(settings, "prompt_versions", original_versions, raising=False)
    monkeypatch.setattr(settings, "prompt_directory", original_directory, raising=False)
    prompt_loader.clear_prompt_cache()


def test_get_prompt_default_version_selects_latest(monkeypatch):
    monkeypatch.setattr(settings, "prompt_versions", {}, raising=False)

    prompt = prompt_loader.get_prompt("customer_follow_up")

    assert prompt["version"] == "v2"
    assert prompt["metadata"]["max_tokens"] == 640


def test_get_prompt_respects_config_override(monkeypatch):
    monkeypatch.setattr(
        settings, "prompt_versions", {"customer_follow_up": "v1"}, raising=False
    )

    prompt = prompt_loader.get_prompt("customer_follow_up")

    assert prompt["version"] == "v1"
    assert prompt["metadata"]["temperature"] == 0.4


def test_get_prompt_explicit_version_overrides_config(monkeypatch):
    monkeypatch.setattr(
        settings, "prompt_versions", {"customer_follow_up": "v1"}, raising=False
    )

    prompt = prompt_loader.get_prompt("customer_follow_up", version="v2")

    assert prompt["version"] == "v2"


def test_get_prompt_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(settings, "prompt_versions", {}, raising=False)

    prompt = prompt_loader.get_prompt("CUSTOMER_FOLLOW_UP")

    assert prompt["version"] == "v2"
