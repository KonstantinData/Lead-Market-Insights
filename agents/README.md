# Agents module

The `agents` package contains the autonomous building blocks that power the event
processing workflow.  Each agent focuses on a narrow responsibility so they can be reused
or replaced independently when integrating the automation platform into different
environments.

## Available agents

| File | Responsibility |
|------|----------------|
| [`email_agent.py`](email_agent.py) | Sends transactional emails via SMTP using plain text and optional HTML bodies. Provides basic logging around delivery success/failure. |
| [`event_polling_agent.py`](event_polling_agent.py) | Connects to Google Calendar and Google Contacts to poll upcoming events and related organiser data while filtering out noise such as birthday reminders. |
| [`extraction_agent.py`](extraction_agent.py) | Extracts core metadata (company name, web domain) from events and flags whether the information set is complete. Designed to be extended with richer parsing. |
| [`human_in_loop_agent.py`](human_in_loop_agent.py) | Facilitates human-in-the-loop interactions for gathering missing event data and confirming dossier creation. Works with a pluggable communication backend or a built-in simulator. |
| [`master_workflow_agent.py`](master_workflow_agent.py) | Implements the end-to-end business logic: polls events, detects triggers, performs extraction, coordinates with humans, and hands confirmed events to downstream systems. |
| [`s3_storage_agent.py`](s3_storage_agent.py) | Uploads files (typically generated logs) to Amazon S3 using the configured credentials. |
| [`trigger_detection_agent.py`](trigger_detection_agent.py) | Detects hard and soft trigger phrases in event summaries/descriptions using normalised keyword matching. |
| [`workflow_orchestrator.py`](workflow_orchestrator.py) | High-level orchestrator that initialises the `MasterWorkflowAgent`, handles error resilience, and finalises runs (e.g., optional S3 log upload). |

## Extending agents

* **Add new automation steps** by creating dedicated agent classes that expose a clear
  method contract (e.g., `process`, `send`, `validate`).
* **Provide dependency injection** through constructor parameters so agents can be reused in
  different contexts and unit tested in isolation.
* **Keep orchestration concerns** in `workflow_orchestrator.py`; agents themselves should
  remain side-effect focused and composable.

Refer to [`tests/test_master_workflow_agent_hitl.py`](../tests/test_master_workflow_agent_hitl.py)
for examples of orchestrating agents within the broader workflow.
