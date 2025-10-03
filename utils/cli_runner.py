"""Centralised helpers for running asynchronous CLI entrypoints."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
from typing import Awaitable, Callable, Optional, Sequence

AsyncFactory = Callable[[], Awaitable[object]]


def run_cli(entrypoint: AsyncFactory) -> object:
    """Execute an asynchronous CLI entrypoint using ``asyncio.run``."""

    return asyncio.run(entrypoint())


def _resolve_entrypoint(spec: str) -> AsyncFactory:
    module_name, separator, attr_name = spec.partition(":")
    if not separator:
        raise ValueError(
            "Entrypoint specification must be of the form 'package.module:callable'",
        )

    module = importlib.import_module(module_name)
    try:
        entrypoint = getattr(module, attr_name)
    except AttributeError as exc:  # pragma: no cover - defensive guard
        raise ValueError(
            f"Module '{module_name}' has no attribute '{attr_name}'"
        ) from exc

    if not inspect.iscoroutinefunction(entrypoint):
        raise TypeError(
            f"Entrypoint '{spec}' must be an async function with no required arguments",
        )

    return entrypoint


def _parse_args(argv: Optional[Sequence[str]]) -> str:
    parser = argparse.ArgumentParser(description="Run an async CLI entrypoint")
    parser.add_argument(
        "entrypoint",
        metavar="MODULE:CALLABLE",
        help="Dotted path to an async callable exposing a CLI entrypoint",
    )
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    return parsed.entrypoint


def main(argv: Optional[Sequence[str]] = None) -> None:
    entrypoint = _resolve_entrypoint(_parse_args(argv))
    run_cli(entrypoint)


if __name__ == "__main__":
    main()
