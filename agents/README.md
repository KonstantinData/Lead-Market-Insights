# Agents module

The `agents` package contains the autonomous building blocks that power the event
processing workflow. Each agent focuses on a narrow responsibility so they can be reused
or replaced independently when integrating the automation platform into different
environments.

## Available agents

| File | Responsibility |
|------|----------------|
| [`email_agent.py`](email_agent.py) | Sends transactional emails via SMTP using plain text and optional HTML bodies while logging delivery success or failure. |
| [`event_polling_agent.py`](event_polling_agent.py) | Connects to Google Calendar and Google Contacts to poll upcoming events, related organiser data, and filters out noise such as birthday reminders. |
| [`extraction_agent.py`](extraction_agent.py) | Extracts core metadata (company name, web domain) from events and flags whether the information set is complete, ready for richer parsing extensions. |
| [`human_in_loop_agent.py`](human_in_loop_agent.py) | Facilitates human-in-the-loop interactions for gathering missing event data and confirming dossier creation via a pluggable communication backend or built-in simulator. |
| [`master_workflow_agent.py`](master_workflow_agent.py) | Implements the end-to-end business logic: polls events, detects triggers, performs extraction, coordinates with humans, and forwards confirmed events downstream. |
| [`local_storage_agent.py`](local_storage_agent.py) | Persists generated artefacts such as workflow log files into a structured local directory tree for inspection. |
| [`trigger_detection_agent.py`](trigger_detection_agent.py) | Detects hard and soft trigger phrases in event summaries and descriptions using normalised keyword matching. |
| [`workflow_orchestrator.py`](workflow_orchestrator.py) | High-level orchestrator that initialises the `MasterWorkflowAgent`, handles error resilience, and finalises runs by recording local log metadata. |

## Extending agents

* **Add new automation steps** by creating dedicated agent classes that expose a clear
  method contract (e.g., `process`, `send`, `validate`).
* **Provide dependency injection** through constructor parameters so agents can be reused in
  different contexts and unit tested in isolation.
* **Keep orchestration concerns** in `workflow_orchestrator.py`; agents themselves should
  remain side-effect focused and composable.

Refer to [`tests/test_master_workflow_agent_hitl.py`](../tests/test_master_workflow_agent_hitl.py)
for examples of orchestrating agents within the broader workflow.

