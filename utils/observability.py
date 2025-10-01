"""Centralised observability utilities for metrics, tracing, and logging context."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

try:  # pragma: no cover - optional dependency import
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        InMemoryMetricReader,
        MetricReader,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        SpanExporter,
        SpanProcessor,
    )
    from opentelemetry.trace import Span as OtelSpan
    from opentelemetry.trace import Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - graceful degradation when OTEL is absent
    metrics = trace = None  # type: ignore[assignment]
    OTLPMetricExporter = OTLPSpanExporter = None  # type: ignore[assignment]
    MeterProvider = MetricReader = PeriodicExportingMetricReader = None  # type: ignore[assignment]
    InMemoryMetricReader = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]
    TracerProvider = None  # type: ignore[assignment]
    BatchSpanProcessor = None  # type: ignore[assignment]
    SpanExporter = SpanProcessor = Any  # type: ignore[assignment]
    OtelSpan = Any  # type: ignore[assignment]
    Status = StatusCode = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False

_logger = logging.getLogger(__name__)

_TRACER_NAME = "agentic.workflow"
_SERVICE_NAME = "agentic-intelligence-workflow"

_run_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "workflow_run_id", default=None
)

_tracer_provider: Optional[Any] = None
_meter_provider: Optional[Any] = None
_configured = False

_run_counter = None
_trigger_counter = None
_hitl_counter = None
_latency_histogram = None
_cost_spend_counter = None
_cost_event_counter = None

_log_record_factory_installed = False
_original_log_record_factory = logging.getLogRecordFactory()


class _NoopSpan:
    """Minimal span shim used when OpenTelemetry is unavailable."""

    def __init__(self, attributes: Optional[Dict[str, object]] = None) -> None:
        self.attributes: Dict[str, object] = dict(attributes or {})
        self.parent = None
        self.context = type("Context", (), {"span_id": 0, "trace_id": 0})()

    def record_exception(self, _exc: Exception) -> None:  # pragma: no cover - noop
        return

    def set_status(self, _status: Any) -> None:  # pragma: no cover - noop
        return

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


Span = OtelSpan


@dataclass
class RunContext:
    """Runtime context for a workflow run."""

    run_id: str
    span: Span
    start_time: float
    status: str = "unknown"
    completed: bool = False

    def mark_success(self) -> None:
        self.status = "success"

    def mark_failure(self, exc: Optional[Exception] = None) -> None:
        self.status = "failure"
        if exc and hasattr(self.span, "record_exception"):
            try:
                self.span.record_exception(exc)
            except Exception:  # pragma: no cover - defensive guard
                pass
        if (
            exc
            and Status is not None
            and StatusCode is not None
            and hasattr(self.span, "set_status")
        ):
            try:
                self.span.set_status(Status(StatusCode.ERROR, str(exc)))
            except Exception:  # pragma: no cover - defensive guard
                pass

    def mark_status(self, status: str) -> None:
        self.status = status

    def finish(self) -> None:
        if self.completed:
            return
        if self.status == "unknown":
            self.status = "success"
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        if hasattr(self.span, "set_attribute"):
            self.span.set_attribute("workflow.run.duration_ms", duration_ms)
            self.span.set_attribute("workflow.run.status", self.status)
        _record_run_completion(self.status, duration_ms)
        self.completed = True


def configure_observability(
    *,
    span_exporter: Optional[SpanExporter] = None,
    span_processor: Optional[SpanProcessor] = None,
    metric_reader: Optional[MetricReader] = None,
    service_name: str = _SERVICE_NAME,
    force: bool = False,
) -> None:
    """Configure global tracing, metrics, and logging integration."""

    global _configured, _tracer_provider, _meter_provider

    if _configured and not force:
        return

    _install_log_record_factory()

    if not _OTEL_AVAILABLE:
        _tracer_provider = None
        _meter_provider = None
        _reset_instruments()
        _configured = True
        return

    resource = Resource.create({"service.name": service_name}) if Resource else None

    _tracer_provider = TracerProvider(resource=resource) if TracerProvider else None

    processor = span_processor
    exporter = span_exporter
    if processor is None and exporter is None and OTLPSpanExporter is not None:
        try:
            exporter = OTLPSpanExporter()
        except Exception as exc:  # pragma: no cover - exporter misconfiguration
            _logger.warning("Failed to initialise OTLP span exporter: %s", exc)
            exporter = None
    if processor is None and exporter is not None and BatchSpanProcessor is not None:
        processor = BatchSpanProcessor(exporter)
    if processor is not None and _tracer_provider is not None:
        _tracer_provider.add_span_processor(processor)

    if trace is not None and _tracer_provider is not None:
        trace.set_tracer_provider(_tracer_provider)

    reader = metric_reader
    if reader is None and OTLPMetricExporter is not None:
        try:
            metric_exporter = OTLPMetricExporter()
            reader = PeriodicExportingMetricReader(metric_exporter)
        except Exception as exc:  # pragma: no cover - exporter misconfiguration
            _logger.warning("Failed to initialise OTLP metric exporter: %s", exc)
            reader = None

    if MeterProvider is not None:
        if reader is not None:
            _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        else:
            _meter_provider = MeterProvider(resource=resource)
        if metrics is not None and _meter_provider is not None:
            metrics.set_meter_provider(_meter_provider)
    else:
        _meter_provider = None

    _reset_instruments()

    _configured = True


def generate_run_id() -> str:
    """Generate a unique, log-friendly run identifier."""

    return f"run-{uuid.uuid4()}"


def _start_span(name: str, attributes: Dict[str, object]):
    if _OTEL_AVAILABLE and trace is not None:
        tracer = trace.get_tracer(_TRACER_NAME)
        return tracer.start_as_current_span(name, attributes=attributes)
    span = _NoopSpan(attributes)
    return contextlib.nullcontext(span)


@contextlib.contextmanager
def workflow_run(
    *, run_id: Optional[str] = None, attributes: Optional[Dict[str, object]] = None
) -> Iterable[RunContext]:
    """Context manager that establishes tracing and metrics for a run."""

    if not _configured:
        configure_observability()

    resolved_run_id = run_id or generate_run_id()
    token = _run_id_var.set(resolved_run_id)

    span_attributes = {"workflow.run_id": resolved_run_id}
    if attributes:
        span_attributes.update(attributes)

    start_time = time.perf_counter()

    with _start_span("workflow.run", span_attributes) as span:
        context = RunContext(resolved_run_id, span, start_time)
        try:
            yield context
        except Exception as exc:
            context.mark_failure(exc)
            raise
        finally:
            context.finish()
            _run_id_var.reset(token)


@contextlib.contextmanager
def observe_operation(
    operation: str, attributes: Optional[Dict[str, object]] = None
) -> Iterable[Span]:
    """Track latency and tracing information for an operation."""

    if not _configured:
        configure_observability()

    span_attributes = {"workflow.operation": operation}
    run_id = get_current_run_id()
    if run_id:
        span_attributes["workflow.run_id"] = run_id
    if attributes:
        span_attributes.update(attributes)

    start = time.perf_counter()

    with _start_span(f"workflow.{operation}", span_attributes) as span:
        try:
            yield span
        except Exception as exc:
            if hasattr(span, "record_exception"):
                try:
                    span.record_exception(exc)
                except Exception:  # pragma: no cover - defensive guard
                    pass
            if (
                Status is not None
                and StatusCode is not None
                and hasattr(span, "set_status")
            ):
                try:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                except Exception:  # pragma: no cover - defensive guard
                    pass
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            _record_operation_latency(operation, duration_ms, attributes)
            if hasattr(span, "set_attribute"):
                span.set_attribute("workflow.operation.duration_ms", duration_ms)


def record_trigger_match(trigger_type: str) -> None:
    if not _configured:
        configure_observability()

    if _trigger_counter is None:
        return

    attributes = {"trigger.type": trigger_type or "unknown"}
    _trigger_counter.add(1, attributes=attributes)


def record_hitl_outcome(kind: str, outcome: str) -> None:
    if not _configured:
        configure_observability()

    if _hitl_counter is None:
        return

    attributes = {"hitl.kind": kind, "hitl.outcome": outcome}
    _hitl_counter.add(1, attributes=attributes)


def record_cost_spend(service: str, amount: float) -> None:
    if not _configured:
        configure_observability()

    if _cost_spend_counter is None:
        return

    attributes = {"service": service or "unknown"}
    try:
        _cost_spend_counter.add(float(amount), attributes=attributes)
    except Exception:  # pragma: no cover - defensive guard around metric emission
        _logger.exception("Failed to record cost spend metric")


def record_cost_limit_event(
    event: str, service: str, *, limit: Optional[float] = None
) -> None:
    if not _configured:
        configure_observability()

    if _cost_event_counter is None:
        return

    attributes: Dict[str, object] = {"service": service or "unknown", "event": event}
    if limit is not None:
        attributes["limit"] = float(limit)

    try:
        _cost_event_counter.add(1, attributes=attributes)
    except Exception:  # pragma: no cover - defensive guard around metric emission
        _logger.exception("Failed to record cost limit event metric")


def get_current_run_id() -> Optional[str]:
    return _run_id_var.get()


async def flush_telemetry(timeout: float = 5.0) -> None:
    """Flush pending telemetry exports and shut down providers."""

    if not _configured:
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _flush_providers, float(timeout))


def _flush_providers(timeout: float) -> None:
    global _configured, _tracer_provider, _meter_provider  # noqa: PLW0603

    if timeout <= 0:
        timeout = 5.0

    timeout_millis = int(timeout * 1000)

    if _tracer_provider is not None:
        closer = getattr(_tracer_provider, "force_flush", None)
        if callable(closer):
            try:
                closer(timeout_millis=timeout_millis)
            except TypeError:
                closer()
            except Exception:  # pragma: no cover - defensive guard
                _logger.exception("Failed to flush tracer provider")

        shutdown = getattr(_tracer_provider, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
            except Exception:  # pragma: no cover - defensive guard
                _logger.exception("Failed to shutdown tracer provider")

    if _meter_provider is not None:
        force_flush = getattr(_meter_provider, "force_flush", None)
        if callable(force_flush):
            try:
                force_flush(timeout_millis=timeout_millis)
            except TypeError:
                force_flush()
            except Exception:  # pragma: no cover - defensive guard
                _logger.exception("Failed to flush meter provider")

        shutdown = getattr(_meter_provider, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
            except Exception:  # pragma: no cover - defensive guard
                _logger.exception("Failed to shutdown meter provider")

    _configured = False
    _tracer_provider = None
    _meter_provider = None


def _record_run_completion(status: str, duration_ms: float) -> None:
    if _run_counter is not None:
        _run_counter.add(1, attributes={"status": status})
    _record_operation_latency("run", duration_ms, {"status": status})


def _record_operation_latency(
    operation: str, duration_ms: float, attributes: Optional[Dict[str, object]]
) -> None:
    if _latency_histogram is None:
        return

    metric_attributes = {"operation": operation}
    if attributes:
        metric_attributes.update(attributes)
    _latency_histogram.record(duration_ms, attributes=metric_attributes)


def _reset_instruments() -> None:
    global _run_counter, _trigger_counter, _hitl_counter, _latency_histogram
    global _cost_spend_counter, _cost_event_counter

    if not _OTEL_AVAILABLE or metrics is None:
        _run_counter = _trigger_counter = _hitl_counter = _latency_histogram = None
        _cost_spend_counter = _cost_event_counter = None
        return

    meter = metrics.get_meter(_TRACER_NAME)
    _run_counter = meter.create_counter(
        "workflow_runs_total",
        description="Total number of workflow runs processed.",
    )
    _trigger_counter = meter.create_counter(
        "workflow_trigger_matches_total",
        description="Number of events that matched workflow triggers.",
    )
    _hitl_counter = meter.create_counter(
        "workflow_hitl_outcomes_total",
        description="Outcomes recorded for human-in-the-loop interactions.",
    )
    _latency_histogram = meter.create_histogram(
        "workflow_operation_duration_ms",
        description="Latency distribution for workflow operations.",
        unit="ms",
    )
    _cost_spend_counter = meter.create_counter(
        "workflow_cost_spend_usd_total",
        description="Total spend recorded by the workflow cost guard.",
    )
    _cost_event_counter = meter.create_counter(
        "workflow_cost_guard_events_total",
        description="Count of budget guard events (warnings, breaches, rate limits).",
    )


def _install_log_record_factory() -> None:
    global _log_record_factory_installed

    if _log_record_factory_installed:
        return

    def record_factory(*args, **kwargs):  # type: ignore[override]
        record = _original_log_record_factory(*args, **kwargs)
        record.run_id = get_current_run_id() or "n/a"
        return record

    logging.setLogRecordFactory(record_factory)
    _log_record_factory_installed = True


# Convenience helpers for tests -------------------------------------------------

def get_in_memory_exporters() -> Dict[str, object]:
    """Return configured in-memory testing exporters, if any."""

    readers: Dict[str, object] = {}
    if not _OTEL_AVAILABLE or _meter_provider is None or InMemoryMetricReader is None:
        return readers
    for reader in getattr(_meter_provider, "_metric_readers", []):  # type: ignore[attr-defined]
        if isinstance(reader, InMemoryMetricReader):
            readers["metric_reader"] = reader
    return readers
