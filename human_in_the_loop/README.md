# Human-in-the-loop (HITL)

Manual decision steps ensure that sensitive automations always receive explicit approval
before proceeding.  This package contains scaffolding for implementing those interactions.

## Components

| File | Description |
|------|-------------|
| [`hitl_module.py`](hitl_module.py) | Example class illustrating how to request human approval or collect missing information before advancing a workflow. |

The higher-level [`agents/human_in_loop_agent.py`](../agents/human_in_loop_agent.py) wraps
these concepts with additional orchestration logic and pluggable communication backends.

## Implementation tips

* Integrate with messaging platforms (email, Slack, ticketing systems) by injecting
  backend clients that expose clear confirmation methods.
* Record human responses in the logging layer for auditability.
* Keep HITL flows deterministic in tests by providing mocked backends or simulated
  responses.
