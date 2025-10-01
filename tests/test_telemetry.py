import importlib.util
import pytest
import logging

# Skip, wenn Exporter-Modul fehlt (robust gegen fehlende Dev-Abhängigkeiten)
if (
    importlib.util.find_spec("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    is None
):
    pytest.skip(
        "OTLP exporter not installed; skipping telemetry tests.",
        allow_module_level=True,
    )

from utils.telemetry import setup_telemetry


def test_setup_telemetry_disabled(monkeypatch, caplog):
    monkeypatch.setenv("ENABLE_OTEL", "false")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    with caplog.at_level(logging.INFO):
        tracer = setup_telemetry(service_name="test-svc")
    assert tracer is None
    assert any("Telemetry disabled" in m for m in caplog.messages)


def test_setup_telemetry_enabled(monkeypatch, caplog):
    monkeypatch.setenv("ENABLE_OTEL", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.delenv("OTEL_DISABLE_DEV", raising=False)
    with caplog.at_level(logging.INFO):
        tracer = setup_telemetry(service_name="test-svc")
    # tracer kann None sein, falls Exporter doch nicht vollständig ladbar -> akzeptiere Warnpfad
    if tracer is None:
        assert any("Telemetry exporter unavailable" in m for m in caplog.messages)
    else:
        assert any("Telemetry enabled" in m for m in caplog.messages)
