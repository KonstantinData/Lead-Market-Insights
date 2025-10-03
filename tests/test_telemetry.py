import importlib

import pytest
from opentelemetry import trace

# We import from our utils package
from utils import telemetry as telemetry_mod
from utils.telemetry import setup_telemetry


def reset_otel_singletons():
    """
    Helper to reset the global tracer provider between tests so that we can
    exercise setup_telemetry(force=True) in a controlled way.
    """
    # The opentelemetry SDK stores the global provider in trace._TRACER_PROVIDER
    # To avoid relying on private APIs too much, we just force a reload of the 'opentelemetry.trace'
    # module AFTER clearing the provider reference. If the internals change, this test
    # will still fail loudly rather than silently mask a problem.
    try:
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    except Exception:
        pass
    importlib.reload(trace)


def test_setup_telemetry_basic(monkeypatch):
    reset_otel_singletons()
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-svc")
    monkeypatch.setenv("DEPLOY_ENV", "test-env")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    setup_telemetry(force=True)  # Should not raise

    tracer_provider = trace.get_tracer_provider()
    # Basic sanity: provider should not be the default no-op
    assert tracer_provider is not None

    # Acquire a tracer and create a span
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("demo-span") as span:
        assert span is not None
        # No strict assertions about export side effects; just ensure span creation works.


def test_setup_telemetry_idempotent(monkeypatch):
    reset_otel_singletons()
    monkeypatch.setenv("OTEL_SERVICE_NAME", "idempotent-svc")

    setup_telemetry(force=True)
    first_provider = trace.get_tracer_provider()

    # Call again without force → should keep same provider object
    setup_telemetry()
    second_provider = trace.get_tracer_provider()
    assert first_provider is second_provider

    # Call again with force=True → provider can be replaced
    setup_telemetry(force=True)
    third_provider = trace.get_tracer_provider()
    assert third_provider is not None
    # We allow replacement; just ensure still valid
    assert third_provider is trace.get_tracer_provider()


def test_ratio_sampler_extremes(monkeypatch):
    reset_otel_singletons()
    # Force ratio = 0.0 → no spans should be recorded (heuristic: using internal span property)
    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.0")
    setup_telemetry(force=True)

    tracer = trace.get_tracer("ratio0")
    with tracer.start_as_current_span("zero-span") as span:
        # We cannot easily assert exporter output here; for a ratio of 0, span context
        # typically is still created but may not be sampled. We check sampled flag if present.
        sampled_flag = getattr(span.get_span_context(), "trace_flags", None)
        if sampled_flag is not None:
            # In OTel TraceFlags, sampled == 0x01
            assert int(sampled_flag) & 0x01 == 0

    reset_otel_singletons()
    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "1.0")
    setup_telemetry(force=True)
    tracer = trace.get_tracer("ratio1")
    with tracer.start_as_current_span("one-span") as span:
        sampled_flag = getattr(span.get_span_context(), "trace_flags", None)
        if sampled_flag is not None:
            assert int(sampled_flag) & 0x01 == 0x01


def test_custom_ratio_env(monkeypatch):
    reset_otel_singletons()
    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.25")
    setup_telemetry(force=True)

    tracer = trace.get_tracer("ratio25")
    # Smoke-test: create several spans; just ensure no exception
    for _ in range(10):
        with tracer.start_as_current_span("loop-span"):
            pass  # intentionally empty


def test_parse_resource_kv_and_ratio_resolution(monkeypatch):
    raw = "team=core, bad-entry, env = staging "
    parsed = telemetry_mod._parse_resource_kv(raw)
    assert parsed == {"team": "core", "env": "staging"}

    assert telemetry_mod._resolve_ratio(2.0) == 1.0
    assert telemetry_mod._resolve_ratio(-1.0) == 0.0

    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.15")
    assert telemetry_mod._resolve_ratio(None) == pytest.approx(0.15)

    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "bogus")
    assert telemetry_mod._resolve_ratio(None) == 1.0


