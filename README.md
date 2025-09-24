# Google Calendar Event Processing System

This repository contains an intelligent system for processing Google Calendar events with automated triggers, logging, and email notifications.

## Block 1 Implementation - Core Infrastructure

This initial implementation provides the foundational components for the Google Calendar event processing system:

### Components

#### 1. Email Agent (`email_agent.py`)
Central SMTP email sending functionality that handles all system email types:
- **Human-in-the-loop requests** for company/domain validation
- **Reminder emails** to event organizers
- **Escalation emails** to administrators
- **Error notifications** for system issues

**Features:**
- Template-based email system with Jinja2 rendering
- Email address validation
- Support for CC/BCC recipients
- Configurable SMTP settings via environment variables
- Automatic retry and error handling

#### 2. Event Log Manager (`event_log_manager.py`)
S3-based event logging system that tracks individual calendar events:
- **Duplicate detection** via event ID lookup
- **Processing history** with timestamps and actions
- **Email history** tracking all sent emails
- **Error history** for debugging failed events
- **Status tracking** (CREATED, PROCESSING, COMPLETED, ERROR)

**Features:**
- S3 storage with encryption (AES256)
- JSON format for easy querying
- Automatic event ID sanitization
- Configurable retention and deletion
- Comprehensive event metadata tracking

#### 3. Workflow Log Manager (`workflow_log_manager.py`)
S3-based workflow logging for tracking entire processing runs:
- **Run-level tracking** with unique run IDs
- **Step-by-step logging** of workflow execution
- **Error tracking** with full tracebacks
- **Performance metrics** and timing data
- **Event processing summary**

**Features:**
- Hierarchical logging (run → steps → events)
- Performance monitoring and metrics
- Error aggregation and reporting
- Configurable log retention
- Console fallback when S3 unavailable

#### 4. Email Templates (`email_templates.md`)
Centralized, editable email templates using Jinja2 syntax:
- **HUMAN_IN_LOOP_REQUEST** - Company validation requests
- **REMINDER_TO_ORGANIZER** - Event follow-up reminders
- **ESCALATION_TO_ADMIN** - Administrator escalations
- **ERROR_NOTIFICATION** - System error alerts

**Features:**
- Variable substitution with Jinja2
- Immediate template reloading
- Comprehensive template documentation
- Fallback templates for reliability

#### 5. Configuration (`config.py`)
Centralized configuration management:
- **Environment variable support**
- **Configuration validation**
- **Masked sensitive values**
- **Default value handling**

## Installation

1. Clone the repository:
```bash
git clone https://github.com/KonstantinData/Agentic-Intelligence-Research.git
cd Agentic-Intelligence-Research
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
# Required settings
export S3_BUCKET_NAME="your-s3-bucket"
export ADMIN_EMAIL="admin@example.com"

# SMTP settings for email sending
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export FROM_EMAIL="your-email@gmail.com"

# AWS credentials
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

## Usage

### Basic Usage

```python
from email_agent import email_agent
from event_log_manager import event_log_manager
from workflow_log_manager import workflow_log_manager

# Create a workflow run
run_id = workflow_log_manager.create_workflow_log(
    workflow_type='CALENDAR_PROCESSING'
)

# Process an event
event_data = {
    'id': 'cal_event_123',
    'summary': 'Meeting with ACME Corp',
    'description': 'Discuss contract renewal',
    'dateTime': '2024-01-15T10:00:00Z'
}

# Check for duplicates
if not event_log_manager.event_exists(event_data['id']):
    # Create event log
    event_log_manager.create_event_log(
        event_id=event_data['id'],
        event_data=event_data
    )
    
    # Send human-in-loop request
    success = email_agent.send_human_in_loop_request(
        event_data=event_data,
        company_name='ACME Corp',
        web_domain='acme.com'
    )
    
    # Log the email action
    event_log_manager.add_email_record(
        event_id=event_data['id'],
        email_type='HUMAN_IN_LOOP_REQUEST',
        recipient=email_agent.admin_email,
        success=success
    )

# Complete the workflow
workflow_log_manager.complete_workflow(
    run_id=run_id,
    status='COMPLETED',
    final_summary={'events_processed': 1}
)
```

### Configuration Validation

```python
from config import validate_config

validation = validate_config()
if not validation['valid']:
    print("Configuration errors:")
    for error in validation['errors']:
        print(f"  - {error}")
```

## Error Handling

The system implements comprehensive error handling at multiple levels:

1. **Email Agent Errors**: Failed email sends are logged and returned as boolean status
2. **S3 Connection Errors**: Automatic fallback to console logging when S3 unavailable
3. **Workflow Errors**: Full exception tracking with tracebacks in workflow logs
4. **Event Processing Errors**: Individual event errors recorded in event logs

All errors are automatically logged to the appropriate log system and can trigger admin notifications.

## Storage Structure

### S3 Bucket Layout
```
your-s3-bucket/
├── events/
│   ├── cal_event_123.json
│   ├── cal_event_456.json
│   └── ...
└── workflow_log/
    ├── 20240115_120000_abc123.json
    ├── 20240115_130000_def456.json
    └── ...
```

### Event Log Structure
```json
{
  "event_id": "cal_event_123",
  "created_timestamp": "2024-01-15T12:00:00Z",
  "status": "PROCESSING",
  "event_data": {...},
  "processing_history": [...],
  "email_history": [...],
  "error_history": [...]
}
```

### Workflow Log Structure
```json
{
  "run_id": "20240115_120000_abc123",
  "workflow_type": "CALENDAR_PROCESSING",
  "start_timestamp": "2024-01-15T12:00:00Z",
  "status": "RUNNING",
  "steps": [...],
  "errors": [...],
  "performance_metrics": {...}
}
```

## Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `S3_BUCKET_NAME` | Yes | S3 bucket for logs | - |
| `ADMIN_EMAIL` | Yes | Administrator email | - |
| `SMTP_SERVER` | No | SMTP server hostname | localhost |
| `SMTP_PORT` | No | SMTP server port | 587 |
| `SMTP_USERNAME` | No | SMTP username | - |
| `SMTP_PASSWORD` | No | SMTP password | - |
| `FROM_EMAIL` | No | From email address | SMTP_USERNAME |
| `AWS_ACCESS_KEY_ID` | No | AWS access key | - |
| `AWS_SECRET_ACCESS_KEY` | No | AWS secret key | - |
| `AWS_REGION` | No | AWS region | us-east-1 |

## Next Steps (Future PRs)

The following components will be implemented in subsequent pull requests:

1. **Google Calendar Polling** - Fetch events from Google Calendar API
2. **Trigger System** - Hard/soft trigger detection and processing  
3. **Company/Domain Extraction** - NLP-based extraction from event text
4. **Reminder/Escalation Workflows** - Automated scheduling and sending
5. **Web Interface** - Dashboard for monitoring and management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.