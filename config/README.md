# Configuration

The configuration package exposes a single `Settings` object that loads environment
variables (optionally from a `.env` file via `python-dotenv`). The settings inform how the
workflow connects to Google services, where local log artefacts are stored, and how far ahead/behind
to poll events.

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CAL_LOOKAHEAD_DAYS` | Number of days into the future to request events from Google Calendar. | `14` |
| `CAL_LOOKBACK_DAYS` | Number of days in the past to include when polling events. | `1` |
| `GOOGLE_CLIENT_ID` | OAuth client ID for the Google Workspace project. | _required_ |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret paired with the client ID. | _required_ |
| `GOOGLE_REFRESH_TOKEN` | Refresh token used to obtain short-lived access tokens. | _required_ |
| `GOOGLE_TOKEN_URI` | Token endpoint URL; defaults to Google's standard OAuth token URI when not provided. | _optional_ |
| `GOOGLE_CALENDAR_ID` | Calendar identifier to poll (e.g., `primary` or an email address). | `info@condata.io` |
| `TRIGGER_WORDS` | Comma-separated list of trigger words that override the default list and the contents of `trigger_words.txt`. | _optional_ |
| `LOG_STORAGE_DIR` | Root directory for storing workflow run artefacts. | `<repo>/log_storage/run_history` |
| `EVENT_LOG_DIR` | Override for event log storage (defaults to a subdirectory of `LOG_STORAGE_DIR`). | `<LOG_STORAGE_DIR>/events` |
| `WORKFLOW_LOG_DIR` | Override for workflow log storage. | `<LOG_STORAGE_DIR>/workflows` |
| `RUN_LOG_DIR` | Override for per-run log files. | `<LOG_STORAGE_DIR>/runs` |

Set `SETTINGS_SKIP_DOTENV=1` to bypass `.env` loading (useful for automated tests that inject configuration via environment variables).

If `TRIGGER_WORDS` is not defined, the system falls back to the newline-separated list in
[`trigger_words.txt`](trigger_words.txt). Empty lines and comments (lines starting with `#`)
inside the file are ignored.

## Usage

```python
from config.config import settings

lookahead = settings.cal_lookahead_days
log_dir = settings.log_storage_dir
```

The `settings` object is instantiated once and reused across the codebase for consistent
configuration access.
