"""Simplified metrics API compatible with the observability helpers."""

from __future__ import annotations

from typing import Optional

from ..sdk.metrics import MeterProvider as _MeterProvider

__all__ = ["get_meter", "set_meter_provider", "MeterProvider"]

_METER_PROVIDER: Optional[_MeterProvider] = None


def set_meter_provider(provider: _MeterProvider) -> None:
    global _METER_PROVIDER
    _METER_PROVIDER = provider


def get_meter(name: str):
    if _METER_PROVIDER is None:
        raise RuntimeError("Meter provider has not been configured")
    return _METER_PROVIDER.get_meter(name)


MeterProvider = _MeterProvider
