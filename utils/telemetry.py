"""
Central OpenTelemetry tracing setup (extended version).

Adds:
- deployment.environment (from APP_ENV, defaults to dev)
- service.version (from SERVICE_VERSION, defaults to unknown)
"""

import os
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

_LOG = logging.getLogger(__name__)


def setup_telemetry(
    service_name: str = "lead-market-insights",
) -> Optional[trace.Tracer]:
    if not _is_enabled():
        _LOG.info("Telemetry disabled (ENABLE_OTEL not set to a truthy value).")
        return None

    base_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not base_endpoint:
        _LOG.info("Telemetry disabled: OTEL_EXPORTER_OTLP_ENDPOINT not set.")
        return None

    base_endpoint = base_endpoint.rstrip("/")
    full_traces_endpoint = f"{base_endpoint}/v1/traces"

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": os.getenv("APP_ENV", "dev"),
            "service.version": os.getenv("SERVICE_VERSION", "unknown"),
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=full_traces_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer(service_name)
    _LOG.info(
        "Telemetry enabled (endpoint=%s, env=%s, version=%s)",
        full_traces_endpoint,
        resource.attributes.get("deployment.environment"),
        resource.attributes.get("service.version"),
    )

    with tracer.start_as_current_span("startup"):
        pass

    return tracer


def _is_enabled() -> bool:
    val = os.getenv("ENABLE_OTEL", "").lower()
    return val in {"1", "true", "yes", "on"}
