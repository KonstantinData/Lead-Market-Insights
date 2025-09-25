"""Tests for configuration settings loading."""

import importlib


def reload_settings():
    config_module = importlib.import_module("config.config")
    importlib.reload(config_module)
    return config_module.settings


def test_s3_bucket_prefers_primary_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "primary-bucket")
    monkeypatch.setenv("S3_BUCKET", "legacy-bucket")

    settings = reload_settings()

    assert settings.s3_bucket == "primary-bucket"


def test_s3_bucket_supports_legacy_env(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.setenv("S3_BUCKET", "legacy-only")

    settings = reload_settings()

    assert settings.s3_bucket == "legacy-only"
