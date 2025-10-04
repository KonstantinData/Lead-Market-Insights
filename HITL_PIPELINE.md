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
