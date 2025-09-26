"""Local PostgreSQL-backed storage helpers for persisting generated artefacts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import psycopg
from psycopg import sql


class PostgresStorageAgent:
    """Persist files into a PostgreSQL table for local inspection.

    Parameters
    ----------
    dsn:
        PostgreSQL connection string (e.g. ``postgresql://user:pass@localhost/db``).
    table_name:
        Target table. Created automatically when missing.
    logger:
        Optional logger used for status and error reporting.
    """

    def __init__(
        self,
        *,
        dsn: str,
        table_name: str = "workflow_log_files",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required for PostgresStorageAgent.")

        self.dsn = dsn
        self.table_name = table_name
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the storage table if it does not already exist."""

        create_statement = sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {table} (
                id BIGSERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ).format(table=sql.Identifier(self.table_name))

        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(create_statement)
            connection.commit()

    def upload_file(self, local_path: str, stored_name: Optional[str] = None) -> bool:
        """Persist a local file in the configured PostgreSQL table.

        The file content is stored as text for easy inspection with SQL queries.
        Returns ``True`` on success and ``False`` when the database rejects the
        insert operation. ``FileNotFoundError`` and other IO errors propagate to
        the caller to surface missing artefacts early.
        """

        path = Path(local_path)
        content = path.read_text(encoding="utf-8")
        target_name = stored_name or path.name

        insert_statement = sql.SQL(
            """
            INSERT INTO {table} (filename, content)
            VALUES (%s, %s)
            """
        ).format(table=sql.Identifier(self.table_name))

        try:
            with psycopg.connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(insert_statement, (target_name, content))
                connection.commit()
            if self.logger:
                self.logger.info(
                    "Stored file '%s' in PostgreSQL table '%s'.",
                    target_name,
                    self.table_name,
                )
            return True
        except psycopg.Error as error:  # pragma: no cover - depends on DB state
            if self.logger:
                self.logger.error(
                    "Failed to store '%s' in PostgreSQL: %s", target_name, error
                )
            return False

