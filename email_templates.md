# Email Templates

This file contains all email templates used by the system. Templates use Jinja2 syntax for variable substitution.

## Template Variables

Common variables available in all templates:
- `event_id`: The Google Calendar event ID
- `event_summary`: The event summary/title
- `event_description`: The event description
- `event_datetime`: The event date and time
- `company_name`: Extracted company name (if available)
- `web_domain`: Extracted web domain (if available)
- `organizer_email`: The event organizer's email address

## Templates

### HUMAN_IN_LOOP_REQUEST
**Subject:** Action Required: Validate Company Information for Calendar Event

**Body:**
```
Hello,

We need your help to validate company information for a Google Calendar event:

Event Details:
- Event ID: {{ event_id }}
- Summary: {{ event_summary }}
- Date/Time: {{ event_datetime }}
- Description: {{ event_description }}

We attempted to extract the following information:
- Company Name: {{ company_name or 'Not detected' }}
- Web Domain: {{ web_domain or 'Not detected' }}

Please verify and correct this information if needed by replying to this email with:
- Correct Company Name: [Your answer]
- Correct Web Domain: [Your answer]

If the information is correct, please reply with "CONFIRMED".

Thank you for your assistance.

Best regards,
Calendar Event Processing System
```

### REMINDER_TO_ORGANIZER
**Subject:** Reminder: Follow-up Required for {{ event_summary }}

**Body:**
```
Hello {{ organizer_email }},

This is a friendly reminder regarding your calendar event:

Event Details:
- Summary: {{ event_summary }}
- Date/Time: {{ event_datetime }}
- Company: {{ company_name }}
- Domain: {{ web_domain }}

Please ensure any follow-up actions for this event are completed.

Best regards,
Calendar Event Processing System
```

### ESCALATION_TO_ADMIN
**Subject:** Escalation: No Response for Event {{ event_id }}

**Body:**
```
Hello Admin,

An escalation has been triggered for the following calendar event due to no response to the reminder:

Event Details:
- Event ID: {{ event_id }}
- Summary: {{ event_summary }}
- Date/Time: {{ event_datetime }}
- Organizer: {{ organizer_email }}
- Company: {{ company_name }}
- Domain: {{ web_domain }}

Reminder was sent on: {{ reminder_sent_datetime }}
No response received after the reminder period.

Please take appropriate action.

Best regards,
Calendar Event Processing System
```

### ERROR_NOTIFICATION
**Subject:** System Error in Calendar Event Processing

**Body:**
```
Hello Admin,

An error occurred during calendar event processing:

Error Details:
- Run ID: {{ run_id }}
- Event ID: {{ event_id or 'N/A' }}
- Error Step: {{ error_step }}
- Timestamp: {{ error_timestamp }}
- Error Message: {{ error_message }}

{% if error_traceback %}
Traceback:
{{ error_traceback }}
{% endif %}

Please investigate and resolve the issue.

Best regards,
Calendar Event Processing System
```

## Template Usage Notes

1. Templates are loaded and rendered by the `email_agent.py` module
2. Variable substitution uses Jinja2 template engine
3. Missing variables will be replaced with empty strings unless specified otherwise
4. Admin email address should be configured in the system settings
5. Templates can be modified directly in this file - changes take effect immediately