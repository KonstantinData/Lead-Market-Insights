# Polling and trigger detection

The polling layer is responsible for collecting new input data on a schedule and deciding
which events should move forward in the automation pipeline.

## Responsibilities

* Define cron jobs, schedulers, or background workers that invoke the polling agents.
* Coordinate with [`agents/event_polling_agent.py`](../agents/event_polling_agent.py) to pull
data from Google Calendar and contacts.
* Feed retrieved events into the trigger detection logic described in
  [`agents/trigger_detection_agent.py`](../agents/trigger_detection_agent.py).

As the project evolves, this directory can house reusable scheduler configurations,
documentation, or helper scripts for running the polling infrastructure.
