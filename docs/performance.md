# Performance & Load Baseline

This document captures the initial performance baseline for the synthetic load
scenario introduced in PR10.

## Scenario definition

| Parameter | Value | Notes |
| --- | --- | --- |
| Event count | 100 | Generated via `scripts/perf/generate_fake_events.py` |
| Parallelism | 10 | Controlled by `PERF_PARALLELISM` |
| Fault rate | 20 % | Injected via `PERF_FAULT_RATE=0.2` |
| Max retries | 3 | Hard cap per event |
| Base latency | 150 ms | Artificial processing latency |
| Jitter | 100 ms | Randomized latency variance |
| Random seed | 42 | Ensures reproducibility |

Commands executed:

```bash
python scripts/perf/generate_fake_events.py
PERF_RANDOM_SEED=42 python -m utils.cli_runner scripts.perf.stress_run:cli
```

## Baseline metrics

The resulting JSON artifact (`logs/perf/results.json`) contains per-event and
aggregate measurements. Key metrics:

* **Average latency:** 246.68 ms
* **95th percentile latency:** 449.08 ms
* **Maximum concurrent tasks:** 10 (matching configured parallelism)
* **Average retries per event:** 0.23
* **Error rate:** 0 %

## Observations & follow-up

* The retry budget of three attempts was sufficient to recover all injected
  faults in this run, resulting in zero permanent failures.
* No abnormal memory growth observed during the short-lived synthetic run.
* The Prometheus exporter can be enabled via `PERF_ENABLE_PROMETHEUS=1` if
  additional metric scraping is required.
* Future iterations should compare real workflow performance against this
  baseline and adjust fault injection ratios to match production error rates.
