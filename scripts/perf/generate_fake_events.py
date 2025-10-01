"""Utility to generate synthetic calendar events for performance testing.

The script can be configured via environment variables:

* ``PERF_EVENT_COUNT`` – number of events to emit (default: 100)
* ``PERF_EVENT_START`` – ISO timestamp used as base for the first event
  (default: ``2024-01-01T09:00:00``)
* ``PERF_EVENT_INCREMENT_MINUTES`` – minutes added between subsequent events
  (default: 30)
* ``PERF_OUTPUT_PATH`` – destination JSON file (default: ``logs/perf/events.json``)
* ``PERF_RANDOM_SEED`` – optional seed for deterministic output.

The generated payload resembles the structure returned by the Google Calendar API
with a reduced set of fields that are used throughout the codebase.  The goal is
not to perfectly mimic the upstream service but to provide a lightweight set of
fixtures that unlocks load-testing scenarios without requiring access to real
customer data.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


@dataclass
class SyntheticEvent:
    """Representation of a synthetic calendar event."""

    id: str
    summary: str
    description: str
    start: str
    end: str
    location: str
    attendees: List[dict]

    @classmethod
    def from_index(
        cls,
        index: int,
        *,
        base_start: datetime,
        delta: timedelta,
        duration: timedelta,
    ) -> "SyntheticEvent":
        start = base_start + delta * index
        end = start + duration

        def fmt(dt: datetime) -> str:
            return dt.strftime(ISO_FORMAT)

        return cls(
            id=f"perf-event-{index:05d}",
            summary=f"Performance Test Event #{index}",
            description="Synthetic event generated for load testing",
            start=fmt(start),
            end=fmt(end),
            location=random.choice(
                [
                    "Zoom",
                    "Teams",
                    "Meeting Room A",
                    "Meeting Room B",
                ]
            ),
            attendees=[
                {
                    "email": f"participant{participant}@example.com",
                    "responseStatus": random.choice(["accepted", "tentative", "needsAction"]),
                }
                for participant in range(1, random.randint(2, 6))
            ],
        )


def _ensure_directory(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def generate_events(*, count: int, base_start: datetime, step_minutes: int) -> Iterable[SyntheticEvent]:
    duration_minutes = max(step_minutes // 2, 15)
    duration = timedelta(minutes=duration_minutes)
    delta = timedelta(minutes=step_minutes)
    for idx in range(count):
        yield SyntheticEvent.from_index(
            idx,
            base_start=base_start,
            delta=delta,
            duration=duration,
        )


def load_config() -> dict:
    return {
        "count": int(os.getenv("PERF_EVENT_COUNT", "100")),
        "base_start": os.getenv("PERF_EVENT_START", "2024-01-01T09:00:00"),
        "step_minutes": int(os.getenv("PERF_EVENT_INCREMENT_MINUTES", "30")),
        "output_path": os.getenv("PERF_OUTPUT_PATH", "logs/perf/events.json"),
        "seed": os.getenv("PERF_RANDOM_SEED"),
    }


def main() -> None:
    config = load_config()
    seed = config["seed"]
    if seed is not None:
        random.seed(seed)

    base_start = datetime.fromisoformat(config["base_start"])
    if base_start.tzinfo is None:
        base_start = base_start.replace(tzinfo=timezone.utc)

    events = list(
        generate_events(
            count=config["count"],
            base_start=base_start,
            step_minutes=config["step_minutes"],
        )
    )
    output_path = Path(config["output_path"])
    _ensure_directory(output_path)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump([asdict(event) for event in events], handle, indent=2)

    print(f"Generated {len(events)} synthetic events at {output_path}")


if __name__ == "__main__":
    main()
