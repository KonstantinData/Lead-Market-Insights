"""Stub OTLP span exporter used by the in-repo OpenTelemetry shim."""


class OTLPSpanExporter:  # pragma: no cover - simple placeholder
    def export(self, spans) -> None:
        # No-op exporter used during testing.
        pass
