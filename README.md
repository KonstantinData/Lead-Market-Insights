# Agentic Intelligence Research System

An intelligent agent system for managing Google Calendar events with automated email notifications, reminders, and escalation workflows.

## Block 1 Components - Foundation

This initial implementation provides the core foundation components for the agentic intelligence research system:

### 🎯 Core Components

#### 1. Email Templates (`email_templates.md`)
- **6 customizable email templates** for different workflow stages
- **Variable substitution system** with 23+ template variables
- **Markdown format** for easy editing and version control
- Templates include: Initial requests, reminders, and escalation emails

#### 2. Email Agent (`email_agent.py`)
- **Central SMTP email sending** with comprehensive error handling
- **Template rendering engine** with variable validation
- **Delivery tracking** and email validation
- **Multiple SMTP provider support** (Gmail, Outlook, custom)
- **Priority handling** and HTML/text email support

#### 3. Event Log Manager (`event_log_manager.py`)
- **S3-based event logging** in `events/{event_id}.json` format
- **Status tracking** for events and email communications
- **Trigger information** logging and timestamping
- **Automatic cleanup** of completed events
- **Comprehensive error handling** with workflow integration

#### 4. Workflow Log Manager (`workflow_log_manager.py`)
- **S3-based workflow execution logging** in `workflow_log/{run_id}.json` format
- **Step-by-step tracking** with timing and error details
- **Exception logging** with full tracebacks
- **Memory-efficient** run management
- **Statistics and reporting** capabilities

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from email_agent import EmailAgent, EmailConfig
from event_log_manager import EventLogManager, TriggerInfo
from workflow_log_manager import WorkflowLogManager

# Configure email agent
config = EmailConfig(
    smtp_server="smtp.gmail.com",
    smtp_port=587,
    username="your-email@gmail.com",
    password="your-app-password",
    sender_name="Your System Name"
)

# Initialize components
email_agent = EmailAgent(config)
event_logger = EventLogManager(bucket_name="your-s3-bucket")
workflow_logger = WorkflowLogManager(bucket_name="your-s3-bucket")

# Send templated email
template_vars = {
    'recipient_name': 'John Doe',
    'event_title': 'Team Meeting',
    'event_datetime': '2024-01-15 10:00 AM',
    'event_duration': '1 hour',
    'event_location': 'Conference Room A',
    'event_description': 'Weekly team sync',
    'sender_name': 'Meeting Coordinator'
}

result = email_agent.send_template_email(
    template_name="initial_request_template",
    to_email="john.doe@company.com",
    template_variables=template_vars
)
```

### Running the Demo

```bash
python example_usage.py
```

## 📧 Email Templates

The system includes 6 comprehensive email templates:

1. **Initial Request Template** - First invitation to calendar events
2. **Meeting Request Template** - General meeting requests
3. **First Reminder Template** - Gentle reminder for non-responses
4. **Second Reminder Template** - Urgent reminder with deadline
5. **Manager Escalation Template** - Escalation to managers
6. **Final Escalation Template** - Final notice escalation

### Template Variables

All templates support variable substitution using `{variable_name}` syntax:

- `{recipient_name}`, `{sender_name}` - People names
- `{event_title}`, `{event_datetime}`, `{event_location}` - Event details
- `{time_until_event}`, `{response_deadline}` - Time-based variables
- `{escalation_reason}`, `{business_justification}` - Escalation context
- And 13+ more variables for comprehensive customization

## 🔧 Configuration

### Environment Variables

```bash
# SMTP Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# AWS S3 Configuration
S3_EVENTLOG_BUCKET=your-events-bucket
S3_WORKFLOW_BUCKET=your-workflows-bucket
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
```

### SMTP Providers

#### Gmail Configuration
```python
from email_agent import create_gmail_config

config = create_gmail_config(
    email="your-email@gmail.com",
    password="your-app-password",
    sender_name="Your System"
)
```

#### Outlook Configuration
```python
from email_agent import create_outlook_config

config = create_outlook_config(
    email="your-email@outlook.com",
    password="your-password",
    sender_name="Your System"
)
```

## 🏗️ Architecture

### Data Flow
1. **Event Creation** → Event logged to S3
2. **Workflow Start** → Workflow run logged to S3
3. **Email Sending** → Template rendered, email sent, delivery tracked
4. **Status Updates** → Event and workflow status updated
5. **Error Handling** → All exceptions logged with context

### S3 Storage Structure
```
your-bucket/
├── events/
│   ├── event-001.json
│   ├── event-002.json
│   └── ...
└── workflow_log/
    ├── workflow-run-001.json
    ├── workflow-run-002.json
    └── ...
```

## 🛠️ Error Handling

All components implement comprehensive error handling:

- **Workflow Integration** - Errors automatically logged to workflow runs
- **Exception Tracking** - Full tracebacks captured
- **Graceful Degradation** - System continues operating on non-critical failures
- **Retry Logic** - Built-in retry capabilities for transient failures

## 🧪 Testing

Run the basic functionality tests:

```bash
python /tmp/test_basic_functionality.py
```

Expected output: All 4 test suites should pass ✓

## 🔮 Next Steps

Block 1 provides the foundation for:

- **Google Calendar API Integration** - Polling and event synchronization
- **Advanced Trigger Systems** - Time-based and event-driven triggers
- **Complex Agent Workflows** - Multi-step automation processes
- **Reminder & Escalation Logic** - Intelligent response handling
- **Production Deployment** - Scaling and monitoring capabilities

## 📄 License

This project is part of the Agentic Intelligence Research initiative.

---

**Status**: ✅ Block 1 Complete - Core foundation implemented and tested