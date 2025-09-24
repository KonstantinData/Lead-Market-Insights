
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

Further documentation will follow as the functionality grows.
