# Logging helpers

The modules in this package provide structured logging utilities that capture both event
level and workflow level activity.  Logs can be written locally and optionally pushed to
Amazon S3 for centralised auditing.

## Modules

| File | Description |
|------|-------------|
| [`event_log_manager.py`](event_log_manager.py) | Provides `get_event_log_manager` to create a ready-to-use log manager that writes structured JSON lines for event activity with optional S3 upload support. |
| [`workflow_log_manager.py`](workflow_log_manager.py) | Supplies a `WorkflowLogManager` class for appending run-level log entries such as success, failure, or escalation with optional error payloads. |
| [`__init__.py`](__init__.py) | Exposes convenience factories for importing the log managers directly from the package. |

## Usage

```python
from logs import get_event_log_manager

log_manager = get_event_log_manager()
log_manager.write_event_log("event-123", {"status": "started"})
```

When AWS credentials and a bucket name are configured (`AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `S3_BUCKET_NAME`), the log managers can
upload generated log files via the [`agents.s3_storage_agent.S3StorageAgent`](../agents/s3_storage_agent.py).
