# Compliance and audit controls

The automation workflow must balance operational efficiency with regulatory and customer
commitments. This guide summarises the mandatory controls that govern how data flows through
the agents and how teams should extend the platform.

## Data classification and retention

| Data type | Source | Storage location | Retention | Notes |
| --------- | ------ | ---------------- | --------- | ----- |
| Calendar events | Google Calendar API | `log_storage/run_history/events` | 30 days by default | PII is masked before persistence. |
| Workflow metadata | Orchestrator runtime | `log_storage/run_history/workflows` | 90 days | Includes run IDs, agent decisions, latency metrics. |
| Human review transcripts | Human-in-the-loop agent | Configurable (`LOG_STORAGE_DIR` or remote queue) | 90 days | Masked when `COMPLIANCE_MODE=strict`. |
| CRM payloads | CRM agent dispatch | Downstream CRM / data warehouse | Per downstream policy | Attach `run_id` and masking hints. |

Retention values can be adjusted through configuration; shorten them for jurisdictions with
stricter privacy requirements.

## PII masking and redaction

1. Always call `utils.pii.mask_pii` on any event payload before logging or forwarding to
   human reviewers.
2. Enable strict compliance mode (`COMPLIANCE_MODE=strict`) to force redaction in outbound
   communications and expand numeric masking.
3. Extend the `PII_FIELD_WHITELIST` only after documenting the business justification in an
   architecture decision record or ticket.

## Audit logging

* Every workflow run is tagged with a `run_id` that propagates through structured logs,
  OpenTelemetry spans, CRM payloads, and alert notifications.
* The `logs` package persists JSON lines files with the masked payload, agent decisions, and
  timestamps. Do not edit these files manually—rely on the provided log managers.
* Export telemetry to your observability stack (Grafana, Datadog, Honeycomb) to obtain
  immutable timelines for investigations.

## Access controls

* Limit credentials loaded through `config.Settings` to service accounts with read-only
  calendar access and scoped CRM permissions.
* Store `.env` files and secrets in your secret manager or CI variables instead of committing
  them to the repository.
* When running in shared infrastructure, ensure filesystem permissions restrict `log_storage`
  to the orchestrator user.

## Change management

* New prompts or templates must include metadata describing authorship, change reason, and
  rollout plan. See [`templates/README.md`](../templates/README.md) for the prompt lifecycle.
* Feature branches that affect compliance or data handling should link to a risk assessment or
  legal review ticket in the pull request description.
* When introducing new agents, update [`docs/architecture.md`](architecture.md) to explain the
  data flow and specify the controls applied at each stage.
* During the release process, add the note "ZIP-Snapshot ohne .git/ – Herkunft/Historie extern
  prüfen." whenever publishing artefacts created from a repository snapshot to make missing Git
  history explicit for audit reviewers.

## Incident response

* Configure the Alerting agent to escalate compliance failures (e.g. masking errors,
  unexpected PII exposure) via PagerDuty or Slack.
* Use the stored `run_id` to correlate filesystem logs with telemetry when triaging incidents.
* After remediation, document the root cause and mitigation steps in the incident knowledge
  base before closing the alert.
