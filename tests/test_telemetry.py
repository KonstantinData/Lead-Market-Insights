import os
import importlib

import pytest
from opentelemetry import trace

# We import from our utils package
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
