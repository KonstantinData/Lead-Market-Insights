
# Agentic-Intelligence-Research

This repository contains workflows and components for agent-based process automation (e.g., around Google Calendar, event handling, logging, communication).

## Prerequisites

- **Python**: Install [Python 3.8+](https://www.python.org/downloads/) for your system (e.g., Windows).
- **Virtual environment** (recommended):
  ```batch
  python -m venv .venv
  .venv\Scripts\activate
  ```
- **Install dependencies**:
  After activating the environment:
  ```batch
  pip install -r requirements.txt
  ```

## Structure

- `agents/`: Central agents (e.g., email agent)
- `logs/`: Logging modules for events, workflows, etc.
- `templates/`: Central templates for emails and other communication
- `polling/`, `extraction/`, `human_in_the_loop/`, `reminders/`: Placeholders for planned extensions
- `tests/`: Unit tests and test scripts

## Notes

- The AWS integration (boto3/botocore) requires valid AWS credentials if logging to S3 is used.
- For secure handling of environment variables, `python-dotenv` is recommended. Create a `.env` file and set your configuration values there (e.g., for mail server, AWS, etc.).

## Configuring S3 logging

1. Ensure your `.env` file (or environment configuration) defines the AWS credentials and bucket details required for logging:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_DEFAULT_REGION`
   - `S3_BUCKET_NAME`
2. Ensure the environment variables are available when running the project (either through the `.env` file or your CI configuration).
3. Use the helper in `logs` to obtain a ready-to-use manager:

   ```python
   from logs import get_event_log_manager

   event_log_manager = get_event_log_manager()
   event_log_manager.write_event_log("event-id", {"status": "started"})
   ```

The helper automatically loads environment variables via `python-dotenv` and raises an error if `S3_BUCKET_NAME` is missing.

Further documentation will follow as the functionality grows.
