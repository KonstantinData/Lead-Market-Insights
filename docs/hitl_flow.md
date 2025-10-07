# Human-in-the-Loop Flow

The HITL workflow coordinates persistence, notification, telemetry, and inbox
processing so every request remains pending until an operator explicitly
responds.

## Sequence Overview

```mermaid
sequenceDiagram
    autonumber
    participant Master as MasterWorkflowAgent
    participant Human as HumanInLoopAgent
    participant Email as EmailAgent (SMTP)
    participant Operator as Operator Inbox
    participant Orchestrator as WorkflowOrchestrator

    Master->>Human: persist_pending_request(run_id, context)
    note over Human: Write {run_id}_hitl.json with status "pending"
    Master->>Human: dispatch_request_email(...)
    Human->>Email: send_email(operator_email, template)
    Email-->>Operator: HITL request email
    Master->>Human: schedule_reminders(...)
    Human->>Human: reminder_escalation.schedule(...)
    Operator-->>Orchestrator: Reply via inbox (approve/decline/change)
    Orchestrator->>Human: apply_decision(run_id, decision, actor, extra)
    Orchestrator->>Master: on_hitl_decision(run_id, state)
    Master->>Master: Advance workflow branch based on status
```

## State Transitions & Telemetry

```mermaid
stateDiagram-v2
    [*] --> Pending: trigger_hitl()
    Pending --> Approved: inbox reply "APPROVE"
    Pending --> Declined: inbox reply "DECLINE"
    Pending --> ChangeRequested: inbox reply "CHANGE"
    Pending --> Pending: reminder/escalation cycle

    state Pending {
        [*] --> AwaitingReply
        AwaitingReply --> AwaitingReply: reminder_sent / telemetry hitl_request_sent
        AwaitingReply --> AwaitingReply: reminder_escalation / telemetry hitl_inbox_no_decision
        AwaitingReply --> Exit: hitl_inbox_unmatched (ignored)
    }

    state Approved {
        [*] --> Exit
    }

    state Declined {
        [*] --> Exit
    }

    state ChangeRequested {
        [*] --> Exit
    }
```

Telemetry events emitted during the flow:

- `hitl_request_sent` – persisted state + email dispatched.
- `hitl_inbox_unmatched` – inbox message without run identifier.
- `hitl_inbox_no_decision` – reply without actionable command.
- `hitl_decision_applied` – parsed decision written back to storage.
- `hitl_approved`, `hitl_change`, `hitl_declined` – workflow branches.
