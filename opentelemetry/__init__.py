"""Minimal in-repo OpenTelemetry stubs used for testing instrumentation.

This package intentionally implements only the APIs exercised by the
project's observability helpers and smoke tests.  It is not a complete
implementation of OpenTelemetry, but it emulates the behaviour required
for metrics and tracing collection in an offline environment where the
real dependency cannot be installed.
"""

from . import metrics, trace  # noqa: F401

__all__ = ["metrics", "trace"]
