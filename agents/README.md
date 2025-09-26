# Agents module

The `agents` package contains the autonomous building blocks that power the event
processing workflow. Each agent focuses on a narrow responsibility so they can be reused
or replaced independently when integrating the automation platform into different
environments.

## Available agents

| File | Responsibility |
|------|----------------|
| [`crm_agent.py`](crm_agent.py) | Default CRM sink that logs qualified events. Replace it with a HubSpot, Salesforce, or custom integration by implementing the CRM interface. |
| [`email_agent.py`](email_agent.py) | Sends transactional emails via SMTP using plain text and optional HTML bodies while logging delivery success or failure. |
| [`event_polling_agent.py`](event_polling_agent.py) | Connects to Google Calendar and Google Contacts to poll upcoming events, related organiser data, and filters out noise such as birthday reminders. |
| [`extraction_agent.py`](extraction_agent.py) | Extracts core metadata (company name, web domain) from events and flags whether the information set is complete, ready for richer parsing extensions. |
| [`human_in_loop_agent.py`](human_in_loop_agent.py) | Facilitates human-in-the-loop interactions for gathering missing event data and confirming dossier creation via a pluggable communication backend or built-in simulator. |
| [`master_workflow_agent.py`](master_workflow_agent.py) | Implements the end-to-end business logic: polls events, detects triggers, performs extraction, coordinates with humans, and forwards confirmed events downstream. |
| [`local_storage_agent.py`](local_storage_agent.py) | Persists generated artefacts such as workflow log files into a structured local directory tree for inspection. |
| [`trigger_detection_agent.py`](trigger_detection_agent.py) | Detects hard and soft trigger phrases in event summaries and descriptions using normalised keyword matching. |
| [`workflow_orchestrator.py`](workflow_orchestrator.py) | High-level orchestrator that initialises the `MasterWorkflowAgent`, handles error resilience, and finalises runs by recording local log metadata. |

## Extension points

Reusable abstract base classes live in [`interfaces/`](interfaces). They define the minimum
surface area that each workflow stage must expose:

| Interface | Required methods | Default implementation |
|-----------|-----------------|------------------------|
| `BasePollingAgent` | `poll()`, `poll_contacts()` | [`EventPollingAgent`](event_polling_agent.py) |
| `BaseTriggerAgent` | `check(event)` | [`TriggerDetectionAgent`](trigger_detection_agent.py) |
| `BaseExtractionAgent` | `extract(event)` | [`ExtractionAgent`](extraction_agent.py) |
| `BaseHumanAgent` | `request_info(event, extracted)`, `request_dossier_confirmation(event, info)` | [`HumanInLoopAgent`](human_in_loop_agent.py) |
| `BaseCrmAgent` | `send(event, info)` | [`LoggingCrmAgent`](crm_agent.py) |

Concrete implementations register themselves with the registry defined in
[`factory.py`](factory.py) using the `@register_agent` decorator. The factory supports naming
multiple variants per interface and exposes `create_agent()` to instantiate them on demand.

## Selecting agents via configuration

`MasterWorkflowAgent` resolves all dependencies through the factory. Override the default
implementations with either environment variables or a configuration file:

* **Environment variables** – set `POLLING_AGENT`, `TRIGGER_AGENT`, `EXTRACTION_AGENT`,
  `HUMAN_AGENT`, or `CRM_AGENT` to the registered name of an alternative implementation.
* **Configuration file** – point `AGENT_CONFIG_FILE` to a JSON or YAML document containing an
  `agents` section. Example:

```yaml
agents:
  polling: "custom_polling"
  crm_agent: "hubspot"
```

## Implementing a custom agent

1. Create a class that subclasses the relevant base interface.
2. Decorate the class with `@register_agent(<Interface>, "my_agent", is_default=False)`.
3. Optionally add docs/tests.
4. Select the new implementation via configuration.

Refer to [`tests/test_master_workflow_agent_hitl.py`](../tests/test_master_workflow_agent_hitl.py)
for examples of orchestrating agents within the broader workflow.

