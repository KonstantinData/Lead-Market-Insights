# Integrations

This package encapsulates communication with external services.  The current focus is on
Google Workspace APIs used for polling calendar events and related contacts.

## Modules

| File | Purpose |
|------|---------|
| [`google_calendar_integration.py`](google_calendar_integration.py) | Handles OAuth credential loading, access-token refresh, and REST calls to the Google Calendar API. Provides `list_events` for polling events within configurable windows. |
| [`google_contacts_integration.py`](google_contacts_integration.py) | Provides a read-only wrapper around the Google People API to fetch organiser contact details using an existing access token. |

Both integrations rely on the configuration documented in [`config/README.md`](../config/README.md).

## Extending integrations

* Add new integration modules to this package (e.g., CRM connectors) and expose a
  consistent class-based API.
* Avoid making API calls directly from business logic—route them through integration
  classes so credentials, retries, and error handling stay centralised.
