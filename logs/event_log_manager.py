import logging
from datetime import datetime
from typing import Any, Dict, Optional

import psycopg
from psycopg import sql
from psycopg.types.json import Json


class EventLogManager:
    """
    Manages event logs stored in PostgreSQL: event_logs(event_id, payload, last_updated).
    """

    def __init__(
        self,
        dsn: str,
        *,
        table_name: str = "event_logs",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required for EventLogManager.")

        self.dsn = dsn
        self.table_name = table_name
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._ensure_table()

    def _ensure_table(self) -> None:
        create_statement = sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {table} (
                event_id TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ).format(table=sql.Identifier(self.table_name))

        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(create_statement)
            connection.commit()

    def _log_success(self, action: str, event_id: str) -> None:
        if self.logger:
            self.logger.info("Event log %s: %s", action, event_id)

    def write_event_log(self, event_id: str, data: Dict[str, Any]) -> None:
        """Insert or update the event log in PostgreSQL."""

        data = dict(data)  # Avoid mutating caller state
        data["last_updated"] = datetime.utcnow().isoformat()

        statement = sql.SQL(
            """
            INSERT INTO {table} (event_id, payload, last_updated)
            VALUES (%s, %s, NOW())
            ON CONFLICT (event_id) DO UPDATE SET
                payload = EXCLUDED.payload,
                last_updated = EXCLUDED.last_updated
            """
        ).format(table=sql.Identifier(self.table_name))

        try:
            with psycopg.connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, (event_id, Json(data)))
                connection.commit()
            self._log_success("written", event_id)
        except psycopg.Error as error:
            if self.logger:
                self.logger.error("Error writing event log %s: %s", event_id, error)
            raise

    def read_event_log(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Read the event log from PostgreSQL. Returns None if not found."""

        query = sql.SQL(
            "SELECT payload FROM {table} WHERE event_id = %s"
        ).format(table=sql.Identifier(self.table_name))

        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (event_id,))
                row = cursor.fetchone()

        if row is None:
            if self.logger:
                self.logger.warning("No event log found for %s", event_id)
            return None

        return row[0]

    def delete_event_log(self, event_id: str) -> None:
        """Delete the event log from PostgreSQL."""

        statement = sql.SQL(
            "DELETE FROM {table} WHERE event_id = %s"
        ).format(table=sql.Identifier(self.table_name))

        try:
            with psycopg.connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, (event_id,))
                connection.commit()
            self._log_success("deleted", event_id)
        except psycopg.Error as error:
            if self.logger:
                self.logger.error("Error deleting event log %s: %s", event_id, error)
            raise


# Example:
# manager = EventLogManager("postgresql://user:pass@localhost/db")
# manager.write_event_log("123", {"status": "done"})
