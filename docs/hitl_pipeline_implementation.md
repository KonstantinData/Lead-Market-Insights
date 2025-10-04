# HITL Pipeline Implementation Notes

The HITL workflow polls an IMAP inbox for organiser replies, dispatches them to
workflow handlers, and escalates outstanding items over email. All runtime
configuration is provided by `config.settings` and sourced from the environment.
The variables below describe the communication and policy levers that affect the
pipeline.

| Variable | Purpose | Default |
| --- | --- | --- |
| `SMTP_HOST` | SMTP relay used by `EmailAgent` for outbound notifications. | _unset_ |
| `SMTP_PORT` | Port for the SMTP relay. | `465` |
| `SMTP_USERNAME` | Username for SMTP authentication (`SMTP_USER` accepted as an alias). | _unset_ |
| `SMTP_PASSWORD` | Password for SMTP authentication (`SMTP_PASS` alias supported). | _unset_ |
| `SMTP_SENDER` | Sender address used in outbound email (falls back to `SMTP_FROM` or the SMTP username). | _unset_ |
| `SMTP_SECURE` | Enables implicit TLS when sending email. | `true` |
| `IMAP_HOST` | IMAP server hosting the HITL inbox. | _unset_ |
| `IMAP_PORT` | Port for the IMAP server. | `993` |
| `IMAP_USERNAME` | Username for IMAP authentication (`IMAP_USER` alias supported). | _unset_ |
| `IMAP_PASSWORD` | Password for IMAP authentication (`IMAP_PASS` alias supported). | _unset_ |
| `IMAP_MAILBOX` | Mailbox or folder name that should be polled (`IMAP_FOLDER` alias supported). | `INBOX` |
| `IMAP_USE_SSL` | Enables SSL/TLS for IMAP connections (`IMAP_SSL` alias supported). | `true` |
| `HITL_INBOX_POLL_SECONDS` | Polling cadence (seconds) for `InboxAgent`. | `60.0` |
| `HITL_TIMEZONE` | Timezone used when scheduling reminder notifications. | `Europe/Berlin` |
| `HITL_ADMIN_EMAIL` | Primary administrator contact for escalations. | _unset_ |
| `HITL_ESCALATION_EMAIL` | Distribution list for escalation notifications. | _unset_ |
| `HITL_ADMIN_REMINDER_HOURS` | Comma-separated schedule (in hours) for HITL admin reminders. | `24.0` |

When extending the pipeline ensure new components read from `config.settings`
instead of `os.getenv` so that tests and alternative configuration sources remain
consistent.
