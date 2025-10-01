import os
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

LOG = logging.getLogger(__name__)
_ACCEPT = {"1", "true", "yes", "on"}


def _telemetry_enabled() -> bool:
    val = os.getenv("ENABLE_OTEL", "")
    if val.strip().lower() not in _ACCEPT:
        return False
    if os.getenv("OTEL_DISABLE_DEV", "").strip().lower() in _ACCEPT:
        return False
    return True


def setup_telemetry(
    service_name: str = "lead-market-insights",
) -> Optional[trace.Tracer]:
    if not _telemetry_enabled():
        LOG.info("Telemetry disabled (ENABLE_OTEL not truthy or suppressed).")
        return None

    endpoint_base = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint_base:
        LOG.info("Telemetry disabled: OTEL_EXPORTER_OTLP_ENDPOINT unset.")
        return None

    endpoint_base = endpoint_base.rstrip("/")
    traces_endpoint = f"{endpoint_base}/v1/traces"

    # Lazy Import – verhindert ImportError wenn Paket im CI fehlt
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
    except Exception as exc:
        LOG.warning(
            "Telemetry exporter unavailable (%s). Running without tracing.", exc
        )
        return None

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": os.getenv("APP_ENV", "dev"),
            "service.version": os.getenv("SERVICE_VERSION", "unknown"),
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=traces_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer(service_name)
    LOG.info(
        "Telemetry enabled (endpoint=%s env=%s version=%s)",
        traces_endpoint,
        resource.attributes.get("deployment.environment"),
        resource.attributes.get("service.version"),
    )

    # kurzes Start-Span
    with tracer.start_as_current_span("startup"):
        pass

    if os.getenv("OTEL_METRICS_EXPORTER", "none").lower() == "none":
        LOG.info("Metrics explicitly disabled (OTEL_METRICS_EXPORTER=none).")

    return tracer
