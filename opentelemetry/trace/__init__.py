"""Simplified tracing API compatible with the observability helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .._internal.context import get_current_span as _get_current_span_impl
from .._internal.context import set_current_span as _set_current_span_impl

__all__ = [
    "get_tracer",
    "set_tracer_provider",
    "TracerProvider",
    "Span",
    "Status",
    "StatusCode",
    "get_current_span",
]

_TRACER_PROVIDER: Optional[Any] = None


class StatusCode(Enum):
    UNSET = 0
    OK = 1
    ERROR = 2


@dataclass
class Status:
    status_code: StatusCode
    description: str | None = None


def set_tracer_provider(provider) -> None:
    global _TRACER_PROVIDER
    _TRACER_PROVIDER = provider


def get_tracer(name: str):
    if _TRACER_PROVIDER is None:
        raise RuntimeError("Tracer provider has not been configured")
    return _TRACER_PROVIDER.get_tracer(name)


def get_current_span() -> Optional[Span]:
    return _get_current_span_impl()


def _set_current_span(span: Optional[Span]) -> None:
    _set_current_span_impl(span)


TracerProvider = Any
Span = Any
