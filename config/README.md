# Configuration

The configuration package exposes a single `Settings` object that loads environment
variables (optionally from a `.env` file via `python-dotenv`). The settings inform how the
workflow connects to Google services, local PostgreSQL storage, and how far ahead/behind
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
| `POSTGRES_DSN` | Connection string for the local PostgreSQL instance (alias `DATABASE_URL`). | _optional_ |
| `POSTGRES_EVENT_LOG_TABLE` | Table for event log entries. | `event_logs` |
| `POSTGRES_WORKFLOW_LOG_TABLE` | Table for workflow-level log entries. | `workflow_logs` |
| `POSTGRES_FILE_LOG_TABLE` | Table for persisted workflow artefacts such as log files. | `workflow_log_files` |

Legacy AWS variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `S3_BUCKET_NAME`) are still parsed for backwards compatibility but no longer used by the runtime now that log persistence is handled by PostgreSQL.

Set `SETTINGS_SKIP_DOTENV=1` to bypass `.env` loading (useful for automated tests that inject configuration via environment variables).

If `TRIGGER_WORDS` is not defined, the system falls back to the newline-separated list in
[`trigger_words.txt`](trigger_words.txt). Empty lines and comments (lines starting with `#`)
inside the file are ignored.

## Usage

```python
from config.config import settings

lookahead = settings.cal_lookahead_days
dsn = settings.postgres_dsn
```

The `settings` object is instantiated once and reused across the codebase for consistent
configuration access.

