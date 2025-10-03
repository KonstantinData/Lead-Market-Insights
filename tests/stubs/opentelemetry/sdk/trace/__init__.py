"""Tracing primitives for the in-repo OpenTelemetry shim."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ... import trace as trace_api
from ..._internal.context import set_current_span as _set_current_span

__all__ = ["TracerProvider", "Span"]


def _generate_id(bits: int) -> int:
    return random.getrandbits(bits)


@dataclass
class SpanContext:
    trace_id: int
    span_id: int


class Span:
    def __init__(
        self,
        name: str,
        attributes: Optional[Dict[str, object]] = None,
        parent: Optional["Span"] = None,
    ) -> None:
        self.name = name
        self.attributes: Dict[str, object] = dict(attributes or {})
        self._parent_span = parent
        self.parent = parent.context if parent else None
        trace_id = parent.context.trace_id if parent else _generate_id(128)
        self.context = SpanContext(trace_id=trace_id, span_id=_generate_id(64))
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self._ended = False
        self._recorded_exceptions: List[Exception] = []
        self._status = None

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self._recorded_exceptions.append(exc)

    def set_status(self, status) -> None:
        self._status = status

    def end(self) -> None:
        if self._ended:
            return
        self.end_time = time.time()
        self._ended = True


class _SpanContextManager:
    def __init__(self, tracer: "Tracer", span: Span):
        self._tracer = tracer
        self._span = span

    def __enter__(self) -> Span:
        _set_current_span(self._span)
        return self._span

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc is not None and hasattr(self._span, "record_exception"):
                self._span.record_exception(exc)
            self._span.end()
            self._tracer._on_span_end(self._span)
        finally:
            parent = self._span._parent_span
            _set_current_span(parent)


class Tracer:
    def __init__(self, provider: "TracerProvider") -> None:
        self._provider = provider

    def start_as_current_span(
        self, name: str, attributes: Optional[Dict[str, object]] = None
    ):
        parent = trace_api.get_current_span()
        span = Span(name, attributes=attributes, parent=parent)
        return _SpanContextManager(self, span)

    def _on_span_end(self, span: Span) -> None:
        self._provider._on_span_end(span)


class TracerProvider:
    def __init__(self, *, resource=None) -> None:
        self.resource = resource
        self._processors: List[object] = []

    def add_span_processor(self, processor) -> None:
        self._processors.append(processor)

    def get_tracer(self, name: str) -> Tracer:
        return Tracer(self)

    def _on_span_end(self, span: Span) -> None:
        for processor in self._processors:
            processor.on_end(span)
