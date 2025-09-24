# Agentic Intelligence Research System

A comprehensive research automation system with email communication, event logging, and workflow management capabilities.

## Block 1 Implementation

This repository contains the foundational Block 1 implementation with four core components:

### Components

#### 1. Email Agent (`email_agent.py`)
SMTP-based email system for research requests, reminders, and escalations.

**Features:**
- Multiple email types (initial request, reminders, escalations, thank you)
- Template-based email generation with placeholder substitution
- Comprehensive error handling and logging
- SMTP connection management with TLS/SSL support
- Integration with workflow logging system

**Usage:**
```python
from email_agent import EmailAgent, EmailConfig, EmailRecipient, EmailContext

# Configure SMTP
config = EmailConfig(
    smtp_server="smtp.gmail.com",
    smtp_port=587,
    username="your_email@gmail.com",
    password="your_app_password"
)

agent = EmailAgent(config)

# Send initial request
recipient = EmailRecipient(name="Dr. Expert", email="expert@university.edu")
context = EmailContext(
    request_id="REQ-001",
    event_id="EVT-001",
    recipient=recipient,
    request_details="Research request details",
    deadline="2024-12-31"
)

success = agent.send_initial_request(context)
```

#### 2. Event Log Manager (`event_log_manager.py`)
S3-based event logging with status tracking and duplicate prevention.

**Features:**
- Event logging to S3 with JSON format
- Status tracking (pending, in_progress, completed, failed, etc.)
- Email status monitoring (sent, delivered, replied, bounced, etc.)
- Duplicate detection using hash-based checking
- Event retrieval and querying capabilities
- Automatic cleanup of old events

**Usage:**
```python
from event_log_manager import EventLogManager, S3Config, EventData

# Configure S3
config = S3Config(
    bucket_name="your-logs-bucket",
    region="us-east-1"
)

manager = EventLogManager(config)

# Log event
event_data = EventData(
    event_id="EVT-001",
    request_id="REQ-001",
    status=EventStatus.PENDING,
    trigger=TriggerType.MANUAL,
    timestamp=datetime.utcnow().isoformat() + "Z",
    email_status=EmailStatus.NOT_SENT
)

success = manager.log_event(event_data)
```

#### 3. Workflow Log Manager (`workflow_log_manager.py`)
Comprehensive workflow execution tracking with detailed step logging.

**Features:**
- Complete workflow run tracking
- Individual step logging with timing and status
- Error handling with full tracebacks
- Event and error counting
- Workflow summaries and statistics
- Integration with other components for unified logging

**Usage:**
```python
from workflow_log_manager import WorkflowLogManager, S3WorkflowConfig

# Configure S3
config = S3WorkflowConfig(
    bucket_name="your-logs-bucket",
    region="us-east-1"
)

logger = WorkflowLogManager(config)

# Start workflow
run = logger.start_workflow_run(
    run_id="RUN-001",
    workflow_name="research_workflow",
    triggered_by="user"
)

# Log steps
logger.log_step_start(run_id, "step1", "Send Email")
logger.log_step_completion(run_id, "step1", StepStatus.COMPLETED)

# Finish workflow
logger.finish_workflow_run(run_id)
```

#### 4. Email Templates (`email_templates.md`)
Centralized, editable email templates with placeholder support.

**Features:**
- Multiple template types for different communication stages
- Placeholder-based customization
- Markdown format for easy editing
- Support for escalation levels and priorities
- Professional, consistent messaging

**Placeholders available:**
- `{name}`, `{company}`, `{email}` - Recipient information
- `{request_id}`, `{event_id}` - Tracking identifiers
- `{request_details}`, `{deadline}` - Request specifics
- `{escalation_level}`, `{days_overdue}` - Escalation context
- And many more...

## Configuration

### Environment Variables

Set these environment variables for production use:

#### SMTP Configuration
```bash
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USERNAME="your_email@gmail.com"
export SMTP_PASSWORD="your_app_password"
export SMTP_FROM_EMAIL="research@yourcompany.com"
export SMTP_FROM_NAME="Research Team"
export SMTP_USE_TLS="true"
```

#### AWS S3 Configuration
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_REGION="us-east-1"
export S3_BUCKET_NAME="your-research-logs"
export S3_EVENTS_PREFIX="events/"
export S3_WORKFLOW_LOGS_PREFIX="workflow_logs/"
export S3_USE_ENCRYPTION="true"
```

## Installation and Setup

1. **Clone the repository:**
```bash
git clone https://github.com/KonstantinData/Agentic-Intelligence-Research.git
cd Agentic-Intelligence-Research
```

2. **Install dependencies:**
```bash
pip install boto3 python-dotenv
```

3. **Configure environment variables** (see Configuration section above)

4. **Test the implementation:**
```bash
python test_implementation.py
```

5. **Run example usage:**
```bash
python example_usage.py
```

## Testing

The implementation includes comprehensive tests:

- `test_implementation.py` - Core functionality tests
- `example_usage.py` - Complete workflow demonstration

Run tests:
```bash
python test_implementation.py
```

All tests should pass. The system gracefully handles missing AWS credentials and SMTP configuration for testing purposes.

## Architecture

### Component Integration
```
┌─────────────────┐    ┌───────────────────┐    ┌─────────────────┐
│   Email Agent   │    │ Event Log Manager│    │Workflow Logger  │
│                 │    │                   │    │                 │
│ - Send emails   │    │ - Log events      │    │ - Track runs    │
│ - Use templates │    │ - Status tracking │    │ - Log steps     │
│ - Error handling│    │ - Duplicate check │    │ - Error capture │
└─────────────────┘    └───────────────────┘    └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                    ┌─────────────────────────┐
                    │     S3 Storage          │
                    │                         │
                    │ - events/{id}.json      │
                    │ - workflow_logs/{id}.json│
                    └─────────────────────────┘
```

### Data Flow
1. **Workflow Start** → Workflow Logger creates run record
2. **Event Creation** → Event Manager logs event to S3
3. **Email Sending** → Email Agent sends email, logs result
4. **Status Updates** → Components update their respective logs
5. **Workflow End** → Workflow Logger finalizes run with summary

## Error Handling

All components include comprehensive error handling:

- **Email Agent**: SMTP connection failures, authentication errors, template errors
- **Event Manager**: S3 connectivity issues, duplicate detection, data validation
- **Workflow Logger**: S3 storage failures, serialization errors, step tracking
- **Templates**: Missing placeholders, file access issues, parsing errors

Errors are logged at multiple levels:
- Component-specific logging
- Workflow-level event logging
- Console output for debugging

## Future Enhancements (Placeholders for Block 2+)

The current implementation provides placeholders and hooks for:

1. **Polling Logic** - Monitor email responses and trigger actions
2. **Data Extraction** - Parse and analyze email responses
3. **Human-in-the-Loop** - Manual review and intervention workflows
4. **Advanced Reminder/Escalation** - Time-based triggers and smart escalation
5. **Response Analysis** - AI-powered content analysis and routing
6. **Integration APIs** - Webhooks and external system integration

## Contributing

This is a research project implementation. Key areas for contribution:

1. Enhanced error recovery and retry logic
2. Performance optimizations for large-scale operations
3. Additional email template types and customizations
4. Advanced analytics and reporting features
5. Integration with external systems and APIs

## License

This project is part of the Agentic Intelligence Research initiative.