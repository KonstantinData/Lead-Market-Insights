# Reminders and escalations

Reminder workflows ensure that important follow-ups never slip through the cracks.  This
package implements reusable logic for nudging organisers and escalating issues.

## Components

| File | Description |
|------|-------------|
| [`reminder_escalation.py`](reminder_escalation.py) | Wraps the email agent to send reminder and escalation messages, optionally logging failures via the workflow log manager. |

Future enhancements can introduce SMS, chat, or task management integrations while keeping
escalation routing centralised in this package.
