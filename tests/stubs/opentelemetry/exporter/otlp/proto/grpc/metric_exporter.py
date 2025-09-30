"""Stub OTLP metric exporter used by the in-repo OpenTelemetry shim."""


class OTLPMetricExporter:  # pragma: no cover - simple placeholder
    def export(self, data) -> None:
        # In the stub implementation metrics are not exported anywhere. The
        # method exists to satisfy the observability module API surface.
        pass
