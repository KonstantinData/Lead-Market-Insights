# Email Templates for Agentic Intelligence Research

This file contains standard email templates for various workflows in the agentic intelligence research system.

## Request Templates

### Initial Request Template
**Subject:** Google Calendar Event Request - {event_title}

Dear {recipient_name},

You have been invited to participate in the following Google Calendar event:

**Event:** {event_title}
**Date & Time:** {event_datetime}
**Duration:** {event_duration}
**Location:** {event_location}
**Description:** {event_description}

Please confirm your attendance by replying to this email or updating your status in Google Calendar.

If you have any questions or need to discuss alternative arrangements, please don't hesitate to reach out.

Best regards,
{sender_name}
Agentic Intelligence Research System

---

### Meeting Request Template
**Subject:** Meeting Request - {event_title}

Hello {recipient_name},

I would like to schedule a meeting with you:

**Topic:** {event_title}
**Proposed Date & Time:** {event_datetime}
**Expected Duration:** {event_duration}
**Meeting Type:** {meeting_type}
**Location/Link:** {event_location}

**Agenda:**
{event_description}

Please let me know if this time works for you, or suggest an alternative that better fits your schedule.

Looking forward to our discussion.

Best regards,
{sender_name}

---

## Reminder Templates

### First Reminder Template
**Subject:** Reminder: {event_title} - Response Needed

Dear {recipient_name},

This is a friendly reminder about the following event that requires your response:

**Event:** {event_title}
**Date & Time:** {event_datetime}
**Location:** {event_location}

We haven't received your response yet. Please confirm your attendance at your earliest convenience.

To respond:
- Reply to this email with your availability
- Update your status directly in Google Calendar
- Contact us if you need to discuss alternatives

Thank you for your attention to this matter.

Best regards,
{sender_name}
Agentic Intelligence Research System

---

### Second Reminder Template
**Subject:** 2nd Reminder: {event_title} - Urgent Response Required

Dear {recipient_name},

This is a second reminder regarding the event below. Your response is important for our planning:

**Event:** {event_title}
**Date & Time:** {event_datetime}
**Location:** {event_location}
**Time Until Event:** {time_until_event}

**Action Required:** Please respond by {response_deadline}

If you're unable to attend or need to reschedule, please let us know as soon as possible so we can make alternative arrangements.

Your prompt response would be greatly appreciated.

Best regards,
{sender_name}
Agentic Intelligence Research System

---

## Escalation Templates

### Manager Escalation Template
**Subject:** Escalation: No Response to Calendar Event - {event_title}

Dear {manager_name},

I am writing to inform you that we have not received a response from {recipient_name} regarding the following important event:

**Event Details:**
- **Title:** {event_title}
- **Date & Time:** {event_datetime}
- **Location:** {event_location}
- **Original Invite Sent:** {original_invite_date}
- **Reminders Sent:** {reminder_count}
- **Last Reminder:** {last_reminder_date}

**Impact:**
{escalation_reason}

Could you please follow up with {recipient_name} regarding their attendance? This event is important for {business_justification}.

If there are any scheduling conflicts or issues, please let us know so we can work on alternative solutions.

Thank you for your assistance.

Best regards,
{sender_name}
Agentic Intelligence Research System

---

### Final Escalation Template
**Subject:** Final Notice: {event_title} - {recipient_name} Non-Responsive

Dear {escalation_contact},

Despite multiple attempts to contact {recipient_name}, we have not received any response regarding the following critical event:

**Event Summary:**
- **Title:** {event_title}
- **Date & Time:** {event_datetime}
- **Location:** {event_location}
- **Invitee:** {recipient_name} ({recipient_email})

**Communication History:**
- Initial invite: {original_invite_date}
- First reminder: {first_reminder_date}
- Second reminder: {second_reminder_date}
- Manager escalation: {manager_escalation_date}

**Next Steps:**
{escalation_next_steps}

This is our final automated attempt to resolve this matter. Please advise on how to proceed.

Regards,
{sender_name}
Agentic Intelligence Research System

---

## Template Variables

### Common Variables
- `{recipient_name}` - Name of the email recipient
- `{recipient_email}` - Email address of the recipient
- `{sender_name}` - Name of the sender
- `{event_title}` - Title/subject of the calendar event
- `{event_datetime}` - Date and time of the event
- `{event_duration}` - Duration of the event
- `{event_location}` - Location or meeting link
- `{event_description}` - Event description/agenda

### Reminder-Specific Variables
- `{time_until_event}` - Time remaining until the event
- `{response_deadline}` - Deadline for response
- `{reminder_count}` - Number of reminders sent

### Escalation-Specific Variables
- `{manager_name}` - Name of the recipient's manager
- `{escalation_contact}` - Final escalation contact
- `{escalation_reason}` - Reason for escalation
- `{business_justification}` - Business importance of the event
- `{original_invite_date}` - Date of original invitation
- `{first_reminder_date}` - Date of first reminder
- `{second_reminder_date}` - Date of second reminder
- `{last_reminder_date}` - Date of most recent reminder
- `{manager_escalation_date}` - Date of manager escalation
- `{escalation_next_steps}` - Suggested next steps
- `{meeting_type}` - Type of meeting (in-person, virtual, etc.)

## Usage Notes

1. All templates support variable substitution using curly brace notation `{variable_name}`
2. Templates can be customized per workflow or event type
3. Variables should be validated before template rendering
4. Missing variables will be highlighted in the rendered output
5. Templates are stored in markdown format for easy editing and version control