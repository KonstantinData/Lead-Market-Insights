"""Deprecated S3 storage agent placeholder.

The project now persists artefacts locally in PostgreSQL. Import and use
``agents.postgres_storage_agent.PostgresStorageAgent`` instead.
"""

from __future__ import annotations

from typing import Any


class S3StorageAgent:
    """Placeholder that raises immediately to highlight the deprecation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "S3 storage has been disabled. Configure PostgresStorageAgent instead."
        )

    def upload_file(self, *args: Any, **kwargs: Any) -> bool:  # pragma: no cover
        raise RuntimeError(
            "S3 storage has been disabled. Configure PostgresStorageAgent instead."
        )
