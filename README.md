# Agentic Intelligence Research

A research project for building intelligent agents that process Google Calendar events through automated workflows.

## Block 1 Implementation - Initial Components

This initial implementation provides the foundational components for the agentic workflow system:

### Components

1. **Email Agent** (`email_agent.py`)
   - Central SMTP agent for sending request, reminder, and escalation emails
   - Template-based email system with customizable templates
   - Comprehensive error handling and logging integration
   - Support for various email types (requests, reminders, escalations, notifications)

2. **Event Log Manager** (`event_log_manager.py`)
   - S3-based event logging system for tracking calendar event processing
   - Duplicate detection to prevent processing the same event multiple times
   - Status tracking throughout the event lifecycle
   - Automatic cleanup of completed events after specified time period

3. **Workflow Log Manager** (`workflow_log_manager.py`)
   - S3-based workflow logging for comprehensive run tracking
   - Error collection from all components with full traceback capture
   - Statistics and analytics on workflow performance
   - Component-specific error tracking

4. **Email Templates** (`email_templates.md`)
   - Standardized, editable email templates with placeholder support
   - Templates for all workflow scenarios (requests, reminders, escalations, errors)
   - Easy customization and localization support

### Configuration

- **Configuration Template** (`config_template.py`) - Provides configuration structure and validation
- **Environment Variable Support** - Load configuration from environment variables
- **S3 and SMTP Configuration** - Configurable storage and email settings

### Usage

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the System**:
   - Copy `config_template.py` and customize with your S3 and SMTP settings
   - Or set environment variables (see `config_template.py` for variable names)

3. **Run Example**:
   ```bash
   python example_usage.py
   ```

### Example Usage

```python
from config_template import create_sample_config
from email_agent import EmailAgent
from event_log_manager import EventLogManager, EventStatus
from workflow_log_manager import WorkflowLogManager

# Load configuration
config = create_sample_config()

# Initialize components
workflow_logger = WorkflowLogManager.from_config(config)
email_agent = EmailAgent.from_config(config, workflow_logger)
event_log_manager = EventLogManager.from_config(config, workflow_logger)

# Start workflow
run_id = workflow_logger.start_workflow("calendar_event_processing")

# Process event
event_entry = event_log_manager.create_event_log("event_123", event_data)
email_agent.send_request_email("user@example.com", event_data, run_id)

# Complete workflow
workflow_logger.complete_workflow(success=True)
```

### Key Features

- **Robust Error Handling**: All exceptions are caught and logged to the workflow log
- **Duplicate Prevention**: Event IDs are checked to prevent duplicate processing
- **Template System**: Flexible email templates with variable substitution
- **S3 Storage**: Reliable cloud storage for logs with automatic cleanup
- **Modular Design**: Components can be used independently or together
- **Configuration Validation**: Built-in validation for all configuration parameters

### Future Enhancements (Placeholders Prepared)

- Google Calendar API integration for event polling and extraction
- Human-in-the-loop approval workflows
- Advanced reminder scheduling and escalation logic
- Web dashboard for monitoring and management
- Real-time triggers and webhooks
- Advanced analytics and reporting

### Dependencies

- `boto3` - AWS SDK for S3 operations
- `botocore` - Core AWS functionality
- Standard Python library modules for email, JSON, datetime, etc.

### Architecture

The system follows a modular architecture where:
- **Workflow Log Manager** serves as the central logging hub
- **Event Log Manager** tracks individual event processing
- **Email Agent** handles all communication
- All components report errors to the central workflow log
- Configuration is centralized and validated

This provides a solid foundation for building more complex agentic workflows while maintaining reliability and observability.