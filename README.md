
# Agentic-Intelligence-Research

This repository implements an agent-based workflow system for Google Calendar event processing, trigger detection, information extraction, and human-in-the-loop validation.

## Quick Start

**Entry Point**: Run the main workflow using:
```bash
python main.py
```

This starts the `MasterWorkflowAgent` which orchestrates all sub-agents and handles the complete event processing pipeline.

## Architecture Overview

The system is built around a central `MasterWorkflowAgent` that coordinates specialized sub-agents:

```
main.py
    └── MasterWorkflowAgent
            ├── EventPollingAgent      (Google Calendar polling)
            ├── TriggerDetectionAgent  (Hard/soft trigger matching)
            ├── ExtractionAgent       (Company name & domain extraction)
            ├── HumanInLoopAgent      (Manual validation/completion)
            └── S3StorageAgent        (Log upload to AWS S3)
```

### Workflow Process

1. **Event Polling**: Fetch events from Google Calendar within configured date range
2. **Trigger Detection**: Check event summaries/descriptions against trigger word lists
3. **Information Extraction**: Extract required fields (company_name, web_domain)
4. **Human Validation**: Request manual input for incomplete information
5. **Logging & Storage**: Log all actions and optionally upload to S3

## Prerequisites

- **Python**: Install [Python 3.8+](https://www.python.org/downloads/)
- **Virtual environment** (recommended):
  ```bash
  python -m venv .venv
  source .venv/bin/activate  # On Windows: .venv\Scripts\activate
  ```
- **Install dependencies**:
  ```bash
  pip install -r requirements.txt
  ```

## Project Structure

- `main.py`: **Primary entry point** - initializes and runs MasterWorkflowAgent
- `agents/`: Core agent implementations
  - `master_workflow_agent.py`: Central orchestrator
  - `event_polling_agent.py`: Google Calendar integration
  - `trigger_detection_agent.py`: Trigger word matching logic
  - `extraction_agent.py`: Information extraction from events
  - `human_in_loop_agent.py`: Interactive user input handling
  - `s3_storage_agent.py`: AWS S3 upload functionality
- `config/`: Configuration management and environment variables
- `utils/`: Utility modules (trigger loading, text processing, etc.)
- `logs/`: Logging infrastructure for events and workflows
- `templates/`: Email and communication templates
- `integration/`: External service integrations (Google Calendar, etc.)
- `tests/`: Unit tests and test scripts
- `ARCHIVE/`: Deprecated/legacy code (not used in current system)

## Configuration

### Environment Variables

Create a `.env` file in the root directory to configure the system:

```env
# Google Calendar API Configuration
# (Set up through Google Cloud Console)

# Trigger Words (optional - can also use config/trigger_words.txt)
TRIGGER_WORDS="meeting,call,interview"

# Calendar Date Ranges
CAL_LOOKAHEAD_DAYS=14
CAL_LOOKBACK_DAYS=1

# AWS S3 Configuration (optional - for log uploads)
AWS_ACCESS_KEY_ID=your_key_id
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=your-bucket-name
```

### Google Calendar Setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google Calendar API
3. Create credentials (OAuth 2.0 or service account)
4. Follow Google's authentication documentation for setup

## Developer Guide

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_specific_module.py -v
```

**Note**: Some legacy tests may reference archived components and need updating.

### Code Quality & Linting

```bash
# Format code with Black
black .

# Check with flake8
flake8 .

# Type checking with mypy
mypy .
```

### Extending the System

The architecture supports easy extension:

1. **New Sub-Agents**: Create new agents in `agents/` following existing patterns
2. **Integration Points**: Add new integrations in `integration/`
3. **Custom Triggers**: Modify trigger detection logic in `TriggerDetectionAgent`
4. **Workflow Steps**: Extend `MasterWorkflowAgent.run_workflow()` for new processing steps

### Architecture Notes

- **Single Entry Point**: All processing flows through `main.py` → `MasterWorkflowAgent`
- **Agent Orchestration**: MasterWorkflowAgent coordinates all sub-agents
- **Error Handling**: Each agent handles its own errors with proper logging
- **Extensible Design**: New agents can be easily added to the workflow

## Legacy & Archive

The `ARCHIVE/` directory contains the previous polling and trigger system that has been superseded by the current agent-based architecture. This includes:

- `ARCHIVE/polling_trigger.py`: Previous standalone polling script
- `ARCHIVE/Readme.md`: Documentation for archived components

**Important**: Do not import or use code from `ARCHIVE/` in the current system.

---

For more detailed information about specific components, refer to the inline documentation in each module.
