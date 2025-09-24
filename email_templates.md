# Email Templates

This file contains standardized, editable email templates with placeholders for all workflows in the agentic intelligence system.

## Template Variables

The following placeholders can be used in any template:
- `{event_id}` - Unique identifier for the calendar event
- `{event_title}` - Title of the calendar event
- `{event_date}` - Date of the event
- `{event_time}` - Time of the event
- `{event_description}` - Description of the event
- `{attendees}` - List of event attendees
- `{organizer}` - Event organizer
- `{workflow_run_id}` - Unique identifier for the workflow run
- `{timestamp}` - Current timestamp
- `{recipient_name}` - Name of the email recipient
- `{recipient_email}` - Email address of the recipient

## Request Templates

### Initial Event Processing Request
**Subject:** Event Processing Request: {event_title} - {event_date}

**Body:**
```
Dear {recipient_name},

A new calendar event requires processing:

Event Details:
- Title: {event_title}
- Date: {event_date}
- Time: {event_time}
- Description: {event_description}
- Organizer: {organizer}
- Attendees: {attendees}

Event ID: {event_id}
Workflow Run ID: {workflow_run_id}

Please review and take appropriate action.

Best regards,
Agentic Intelligence System
Generated at: {timestamp}
```

### Event Confirmation Request
**Subject:** Please Confirm: {event_title} - {event_date}

**Body:**
```
Hello {recipient_name},

Please confirm your participation in the following event:

Event: {event_title}
Date: {event_date}
Time: {event_time}
Location/Details: {event_description}

To confirm, please reply to this email or update your calendar response.

Event ID: {event_id}

Thank you,
Agentic Intelligence System
```

## Reminder Templates

### First Reminder
**Subject:** Reminder: {event_title} - {event_date}

**Body:**
```
Dear {recipient_name},

This is a friendly reminder about the upcoming event:

Event: {event_title}
Date: {event_date}
Time: {event_time}
Description: {event_description}

Please ensure you are prepared and available.

Event ID: {event_id}

Best regards,
Agentic Intelligence System
```

### Second Reminder (Urgent)
**Subject:** URGENT Reminder: {event_title} - {event_date}

**Body:**
```
Dear {recipient_name},

This is an urgent reminder about the upcoming event:

Event: {event_title}
Date: {event_date}
Time: {event_time}

This event is approaching soon. Please confirm your attendance or contact the organizer if you cannot attend.

Event ID: {event_id}

Urgent regards,
Agentic Intelligence System
```

## Escalation Templates

### First Escalation
**Subject:** Escalation Required: {event_title} - No Response

**Body:**
```
Dear Team,

The following event requires escalation due to lack of response:

Event Details:
- Title: {event_title}
- Date: {event_date}
- Time: {event_time}
- Original Recipient: {recipient_name} ({recipient_email})

No response has been received after multiple attempts. Please review and take appropriate action.

Event ID: {event_id}
Workflow Run ID: {workflow_run_id}

Escalation Notice,
Agentic Intelligence System
Generated at: {timestamp}
```

### Final Escalation
**Subject:** FINAL ESCALATION: {event_title} - Immediate Action Required

**Body:**
```
ATTENTION: FINAL ESCALATION

Event: {event_title}
Date: {event_date}
Time: {event_time}
Unresponsive Recipient: {recipient_name} ({recipient_email})

This is the final escalation attempt. Immediate manual intervention is required.

Event ID: {event_id}
Workflow Run ID: {workflow_run_id}

FINAL NOTICE,
Agentic Intelligence System
Generated at: {timestamp}
```

## Error Notification Templates

### System Error Notification
**Subject:** System Error in Workflow {workflow_run_id}

**Body:**
```
SYSTEM ERROR DETECTED

An error occurred in the agentic intelligence workflow system:

Workflow Run ID: {workflow_run_id}
Event ID: {event_id}
Timestamp: {timestamp}

Error Details:
{error_details}

Please check the system logs for more information.

System Administrator,
Agentic Intelligence System
```

### Processing Failure Notification
**Subject:** Event Processing Failed: {event_title}

**Body:**
```
EVENT PROCESSING FAILURE

Failed to process the following event:

Event: {event_title}
Date: {event_date}
Event ID: {event_id}
Workflow Run ID: {workflow_run_id}

Error: {error_details}

Manual intervention may be required.

System Alert,
Agentic Intelligence System
Generated at: {timestamp}
```

## Success Notification Templates

### Event Processed Successfully
**Subject:** Event Successfully Processed: {event_title}

**Body:**
```
Dear {recipient_name},

The following event has been successfully processed:

Event: {event_title}
Date: {event_date}
Time: {event_time}
Event ID: {event_id}

All required actions have been completed.

Best regards,
Agentic Intelligence System
```

---

## Template Usage Notes

1. All templates support variable substitution using the format `{variable_name}`
2. Templates can be customized by editing this file
3. New templates can be added following the same format
4. Ensure all required variables are provided when using templates
5. Templates are loaded at runtime, so changes take effect immediately