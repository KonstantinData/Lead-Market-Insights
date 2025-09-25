# Agentic Intelligence Research

This repository contains a modular toolkit for building agent-based process automation
workflows.  The components focus on orchestrating calendar-driven business processes,
collecting the necessary context, requesting human confirmation when required, and
handing off curated events to downstream systems such as CRMs or knowledge bases.

The codebase is organised as a set of focused agents, supporting utilities, and
integration helpers that can be combined to automate a variety of follow-up tasks after
calendar events are created.

## Getting started

### 1. Create a Python environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

All configuration is driven through environment variables or a `.env` file.  The
[`config/README.md`](config/README.md) file describes every supported setting, including
Google OAuth credentials, AWS keys, and optional trigger word overrides.

### 4. Run the orchestrator

The orchestrator wires the agents together and coordinates polling, enrichment, and
escalation flows:

```bash
python -m agents.workflow_orchestrator
```

Individual agents can also be instantiated and exercised directly for targeted tests or
integrations.

## Repository structure

| Path | Description |
|------|-------------|
| [`agents/`](agents/README.md) | Core workflow agents responsible for polling, trigger detection, extraction, human-in-the-loop coordination, S3 uploads, and orchestration. |
| [`integration/`](integration/README.md) | Google Calendar and Google Contacts API integrations, including OAuth token handling. |
| [`config/`](config/README.md) | Centralised configuration loader and trigger word resources. |
| [`logs/`](logs/README.md) | Helpers for structured event/workflow logging with optional S3 upload support. |
| [`utils/`](utils/README.md) | Cross-cutting utilities for text normalisation, trigger loading, and duplicate detection. |
| [`templates/`](templates/README.md) | Shared communication templates (emails, notifications). |
| [`extraction/`](extraction/README.md) | Extension point for advanced data extraction pipelines. |
| [`human_in_the_loop/`](human_in_the_loop/README.md) | Modules dedicated to manual review, approval, and confirmation flows. |
| [`polling/`](polling/README.md) | Scheduling and trigger polling concepts that feed the automation workflows. |
| [`reminders/`](reminders/README.md) | Reminder and escalation helpers built on top of the email agent. |
| [`tests/`](tests/README.md) | Automated test suite covering core agents, integrations, and utilities. |
| [`ARCHIVE/`](ARCHIVE/Readme.md) | Legacy experiments retained for reference. |

## Development workflow

1. **Implement automation logic** within the relevant agent or module.
2. **Update configuration** defaults in `config/config.py` and document any new variables.
3. **Add templates or logging** helpers as required.
4. **Extend or write tests** in `tests/` to capture the expected behaviour.
5. **Run the test suite** (see `tests/README.md` for commands) before opening a pull request.

## Logging and observability

The repository provides dedicated log managers in [`logs/`](logs/README.md) that can persist
event and workflow logs locally or upload them to Amazon S3.  The `MasterWorkflowAgent`
exposes an `upload_log_to_s3` helper that is triggered by the orchestrator when AWS
credentials are configured.

## Human-in-the-loop interactions

Human feedback is requested through the `HumanInLoopAgent`, which can work with a
pluggable communication backend (email, Slack, etc.) or fall back to simulated responses.
The [`human_in_the_loop/`](human_in_the_loop/README.md) directory documents patterns for
custom manual review steps.

## Further reading

* Detailed agent responsibilities: [`agents/README.md`](agents/README.md)
* Google integrations and credential requirements: [`integration/README.md`](integration/README.md)
* Testing guidance: [`tests/README.md`](tests/README.md)

Contributions are welcome—please open issues or pull requests with proposed improvements or
bug fixes.
