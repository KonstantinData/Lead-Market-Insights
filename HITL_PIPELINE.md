# Human-in-the-Loop Pipeline Configuration

The human-in-the-loop (HITL) pipeline relies on a coordinated set of SMTP and
IMAP services in addition to scheduling policies for administrator follow-up.
The following environment variables are read via `config.settings` and provide
centralised configuration for these components.

| Variable | Description | Default |
| --- | --- | --- |
| `SMTP_HOST` | Hostname or IP address of the SMTP relay. | _unset_ |
| `SMTP_PORT` | TCP port used for SMTP connections. | `465` |
| `SMTP_USERNAME` | Username used to authenticate with the SMTP relay. Falls back to `SMTP_USER` for backwards compatibility. | _unset_ |
| `SMTP_PASSWORD` | Password used for SMTP authentication. Falls back to `SMTP_PASS`. | _unset_ |
| `SMTP_SENDER` | Email address that appears in the `From` header. Falls back to `SMTP_FROM` or the SMTP username. | _unset_ |
| `SMTP_SECURE` | Whether to require an implicit TLS connection when sending email (`1`/`0`, `true`/`false`). | `true` |
| `IMAP_HOST` | Hostname of the IMAP server that exposes the HITL inbox. | _unset_ |
| `IMAP_PORT` | TCP port for the IMAP server. | `993` |
| `IMAP_USERNAME` | Username for IMAP authentication. Falls back to `IMAP_USER`. | _unset_ |
| `IMAP_PASSWORD` | Password for IMAP authentication. Falls back to `IMAP_PASS`. | _unset_ |
| `IMAP_MAILBOX` | Name of the mailbox/folder to poll for replies (also accepts `IMAP_FOLDER`). | `INBOX` |
| `IMAP_USE_SSL` | Whether to use SSL/TLS when connecting to IMAP. Falls back to `IMAP_SSL`. | `true` |
| `HITL_INBOX_POLL_SECONDS` | Polling interval (in seconds) used by the inbox agent. | `60.0` |
| `HITL_TIMEZONE` | IANA timezone identifier for scheduling HITL reminders. | `Europe/Berlin` |
| `HITL_ADMIN_EMAIL` | Optional administrator address that receives HITL escalations. | _unset_ |
| `HITL_ESCALATION_EMAIL` | Optional distribution list for escalated requests. | _unset_ |
| `HITL_ADMIN_REMINDER_HOURS` | Comma-separated list of reminder delays (hours) for HITL administrators. | `24.0` |

> **Note:** All services consume these variables via `config.settings`. Production
code must avoid direct calls to `os.getenv` for the settings above.

## Automatic Continuations via InboxAgent

When a HITL follow-up is requested, the workflow orchestrator records the audit
context and registers `_handle_inbox_reply` with the inbox polling agent so that
future replies can be processed automatically. The handler normalises organiser
responses using the parser utilities (`parse_missing_info_key_values` and
`parse_dossier_decision`) and persists a masked audit-log entry before invoking
the corresponding continuation on `MasterWorkflowAgent`. Any active reminder or
escalation tasks owned by the human agent are cancelled at this point to avoid
duplicate nudges. The continuation merges the reply payload with the stored
event context, determines whether the research handoff is complete, and either
dispatches the CRM package or registers a new pending audit for additional
information. This flow ensures that a single organiser reply clears outstanding
reminders and drives the workflow forward without additional manual triage.