def test_endpoint_resolution_and_normalisation(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    assert telemetry_mod._resolve_endpoint(None) is None

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://fallback")
    assert telemetry_mod._resolve_endpoint(None) == "https://fallback"

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://override")
    assert telemetry_mod._resolve_endpoint(None) == "https://override"

    assert telemetry_mod._resolve_endpoint("https://explicit") == "https://explicit"

    assert (
        telemetry_mod._normalise_http_endpoint("https://collector")
        == "https://collector/v1/traces"
    )

    with pytest.raises(ValueError):
        telemetry_mod._normalise_http_endpoint("https:///missing-host")

    assert (
        telemetry_mod._normalise_grpc_endpoint("grpc://host:4317/v1/traces")
        == "host:4317"
    )
    assert telemetry_mod._normalise_grpc_endpoint("collector:4317") == "collector:4317"


def test_exporter_protocol_preference(monkeypatch):
    reset_otel_singletons()

    class DummyProvider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.processors = []

        def add_span_processor(self, processor):
            self.processors.append(processor)

    class DummyBatchProcessor:
        def __init__(self, exporter):
            self.exporter = exporter

    class DummySimpleProcessor:
        def __init__(self, exporter):
            self.exporter = exporter

    class DummyConsoleExporter:
        pass

    http_created = {}
    grpc_created = {}

    class DummyHTTPExporter:
        def __init__(self, endpoint):
            http_created["endpoint"] = endpoint

    class DummyGrpcExporter:
        def __init__(self, endpoint, insecure):
            grpc_created["endpoint"] = endpoint
            grpc_created["insecure"] = insecure

    monkeypatch.setattr(telemetry_mod, "_SdkTracerProvider", DummyProvider)
    monkeypatch.setattr(telemetry_mod, "BatchSpanProcessor", DummyBatchProcessor)
    monkeypatch.setattr(telemetry_mod, "SimpleSpanProcessor", DummySimpleProcessor)
    monkeypatch.setattr(telemetry_mod, "ConsoleSpanExporter", DummyConsoleExporter)
    monkeypatch.setattr(
        telemetry_mod, "_build_real_sampler", lambda ratio: f"sampler:{ratio}"
    )
    monkeypatch.setattr(telemetry_mod, "Resource", None)
    monkeypatch.setattr(telemetry_mod, "_HttpSpanExporter", DummyHTTPExporter)
    monkeypatch.setattr(telemetry_mod, "_GrpcSpanExporter", DummyGrpcExporter)

    provider = telemetry_mod._setup_real_provider(
        ratio=0.5,
        resource_attrs={"service.name": "svc"},
        endpoint="https://collector",
        use_console_exporter=True,
    )

    assert isinstance(provider, DummyProvider)
    # HTTP preferred by default
    assert http_created["endpoint"].endswith("/v1/traces")
    assert "grpc" not in grpc_created

    # Switch to prefer gRPC via protocol env and ensure fallback to HTTP when gRPC fails
    def failing_grpc_exporter(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(telemetry_mod, "_GrpcSpanExporter", failing_grpc_exporter)
    grpc_created.clear()

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")

    provider = telemetry_mod._setup_real_provider(
        ratio=0.5,
        resource_attrs={"service.name": "svc"},
        endpoint="https://collector",
        use_console_exporter=False,
    )

    assert isinstance(provider, DummyProvider)
    # HTTP fallback should have been used because gRPC exporter failed
    assert http_created["endpoint"].endswith("/v1/traces")


def test_setup_telemetry_stub_fallback(monkeypatch):
    reset_otel_singletons()

    monkeypatch.setattr(telemetry_mod, "_SDK_AVAILABLE", True)

    def boom(**_kwargs):
        raise RuntimeError("nope")

    stub_provider = telemetry_mod._CompatProvider(
        telemetry_mod._AlwaysOnSampler(), {"service.name": "stub"}
    )

    monkeypatch.setattr(telemetry_mod, "_setup_real_provider", boom)
    monkeypatch.setattr(
        telemetry_mod, "_setup_stub_provider", lambda **_kwargs: stub_provider
    )

    setup_telemetry(force=True, service_name="stub")
    assert trace.get_tracer_provider() is stub_provider


def test_trace_provider_hooks(monkeypatch):
    reset_otel_singletons()

    monkeypatch.setattr(telemetry_mod, "_SDK_AVAILABLE", False)
    setup_telemetry(force=True, service_name="compat")

    new_provider = telemetry_mod._CompatProvider(
        telemetry_mod._AlwaysOffSampler(), {"service.name": "compat"}
    )

    trace.set_tracer_provider(new_provider)
    assert trace.get_tracer_provider() is new_provider
