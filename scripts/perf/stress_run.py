"""Execute a synthetic load-test run for the workflow orchestrator.

The script is intentionally self-contained so that it can be executed in CI as
well as locally without requiring access to external APIs.  It simulates event
processing by spinning up a configurable number of asynchronous tasks that issue
"HubSpot" calls with controllable latency and failure rates.  Each event run
produces structured measurements that are persisted for further analysis.

Environment variables
---------------------
``PERF_EVENT_COUNT``
    Number of synthetic events to process.  Default: ``100``.
``PERF_PARALLELISM``
    Maximum number of concurrent workers.  Default: ``10``.
``PERF_FAULT_RATE``
    Probability (0.0 – 1.0) that the simulated API call fails with HTTP 500.
    Default: ``0.2``.
``PERF_MAX_RETRIES``
    Number of retries for each event before it is marked as failed.  Default: ``3``.
``PERF_BASE_LATENCY_MS``
    Baseline latency in milliseconds for the simulated API call.  Default: ``150``.
``PERF_JITTER_MS``
    Maximum random jitter added to the latency.  Default: ``100``.
``PERF_RESULTS_PATH``
    File path where JSON encoded measurements are written.  Default:
    ``logs/perf/results.json``.
``PERF_ENABLE_PROMETHEUS``
    When set to ``1`` a small Prometheus exporter is started on
    ``PERF_PROMETHEUS_PORT`` (default ``9464``).
``PERF_RANDOM_SEED``
    Optional random seed for reproducibility.

Example usage::

    PERF_EVENT_COUNT=200 PERF_PARALLELISM=20 python scripts/perf/stress_run.py

"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import statistics
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional, Tuple

try:  # Optional dependency
    from prometheus_client import CollectorRegistry, Gauge, start_http_server
except Exception:  # pragma: no cover - optional dependency
    CollectorRegistry = Gauge = start_http_server = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from prometheus_client import CollectorRegistry as PromCollectorRegistry
    from prometheus_client import Gauge as PromGauge
else:
    PromCollectorRegistry = PromGauge = Any


def _load_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:  # pragma: no cover - defensive programming
        raise ValueError(f"Environment variable {name} must be a float") from exc


def _load_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive programming
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _ensure_directory(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class EventMetrics:
    event_id: str
    started_at: float
    finished_at: float
    latency_ms: float
    retries: int
    success: bool


@dataclass
class LoadConfig:
    event_count: int
    parallelism: int
    fault_rate: float
    max_retries: int
    base_latency_ms: float
    jitter_ms: float
    results_path: Path
    enable_prometheus: bool
    prometheus_port: int
    random_seed: Optional[int]


def load_config() -> LoadConfig:
    return LoadConfig(
        event_count=_load_env_int("PERF_EVENT_COUNT", 100),
        parallelism=_load_env_int("PERF_PARALLELISM", 10),
        fault_rate=_load_env_float("PERF_FAULT_RATE", 0.2),
        max_retries=_load_env_int("PERF_MAX_RETRIES", 3),
        base_latency_ms=_load_env_float("PERF_BASE_LATENCY_MS", 150.0),
        jitter_ms=_load_env_float("PERF_JITTER_MS", 100.0),
        results_path=Path(os.getenv("PERF_RESULTS_PATH", "logs/perf/results.json")),
        enable_prometheus=os.getenv("PERF_ENABLE_PROMETHEUS") == "1",
        prometheus_port=_load_env_int("PERF_PROMETHEUS_PORT", 9464),
        random_seed=int(os.getenv("PERF_RANDOM_SEED")) if os.getenv("PERF_RANDOM_SEED") else None,
    )


async def simulate_hubspot_call(
    *,
    event_id: str,
    base_latency_ms: float,
    jitter_ms: float,
    fault_rate: float,
) -> None:
    latency_ms = base_latency_ms + random.random() * jitter_ms
    await asyncio.sleep(latency_ms / 1000.0)
    if random.random() < fault_rate:
        raise RuntimeError(f"HubSpot call failed for {event_id}")


@asynccontextmanager
async def record_concurrency(metrics: Dict[str, int]) -> AsyncIterator[None]:
    metrics["current"] += 1
    metrics["max"] = max(metrics["max"], metrics["current"])
    try:
        yield
    finally:
        metrics["current"] -= 1


async def process_event(event_id: str, config: LoadConfig, concurrency_metrics: Dict[str, int]) -> EventMetrics:
    start_time = time.perf_counter()
    retries = 0
    success = False

    async with record_concurrency(concurrency_metrics):
        for attempt in range(1, config.max_retries + 2):
            try:
                await simulate_hubspot_call(
                    event_id=event_id,
                    base_latency_ms=config.base_latency_ms,
                    jitter_ms=config.jitter_ms,
                    fault_rate=config.fault_rate,
                )
            except RuntimeError:
                retries += 1
                if attempt > config.max_retries:
                    break
            else:
                success = True
                break

    finished_at = time.perf_counter()
    latency_ms = (finished_at - start_time) * 1000.0
    return EventMetrics(
        event_id=event_id,
        started_at=start_time,
        finished_at=finished_at,
        latency_ms=latency_ms,
        retries=retries,
        success=success,
    )


async def run_load_test(config: LoadConfig) -> Dict[str, object]:
    logging.info(
        "Starting load test with %s events (parallelism=%s, fault_rate=%.0f%%)",
        config.event_count,
        config.parallelism,
        config.fault_rate * 100,
    )
    concurrency_metrics: Dict[str, int] = {"current": 0, "max": 0}
    semaphore = asyncio.Semaphore(config.parallelism)
    events: List[EventMetrics] = []

    async def worker(event_id: str) -> None:
        async with semaphore:
            result = await process_event(event_id, config, concurrency_metrics)
            events.append(result)

    tasks = [asyncio.create_task(worker(f"perf-event-{idx:05d}")) for idx in range(config.event_count)]
    await asyncio.gather(*tasks)

    error_count = sum(1 for event in events if not event.success)
    retry_avg = statistics.mean(event.retries for event in events) if events else 0.0
    latency_avg = statistics.mean(event.latency_ms for event in events) if events else 0.0
    latency_p95 = statistics.quantiles(
        [event.latency_ms for event in events],
        n=20,
    )[18] if len(events) >= 20 else latency_avg

    config_payload = asdict(config)
    config_payload["results_path"] = str(config.results_path)

    results = {
        "config": config_payload,
        "events": [asdict(event) for event in events],
        "metrics": {
            "average_latency_ms": latency_avg,
            "p95_latency_ms": latency_p95,
            "max_concurrent_tasks": concurrency_metrics["max"],
            "average_retries": retry_avg,
            "error_rate": error_count / len(events) if events else 0.0,
            "error_count": error_count,
        },
    }
    return results


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _start_prometheus(
    config: LoadConfig,
) -> Optional[Tuple[PromCollectorRegistry, Dict[str, PromGauge]]]:
    if not config.enable_prometheus:
        return None
    if CollectorRegistry is None or Gauge is None or start_http_server is None:
        logging.warning("prometheus_client not available – exporter disabled")
        return None

    registry = CollectorRegistry()
    gauges: Dict[str, PromGauge] = {
        "average_latency_ms": Gauge("perf_average_latency_ms", "Average latency", registry=registry),
        "p95_latency_ms": Gauge("perf_p95_latency_ms", "95th percentile latency", registry=registry),
        "max_concurrent_tasks": Gauge(
            "perf_max_concurrent_tasks",
            "Maximum observed concurrency",
            registry=registry,
        ),
        "average_retries": Gauge("perf_average_retries", "Average retries per event", registry=registry),
        "error_rate": Gauge("perf_error_rate", "Error rate", registry=registry),
    }

    start_http_server(config.prometheus_port, registry=registry)
    logging.info("Prometheus exporter listening on :%s", config.prometheus_port)
    return registry, gauges


def _update_prometheus(
    registry_info: Optional[Tuple[PromCollectorRegistry, Dict[str, PromGauge]]],
    metrics: Dict[str, float],
) -> None:
    if not registry_info:
        return
    registry, gauges = registry_info
    for key, value in metrics.items():
        gauge = gauges.get(key)
        if gauge is not None:
            gauge.set(value)


def _persist_results(path: Path, results: Dict[str, object]) -> None:
    _ensure_directory(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)


async def _async_main() -> None:
    config = load_config()
    if config.random_seed is not None:
        random.seed(config.random_seed)

    prometheus_info = _start_prometheus(config)
    results = await run_load_test(config)
    _update_prometheus(prometheus_info, results["metrics"])
    _persist_results(config.results_path, results)

    logging.info("Load test finished. Metrics written to %s", config.results_path)


def main() -> None:
    _setup_logging()
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
