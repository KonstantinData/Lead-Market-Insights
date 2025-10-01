from __future__ import annotations

import logging
import os

from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

logger = logging.getLogger(__name__)

DISABLE_VALUES = {"none", "0", "false", "off"}


def _is_disabled() -> bool:
    # Wenn irgendein Exporter explizit auf 'none' gesetzt ist, komplett deaktivieren.
    if os.environ.get("OTEL_TRACES_EXPORTER", "").lower() in DISABLE_VALUES:
        return True
    if os.environ.get("OTEL_METRICS_EXPORTER", "").lower() in DISABLE_VALUES:
        return True
    if os.environ.get("OTEL_LOGS_EXPORTER", "").lower() in DISABLE_VALUES:
        return True
    if os.environ.get("OTEL_DISABLE_DEV", "").lower() in DISABLE_VALUES:
        return True
    return False


def setup_telemetry(service_name: str = "leadmi") -> None:
    """
    Initialisiert OTLP Exporter (Tracing + Metrics) mit kurzen Timeouts.
    Fällt bei Fehlern still zurück und loggt nur einmal WARN.
    """
    if _is_disabled():
        logger.info("Telemetry disabled by environment flags.")
        return

    try:
        resource = Resource.create({"service.name": service_name})
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(timeout=2))
        )
        trace.set_tracer_provider(tracer_provider)

        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(timeout=2),
            export_interval_millis=60000,
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
        metrics.set_meter_provider(meter_provider)

        # Rauschen dämpfen, falls Collector offline
        logging.getLogger("opentelemetry.exporter.otlp").setLevel(logging.ERROR)

        logger.info("Telemetry initialized (OTLP).")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telemetry disabled (exporter init failed: %s)", exc)
