from __future__ import annotations

import logging
import os
from typing import Optional

from opentelemetry import trace, metrics

logger = logging.getLogger(__name__)

TELEMETRY_AVAILABLE = True

try:
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider as SdkMeterProvider
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
except ImportError:
    # Telemetrie-Pakete fehlen – stiller Rückzug
    TELEMETRY_AVAILABLE = False
    SdkTracerProvider = object  # type: ignore[assignment]
    SdkMeterProvider = object  # type: ignore[assignment]


DISABLE_VALUES = {"none", "0", "false", "off"}


def _configured_endpoint() -> Optional[str]:
    """Return the configured OTLP endpoint, if any."""

    for key in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    ):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def _is_disabled() -> bool:
    if os.environ.get("OTEL_DISABLE_DEV", "").lower() in DISABLE_VALUES:
        return True
    if os.environ.get("OTEL_TRACES_EXPORTER", "").lower() in DISABLE_VALUES:
        return True
    if os.environ.get("OTEL_METRICS_EXPORTER", "").lower() in DISABLE_VALUES:
        return True
    return False


def setup_telemetry(service_name: str = "leadmi") -> None:
    """
    Initialisiert OTLP Tracing + Metrics mit kurzer Timeout-Konfiguration.

    - Verhindert doppelte Initialisierung über Umgebungs-Flag LEADMI_TELEMETRY_INITIALIZED.
    - Erkennt bereits gesetzte Provider.
    - Bei Fehler: einmalige WARN, keine Exception nach oben.
    """
    if not TELEMETRY_AVAILABLE:
        logger.info("Telemetry dependencies not installed; skipping.")
        return

    if _is_disabled():
        logger.info("Telemetry disabled via environment flags.")
        return

    if os.environ.get("LEADMI_TELEMETRY_INITIALIZED") == "1":
        logger.debug("Telemetry already initialized (env flag).")
        return

    existing_tp = trace.get_tracer_provider()
    existing_mp = metrics.get_meter_provider()
    if isinstance(existing_tp, SdkTracerProvider) or isinstance(
        existing_mp, SdkMeterProvider
    ):
        logger.debug("Telemetry providers already present; skipping re-init.")
        os.environ["LEADMI_TELEMETRY_INITIALIZED"] = "1"
        return

    if not _configured_endpoint():
        logger.info("Telemetry skipped (no OTLP endpoint configured).")
        return

    try:
        resource = Resource.create({"service.name": service_name})

        tp = SdkTracerProvider(resource=resource)
        tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(timeout=2)))
        trace.set_tracer_provider(tp)

        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(timeout=2),
            export_interval_millis=60000,
        )
        mp = SdkMeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(mp)

        # Unterdrücke OTLP-Exporter-Rauschen, wenn Collector nicht da
        logging.getLogger("opentelemetry.exporter.otlp").setLevel(logging.ERROR)

        os.environ["LEADMI_TELEMETRY_INITIALIZED"] = "1"
        logger.info("Telemetry initialized (OTLP).")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telemetry initialization failed (%s). Continuing without.", exc)
