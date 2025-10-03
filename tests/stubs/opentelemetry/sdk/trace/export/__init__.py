"""Span exporters and processors for the stub tracing SDK."""

from __future__ import annotations

"""Span exporter utilities for the in-repo OpenTelemetry shim."""

from typing import Iterable, List  # noqa: E402

__all__ = [
    "SpanExporter",
    "SpanProcessor",
    "SimpleSpanProcessor",
    "InMemorySpanExporter",
    "BatchSpanProcessor",
]


class SpanExporter:
    def export(self, spans: Iterable) -> None:  # pragma: no cover - interface method
        raise NotImplementedError


class SpanProcessor:
    def on_end(self, span) -> None:  # pragma: no cover - interface method
        raise NotImplementedError


class InMemorySpanExporter(SpanExporter):
    def __init__(self) -> None:
        self._finished_spans: List = []

    def export(self, spans: Iterable) -> None:
        self._finished_spans.extend(spans)

    def get_finished_spans(self) -> List:
        return list(self._finished_spans)

    def clear(self) -> None:
        self._finished_spans.clear()


class SimpleSpanProcessor(SpanProcessor):
    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def on_end(self, span) -> None:
        self._exporter.export([span])


class BatchSpanProcessor(SimpleSpanProcessor):
    """The batch processor behaves like the simple processor in the stub."""

    pass
