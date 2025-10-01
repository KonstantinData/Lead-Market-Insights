# Workflow lifecycle

This document describes how the asynchronous workflow orchestrator boots, coordinates
agents, and shuts down cleanly. It complements the high-level component view in
[`docs/architecture.md`](architecture.md) with a focus on runtime sequencing.

## Overview

* `WorkflowOrchestrator` is the long-lived entrypoint. It prepares observability,
  constructs the `MasterWorkflowAgent`, and installs cooperative shutdown hooks.
* Every concrete agent implements an asynchronous interface. The orchestrator awaits
  their coroutines directly—no synchronous bridge utilities are used in the new model.
* Background tasks (for example, reminder schedulers or I/O writers) are registered
  with the orchestrator so they can be cancelled when the process terminates.

## Startup sequence

1. **Environment bootstrap** – Configuration is loaded via `config.settings`, logging
   is initialised, and OpenTelemetry exporters are wired up through
   `utils.observability.configure_observability()`.
2. **Agent construction** – `WorkflowOrchestrator` creates (or accepts) a
   `MasterWorkflowAgent` instance. If an agent exposes an `aclose()` coroutine it is
   registered for later cleanup.
3. **Signal handlers** – `install_signal_handlers()` attaches SIGTERM/SIGINT listeners
   that trigger an asynchronous shutdown task. This is safe to call only once the
   orchestrator is running inside an event loop.
4. **Event loop integration** – Consumers typically start the orchestrator with
   `python -m agents.workflow_orchestrator`, but it can also be awaited from an
   existing asyncio application by instantiating the class directly and awaiting
   `run()`.

## Event processing lifecycle

1. **Polling** – Calendar and contact polling coroutines retrieve candidate events.
2. **Task fan-out** – For each event the orchestrator schedules asynchronous work that
   covers extraction, research, human escalations, and CRM delivery. Concurrency is
   bounded by the agents themselves; no synchronous wrappers are introduced.
3. **Telemetry** – Each run emits observability metadata (run IDs, duration, failure
   counts) before writing workflow summaries to
   `log_storage/run_history/workflows/<run_id>/`.

## Background tasks and cooperative cancellation

* `track_background_task()` records any awaited task so the orchestrator can cancel it
  later. Tasks remove themselves from the tracking set when they complete.
* `register_async_cleanup()` and `register_sync_cleanup()` store callbacks that flush
  buffers, persist artefacts, or release resources during shutdown.
* The orchestrator protects the shutdown sequence with an asyncio lock/event pair so
  concurrent callers (for example, multiple signals) resolve deterministically.

## Graceful shutdown

1. **Trigger** – Shutdown can be initiated via signals, explicit calls to
   `shutdown()`, or context managers in embedding applications.
2. **Cancellation** – Background tasks are cancelled with an optional timeout (default
   five seconds). Awaitables are given a chance to handle `asyncio.CancelledError`
   before being awaited again.
3. **Cleanup** – Registered async and sync cleanup hooks run in order. Agent-level
   `aclose()` hooks release network resources and flush any outstanding uploads.
4. **Finalisation** – Run manifests are logged, telemetry exporters are flushed via
   `utils.observability.flush_telemetry()`, and the orchestrator marks the shutdown as
   complete so subsequent calls are idempotent.

## Integration guidance

* **Embed in existing loops** – When integrating into a larger asyncio application,
  prefer `await orchestrator.run()` and reuse the hosting loop. Avoid calling
  `asyncio.run()` inside agent implementations.
* **Testing** – Unit tests should rely on `pytest`'s asyncio support or equivalent
  fixtures to exercise agent coroutines directly.
* **Extending agents** – New agents must subclass the async base interfaces in
  `agents/interfaces/base.py` and return coroutines for their public methods. This
  ensures consistent cooperative cancellation semantics across the platform.

By following this lifecycle, deployments benefit from predictable startup timing,
responsive cancellation, and observability-aligned shutdown behaviour.
