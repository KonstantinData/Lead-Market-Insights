"""Simplified MeterProvider and instruments for metrics collection."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from ..resources import Resource
from .export import MetricReader

__all__ = ["MeterProvider"]


class Counter:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: Dict[frozenset[tuple[str, object]], float] = {}

    def add(self, amount: float, attributes: Optional[Dict[str, object]] = None) -> None:
        key = frozenset((attributes or {}).items())
        self._values[key] = self._values.get(key, 0.0) + amount

    def snapshot(self):
        return dict(self._values)


class Histogram:
    def __init__(self, name: str, description: str = "", unit: str = "") -> None:
        self.name = name
        self.description = description
        self.unit = unit
        self._values: Dict[frozenset[tuple[str, object]], List[float]] = {}

    def record(self, value: float, attributes: Optional[Dict[str, object]] = None) -> None:
        key = frozenset((attributes or {}).items())
        self._values.setdefault(key, []).append(value)

    def snapshot(self):
        return {k: list(v) for k, v in self._values.items()}


class Meter:
    def __init__(self, name: str) -> None:
        self.name = name
        self._counters: Dict[str, Counter] = {}
        self._histograms: Dict[str, Histogram] = {}

    def create_counter(self, name: str, description: str = "") -> Counter:
        counter = Counter(name, description)
        self._counters[name] = counter
        return counter

    def create_histogram(self, name: str, description: str = "", unit: str = "") -> Histogram:
        histogram = Histogram(name, description, unit)
        self._histograms[name] = histogram
        return histogram

    def collect(self):
        return list(self._counters.values()), list(self._histograms.values())


class MeterProvider:
    def __init__(
        self,
        *,
        resource: Optional[Resource] = None,
        metric_readers: Optional[Iterable[MetricReader]] = None,
    ) -> None:
        self.resource = resource
        self._metric_readers: List[MetricReader] = []
        self._meters: List[Meter] = []
        for reader in metric_readers or []:
            self.add_metric_reader(reader)

    def add_metric_reader(self, reader: MetricReader) -> None:
        reader._set_meter_provider(self)
        self._metric_readers.append(reader)

    def get_meter(self, name: str) -> Meter:
        meter = Meter(name)
        self._meters.append(meter)
        return meter

    def _collect(self):
        counters = []
        histograms = []
        for meter in self._meters:
            c, h = meter.collect()
            counters.extend(c)
            histograms.extend(h)
        return counters, histograms

    def force_flush(self) -> None:
        for reader in self._metric_readers:
            reader.collect()
