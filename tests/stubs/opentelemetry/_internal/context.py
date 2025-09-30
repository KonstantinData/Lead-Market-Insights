"""Shared context utilities for span management."""

from __future__ import annotations

import contextvars
from typing import Optional

_CURRENT_SPAN: contextvars.ContextVar[Optional[object]] = contextvars.ContextVar(
    "otel_current_span", default=None
)


def get_current_span():
    return _CURRENT_SPAN.get()


def set_current_span(span) -> None:
    _CURRENT_SPAN.set(span)
