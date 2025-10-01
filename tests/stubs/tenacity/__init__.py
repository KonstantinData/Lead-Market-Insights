"""Lightweight subset of the Tenacity API used for retrying async operations."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Optional, Tuple, Type, Union


class RetryError(Exception):
    """Raised when the retry decorator exhausts all attempts."""


class retry_if_exception_type:
    def __init__(self, exception_types: Union[Type[BaseException], Tuple[Type[BaseException], ...]]):
        if not isinstance(exception_types, tuple):
            exception_types = (exception_types,)
        self._types = exception_types

    def __call__(self, exc: BaseException) -> bool:
        return isinstance(exc, self._types)

    def should_retry(self, exc: BaseException) -> bool:
        return isinstance(exc, self._types)


@dataclass
class stop_after_attempt:
    attempts: int

    def should_stop(self, attempt: int) -> bool:
        return attempt >= self.attempts


@dataclass
class wait_exponential_jitter:
    initial: float = 0.5
    max: float = 8.0

    def compute(self, attempt: int) -> float:
        base = min(self.initial * (2 ** (attempt - 1)), self.max)
        jitter = random.random() * self.initial
        return min(base + jitter, self.max)


@dataclass
class wait_fixed:
    value: float

    def compute(self, attempt: int) -> float:  # noqa: ARG002 - signature parity
        return self.value


@dataclass
class RetryState:
    attempt_number: int


def retry(
    *,
    reraise: bool = False,
    stop: stop_after_attempt,
    wait: wait_exponential_jitter,
    retry: retry_if_exception_type,
    before: Optional[Callable[[RetryState], None]] = None,
):
    """Simple retry decorator supporting async callables."""

    def decorator(fn: Callable[..., Any]):
        if asyncio.iscoroutinefunction(fn):

            async def async_wrapper(*args: Any, **kwargs: Any):
                attempt = 1
                while True:
                    state = RetryState(attempt_number=attempt)
                    if before:
                        before(state)
                    try:
                        return await fn(*args, **kwargs)
                    except Exception as exc:  # noqa: BLE001
                        if not retry.should_retry(exc) or stop.should_stop(attempt):
                            if reraise:
                                raise
                            raise RetryError from exc
                        delay = wait.compute(attempt)
                        attempt += 1
                        if delay > 0:
                            await asyncio.sleep(delay)

            async_wrapper.retry = SimpleNamespace(wait=wait, stop=stop, retry=retry)
            async_wrapper.retry_with = lambda **overrides: retry(
                reraise=overrides.get("reraise", reraise),
                stop=overrides.get("stop", stop),
                wait=overrides.get("wait", wait),
                retry=overrides.get("retry", retry),
                before=overrides.get("before", before),
            )
            async_wrapper.statistics = {}

            return async_wrapper

        def sync_wrapper(*args: Any, **kwargs: Any):
            attempt = 1
            while True:
                state = RetryState(attempt_number=attempt)
                if before:
                    before(state)
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    if not retry.should_retry(exc) or stop.should_stop(attempt):
                        if reraise:
                            raise
                        raise RetryError from exc
                    delay = wait.compute(attempt)
                    attempt += 1
                    if delay > 0:
                        time.sleep(delay)

        sync_wrapper.retry = SimpleNamespace(wait=wait, stop=stop, retry=retry)
        sync_wrapper.retry_with = lambda **overrides: retry(
            reraise=overrides.get("reraise", reraise),
            stop=overrides.get("stop", stop),
            wait=overrides.get("wait", wait),
            retry=overrides.get("retry", retry),
            before=overrides.get("before", before),
        )
        sync_wrapper.statistics = {}

        return sync_wrapper

    return decorator


__all__ = [
    "RetryError",
    "retry",
    "retry_if_exception_type",
    "stop_after_attempt",
    "wait_exponential_jitter",
    "wait_fixed",
]
