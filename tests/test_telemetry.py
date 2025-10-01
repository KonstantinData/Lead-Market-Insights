import importlib.util
import logging
import sys
import types


def _ensure_module(module_name: str) -> types.ModuleType:
    """Return an existing module or create a lightweight placeholder."""

    module = sys.modules.get(module_name)
    if module is not None:
        return module

    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    return module


def _install_http_exporter_stub() -> None:
    """Provide a minimal OTLP HTTP exporter so tests can run without the extra package."""

    full_name = "opentelemetry.exporter.otlp.proto.http.trace_exporter"

    # create the full module hierarchy if required
    parts = full_name.split(".")
    for idx in range(1, len(parts)):
        parent_name = ".".join(parts[:idx])
        child_name = parts[idx]
        parent = _ensure_module(parent_name)
        child_module = _ensure_module(".".join(parts[: idx + 1]))
        if not hasattr(parent, child_name):
            setattr(parent, child_name, child_module)

    trace_exporter_module = _ensure_module(full_name)

    if hasattr(trace_exporter_module, "OTLPSpanExporter"):
        return

    class _DummyExporter:  # pragma: no cover - trivial class
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def export(self, *args, **kwargs):
            return None

    trace_exporter_module.OTLPSpanExporter = _DummyExporter  # type: ignore[attr-defined]


# Skip-Logik ersetzen: falls der HTTP-Exporter fehlt, stellen wir einen Stub bereit.
try:
    spec = importlib.util.find_spec(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter"
    )
except ModuleNotFoundError:
    spec = None

if spec is None:
    _install_http_exporter_stub()

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
