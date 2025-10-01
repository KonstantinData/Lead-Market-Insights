from __future__ import annotations

import logging

from utils.telemetry import setup_telemetry


def test_setup_telemetry_skips_without_endpoint(monkeypatch, caplog):
    for env in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    ):
        monkeypatch.delenv(env, raising=False)

    def _fail(*_args, **_kwargs):  # pragma: no cover - sanity guard
        raise AssertionError("Telemetry initialisation should be skipped")

    monkeypatch.setattr("utils.telemetry.TracerProvider", _fail)

    caplog.set_level(logging.INFO)

    setup_telemetry(service_name="test-service")

    assert "Telemetry skipped (no OTLP endpoint configured)." in caplog.text
