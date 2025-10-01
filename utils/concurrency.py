"""Asynchronous concurrency primitives for external service coordination."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable, Iterable, List, Optional

logger = logging.getLogger(__name__)

try:  # Python 3.11+
    from builtins import ExceptionGroup  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Python 3.10 fallback
    try:
        from types import ExceptionGroup  # type: ignore[attr-defined]
    except ImportError:  # pragma: no cover - minimal shim
        class ExceptionGroup(Exception):  # type: ignore[override]
            """Lightweight ExceptionGroup for Python 3.10 environments."""

            def __init__(self, message: str, exceptions: Iterable[BaseException]) -> None:
                super().__init__(message)
                self.exceptions = list(exceptions)

_DEFAULT_HUBSPOT_LIMIT = 5
_DEFAULT_RESEARCH_LIMIT = 3


class LoggingSemaphore:
    """Semaphore wrapper that logs concurrent acquisitions at debug level."""

    def __init__(self, name: str, limit: int) -> None:
        self._name = name
        self._limit = max(1, int(limit))
        self._semaphore = asyncio.Semaphore(self._limit)
        self._lock = asyncio.Lock()
        self._active = 0

    async def __aenter__(self) -> "LoggingSemaphore":
        await self._semaphore.acquire()
        async with self._lock:
            self._active += 1
            logger.debug(
                "%s concurrency acquired (%d/%d)",
                self._name,
                self._active,
                self._limit,
            )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> Optional[bool]:
        async with self._lock:
            self._active = max(0, self._active - 1)
            logger.debug(
                "%s concurrency released (%d/%d)",
                self._name,
                self._active,
                self._limit,
            )
        self._semaphore.release()
        return None

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def active(self) -> int:
        return self._active


def _resolve_limit(env_name: str, default: int) -> int:
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        logger.warning(
            "Invalid value for %s: expected integer but received %r. Using default %d.",
            env_name,
            raw_value,
            default,
        )
        return default

    if value < 1:
        logger.warning(
            "%s must be greater than zero; received %d. Using default %d.",
            env_name,
            value,
            default,
        )
        return default

    return value


def _normalise_limit(value: Optional[int], *, fallback: int, name: str) -> int:
    if value is None:
        return fallback

    try:
        coerced = int(value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid override for %s: expected integer but received %r. Keeping %d.",
            name,
            value,
            fallback,
        )
        return fallback

    if coerced < 1:
        logger.warning(
            "%s override must be positive; received %d. Keeping %d.",
            name,
            coerced,
            fallback,
        )
        return fallback

    return coerced


_HUBSPOT_LIMIT = _resolve_limit("MAX_CONCURRENT_HUBSPOT", _DEFAULT_HUBSPOT_LIMIT)
_RESEARCH_LIMIT = _resolve_limit("MAX_CONCURRENT_RESEARCH", _DEFAULT_RESEARCH_LIMIT)

HUBSPOT_SEMAPHORE = LoggingSemaphore("hubspot", _HUBSPOT_LIMIT)
RESEARCH_TASK_SEMAPHORE = LoggingSemaphore("research", _RESEARCH_LIMIT)


async def run_in_task_group(
    runners: Iterable[Callable[[], Awaitable[None]]],
) -> None:
    """Execute runner callables concurrently with TaskGroup-like semantics."""

    runners_list = list(runners)
    if not runners_list:
        return

    if hasattr(asyncio, "TaskGroup"):
        async with asyncio.TaskGroup() as group:  # type: ignore[attr-defined]
            for runner in runners_list:
                group.create_task(runner())
        return

    tasks: List[asyncio.Task[None]] = [asyncio.create_task(runner()) for runner in runners_list]
    pending: List[asyncio.Task[None]] = tasks.copy()
    exceptions: List[BaseException] = []

    try:
        while pending:
            done, pending_set = await asyncio.wait(
                pending, return_when=asyncio.FIRST_EXCEPTION
            )

            for task in done:
                try:
                    task.result()
                except BaseException as exc:  # pragma: no cover - exercised in tests
                    exceptions.append(exc)

            pending = list(pending_set)

            if exceptions:
                for task in pending:
                    task.cancel()
                cancel_results = await asyncio.gather(
                    *pending, return_exceptions=True
                )
                for result in cancel_results:
                    if isinstance(result, BaseException):
                        exceptions.append(result)
                pending = []
                break

        if exceptions:
            raise ExceptionGroup("Task group failure", exceptions)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def reload_limits(
    *, hubspot: Optional[int] = None, research: Optional[int] = None
) -> None:
    """Reconfigure concurrency limits at runtime.

    Primarily intended for tests where environment variables are modified on the
    fly. When no explicit overrides are provided the current limits remain
    unchanged.
    """

    global HUBSPOT_SEMAPHORE, RESEARCH_TASK_SEMAPHORE, _HUBSPOT_LIMIT, _RESEARCH_LIMIT

    resolved_hubspot = _normalise_limit(
        hubspot,
        fallback=_resolve_limit("MAX_CONCURRENT_HUBSPOT", _HUBSPOT_LIMIT),
        name="MAX_CONCURRENT_HUBSPOT",
    )
    resolved_research = _normalise_limit(
        research,
        fallback=_resolve_limit("MAX_CONCURRENT_RESEARCH", _RESEARCH_LIMIT),
        name="MAX_CONCURRENT_RESEARCH",
    )

    if resolved_hubspot != _HUBSPOT_LIMIT:
        logger.info(
            "Updating HubSpot concurrency limit from %d to %d",
            _HUBSPOT_LIMIT,
            resolved_hubspot,
        )
    if resolved_research != _RESEARCH_LIMIT:
        logger.info(
            "Updating research concurrency limit from %d to %d",
            _RESEARCH_LIMIT,
            resolved_research,
        )

    _HUBSPOT_LIMIT = resolved_hubspot
    _RESEARCH_LIMIT = resolved_research
    HUBSPOT_SEMAPHORE = LoggingSemaphore("hubspot", _HUBSPOT_LIMIT)
    RESEARCH_TASK_SEMAPHORE = LoggingSemaphore("research", _RESEARCH_LIMIT)


__all__ = [
    "HUBSPOT_SEMAPHORE",
    "LoggingSemaphore",
    "RESEARCH_TASK_SEMAPHORE",
    "run_in_task_group",
    "reload_limits",
]
