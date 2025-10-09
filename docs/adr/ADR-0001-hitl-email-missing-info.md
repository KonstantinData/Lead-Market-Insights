
# ADR-0001 — Human-in-the-Loop (HITL) IMAP/SMTP Integration

## Status

✅ **Accepted** — Implemented starting from branch `feat/hitl-imap-reintegration`.

## Context

The workflow system automates event-driven research processes based on triggers from sources such as Google Calendar or CRM updates.
However, some events may be incomplete, ambiguous, or require human confirmation.
To address these cases, a **Human-in-the-Loop (HITL)** mechanism is introduced.

The HITL system must:

- Request human clarification or approval when data confidence is below a threshold.
- Allow operators to reply directly via email.
- Automatically parse and process these responses.
- Be fully auditable and compatible with future channels (e.g. Slack, Web UI).

## Decision

The chosen communication layer for HITL is **email**, for simplicity, auditability, and reliability in production.

### Components

1. **SMTP Sending**

   - Outgoing HITL request emails are sent through `utils/email_agent.py`.
   - Templates located at `templates/hitl_request_email.txt`.
   - Configurable via environment variables:
     ```
     SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SECURE, MAIL_FROM
     ```
2. **IMAP Polling**

   - Implemented in `polling/inbox_agent.py` and `agents/inbox_poller.py`.
   - The system checks for replies every *n* seconds (`HITL_INBOX_POLL_SECONDS`, default 15).
   - It supports SSL and folder selection (e.g., `INBOX`, `Processed`, `Errors`).
3. **Parsing**

   - Replies are parsed through `human_in_the_loop/reply_parsers.py`.
   - The parser extracts approval or rejection decisions from plain text emails.
   - A “confirmation token” links responses to the correct workflow run.
4. **Agent Coordination**

   - `human_in_loop_agent.py` handles the dispatch, persistence, and routing logic.
   - `master_workflow_agent.py` pauses execution until a HITL decision or timeout occurs.
   - Timeout rules and escalation emails are managed via environment variables:
     ```
     HITL_FIRST_DEADLINE, HITL_REMINDER_TIME, HITL_SECOND_DEADLINE, HITL_ADMIN_EMAIL
     ```
5. **Persistence and Logging**

   - Every HITL request and response is logged under:
     ```
     log_storage/run_history/research/artifacts/hitl/
     ```
   - Each run has a JSONL trail documenting decision flow, timestamps, and outcomes.

## Alternatives Considered

| Option               | Description              | Reason for Rejection                                       |
| -------------------- | ------------------------ | ---------------------------------------------------------- |
| Web Portal           | Dedicated HITL dashboard | Too costly and complex for initial deployment              |
| Slack/Teams Bot      | Real-time chat HITL      | Requires additional OAuth scopes and dependency management |
| Auto-resolve via LLM | Fully automated          | Not reliable enough for sensitive CRM workflows            |

## Consequences

**Pros**

- No external dependencies beyond SMTP/IMAP.
- Easy integration for any operator with email access.
- Maintains compliance and traceability.

**Cons**

- Polling-based (not event-driven).
- Dependent on stable email credentials.

## Future Extensions

- Replace IMAP polling with a webhook-based push mechanism.
- Introduce a lightweight Web UI for operator confirmations.
- Integrate SLA monitoring and analytics dashboards.
