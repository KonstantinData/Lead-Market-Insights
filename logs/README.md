# Logging helpers

The modules in this package provide structured logging utilities that capture both event
level and workflow level activity. Logs are persisted to the local filesystem for
centralised auditing and easy querying.

## Modules

| File | Description |
|------|-------------|
| [`event_log_manager.py`](event_log_manager.py) | Provides an `EventLogManager` that stores event level payloads as structured JSON files. |
| [`workflow_log_manager.py`](workflow_log_manager.py) | Supplies a `WorkflowLogManager` class for appending run-level log entries such as success, failure, or escalation with optional error payloads. |
| [`__init__.py`](__init__.py) | Exposes convenience factories for importing the log managers directly from the package. |

## Usage

```python
from logs import get_event_log_manager

log_manager = get_event_log_manager()
log_manager.write_event_log("event-123", {"status": "started"})
```

By default logs are stored under ``logs/run_history`` within the repository. Override the location with the ``LOG_STORAGE_DIR`` or ``EVENT_LOG_DIR`` environment variables when running the workflow.

