# Logging helpers

The modules in this package provide structured logging utilities that capture both event
level and workflow level activity. Logs are persisted to a local PostgreSQL database for
centralised auditing and easy querying.

## Modules

| File | Description |
|------|-------------|
| [`event_log_manager.py`](event_log_manager.py) | Provides an `EventLogManager` that stores event level payloads in a configurable PostgreSQL table. |
| [`workflow_log_manager.py`](workflow_log_manager.py) | Supplies a `WorkflowLogManager` class for appending run-level log entries such as success, failure, or escalation with optional error payloads. |
| [`__init__.py`](__init__.py) | Exposes convenience factories for importing the log managers directly from the package. |

## Usage

```python
from logs import get_event_log_manager

log_manager = get_event_log_manager()
log_manager.write_event_log("event-123", {"status": "started"})
```

Configure the target database via the ``POSTGRES_DSN`` environment variable (or
``DATABASE_URL``). Optional overrides allow custom table names for both event and
workflow logs.

