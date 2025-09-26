"""In-memory metric reader implementations for the stub metrics SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from ...resources import Resource

__all__ = [
    "MetricReader",
    "InMemoryMetricReader",
    "PeriodicExportingMetricReader",
]


class MetricReader:
    def __init__(self) -> None:
        self._meter_provider = None

    def _set_meter_provider(self, provider) -> None:  # pragma: no cover - simple setter
        self._meter_provider = provider

    def collect(self) -> None:
        """Collect metrics from the provider (no-op in stub)."""


@dataclass
class _SumDataPoint:
    attributes: dict
    value: float


@dataclass
class _HistogramDataPoint:
    attributes: dict
    values: List[float]


@dataclass
class _SumData:
    data_points: List[_SumDataPoint]


@dataclass
class _HistogramData:
    data_points: List[_HistogramDataPoint]


@dataclass
class _Metric:
    name: str
    data: object


@dataclass
class _ScopeMetrics:
    metrics: List[_Metric]


@dataclass
class _ResourceMetrics:
    scope_metrics: List[_ScopeMetrics]


@dataclass
class MetricsData:
    resource_metrics: List[_ResourceMetrics]


class InMemoryMetricReader(MetricReader):
    def get_metrics_data(self) -> MetricsData:
        if self._meter_provider is None:
            return MetricsData([])
        counters, histograms = self._meter_provider._collect()
        metrics: List[_Metric] = []
        for counter in counters:
            points = [
                _SumDataPoint(dict(key), value)
                for key, value in counter.snapshot().items()
            ]
            metrics.append(_Metric(counter.name, _SumData(points)))
        for histogram in histograms:
            points = [
                _HistogramDataPoint(dict(key), values)
                for key, values in histogram.snapshot().items()
            ]
            metrics.append(_Metric(histogram.name, _HistogramData(points)))
        return MetricsData([_ResourceMetrics([_ScopeMetrics(metrics)])])


class PeriodicExportingMetricReader(MetricReader):
    def __init__(self, exporter) -> None:
        super().__init__()
        self._exporter = exporter

    def collect(self) -> None:
        if self._meter_provider is None:
            return
        data = InMemoryMetricReader.get_metrics_data(self)
        self._exporter.export(data)
