import logging
from typing import Optional

import psycopg
from psycopg import sql


class WorkflowLogManager:
    """Logging for complete workflows stored in PostgreSQL."""

    def __init__(
        self,
        dsn: str,
        *,
        table_name: str = "workflow_logs",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required for WorkflowLogManager.")

        self.dsn = dsn
        self.table_name = table_name
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._ensure_table()

    def _ensure_table(self) -> None:
        create_statement = sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {table} (
                id BIGSERIAL PRIMARY KEY,
                run_id TEXT NOT NULL,
                step TEXT NOT NULL,
                message TEXT NOT NULL,
                event_id TEXT,
                error TEXT,
                logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ).format(table=sql.Identifier(self.table_name))

        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(create_statement)
            connection.commit()

    def append_log(
        self,
        run_id: str,
        step: str,
        message: str,
        event_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Append a log entry to the workflow log."""

        statement = sql.SQL(
            """
            INSERT INTO {table} (run_id, step, message, event_id, error)
            VALUES (%s, %s, %s, %s, %s)
            """
        ).format(table=sql.Identifier(self.table_name))

        try:
            with psycopg.connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        statement, (run_id, step, message, event_id, error)
                    )
                connection.commit()
            if self.logger:
                self.logger.info(
                    "Workflow log appended for run %s (step: %s)",
                    run_id,
                    step,
                )
        except psycopg.Error as exc:
            if self.logger:
                self.logger.error(
                    "Error in workflow logging for run %s (step: %s): %s",
                    run_id,
                    step,
                    exc,
                )
            raise


# Example:
# wlm = WorkflowLogManager("postgresql://user:pass@localhost/db")
# wlm.append_log("run42", "start", "Workflow started", event_id="evt123")
