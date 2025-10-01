"""
Central OpenTelemetry tracing setup.

Activation rules:
- Set environment variable ENABLE_OTEL=true (or 1 / yes / on)
- Set OTEL_EXPORTER_OTLP_ENDPOINT to the base OTLP HTTP endpoint
  Example: http://otel-collector:4318   (the /v1/traces path is appended automatically)

If either condition is missing, telemetry is skipped silently (only one log line).

This module only enables traces. Metrics/logs can be added later if truly needed.
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
    """
    Initialize OpenTelemetry tracing if enabled.

    Returns:
        A tracer instance if telemetry is enabled, otherwise None.

    Conditions:
    - ENABLE_OTEL must be set to a truthy value.
    - OTEL_EXPORTER_OTLP_ENDPOINT must be defined (base URL, no /v1/traces suffix).

    Example:
        ENABLE_OTEL=true
        OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
    """
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
            # Add more attributes if needed:
            # "deployment.environment": os.getenv("APP_ENV", "dev"),
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=full_traces_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer(service_name)

    _LOG.info("Telemetry enabled (traces endpoint: %s)", full_traces_endpoint)

    # Optional startup span (helps confirm wiring)
    with tracer.start_as_current_span("startup"):
        pass

    return tracer


def _is_enabled() -> bool:
    val = os.getenv("ENABLE_OTEL", "").lower()
    return val in {"1", "true", "yes", "on"}
