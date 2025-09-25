# Test suite

The `tests` package contains automated checks that cover configuration loading, trigger
processing, event polling, integrations, and the master workflow.  Tests are written with
`pytest`.

## Running tests

```bash
pytest
```

Use `pytest -k <keyword>` to run a subset of tests while iterating on specific modules.

## Coverage overview

| File | Purpose |
|------|---------|
| [`test_config_settings.py`](test_config_settings.py) | Validates that environment variables are parsed and defaulted correctly. |
| [`test_trigger_loader.py`](test_trigger_loader.py) | Verifies trigger word normalisation and fallback logic. |
| [`test_trigger_detection_agent.py`](test_trigger_detection_agent.py) | Ensures trigger classification works across hard/soft triggers and different text fields. |
| [`test_google_calendar_integration.py`](test_google_calendar_integration.py) | Exercises OAuth token handling and event listing behaviour (with network calls mocked). |
| [`test_event_polling_agent.py`](test_event_polling_agent.py) | Confirms that event polling skips birthdays and yields relevant events/contacts. |
| [`test_logs_init.py`](test_logs_init.py) | Covers the public logging factories. |
| [`test_master_workflow_agent_hitl.py`](test_master_workflow_agent_hitl.py) | Tests the end-to-end workflow including human-in-the-loop branching. |
| [`conftest.py`](conftest.py) | Provides shared fixtures used across the test modules. |

Add new tests alongside new modules to maintain high confidence in the automation
workflows.
