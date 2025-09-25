# Configuration

The configuration package exposes a single `Settings` object that loads environment
variables (optionally from a `.env` file via `python-dotenv`).  The settings inform how the
workflow connects to Google services, AWS S3, and how far ahead/behind to poll events.

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
| `AWS_ACCESS_KEY_ID` | Access key used when uploading logs to S3. | _optional_ |
| `AWS_SECRET_ACCESS_KEY` | Secret key used when uploading logs to S3. | _optional_ |
| `AWS_DEFAULT_REGION` | AWS region where the target S3 bucket lives. | _optional_ |
| `S3_BUCKET_NAME` | Destination bucket for log uploads (alias `S3_BUCKET` is also supported). | _optional_ |

If `TRIGGER_WORDS` is not defined, the system falls back to the newline-separated list in
[`trigger_words.txt`](trigger_words.txt).  Empty lines and comments (lines starting with `#`)
inside the file are ignored.

## Usage

```python
from config.config import settings

lookahead = settings.cal_lookahead_days
bucket = settings.s3_bucket
```

The `settings` object is instantiated once and reused across the codebase for consistent
configuration access.
