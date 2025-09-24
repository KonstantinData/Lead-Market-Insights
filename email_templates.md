# Email Templates

This file contains centralized email templates for the agentic intelligence research system. Templates use placeholder variables that will be replaced with actual values when sending emails.

## Available Placeholders

- `{name}`: Recipient's name
- `{company}`: Company name
- `{email}`: Recipient's email address
- `{request_id}`: Unique request identifier
- `{event_id}`: Event identifier
- `{request_details}`: Detailed request information
- `{deadline}`: Response deadline
- `{escalation_level}`: Current escalation level (1, 2, 3)
- `{original_date}`: Original request date
- `{days_overdue}`: Number of days overdue
- `{contact_person}`: Contact person for escalation
- `{phone}`: Contact phone number
- `{priority}`: Request priority (Low, Medium, High, Critical)

---

## Initial Request Template

**Subject:** Research Request #{request_id} - {company}

Dear {name},

We hope this email finds you well. We are reaching out regarding a research request that requires your expertise and input.

**Request Details:**
- Request ID: {request_id}
- Event ID: {event_id}
- Company: {company}
- Priority: {priority}
- Deadline: {deadline}

**Request Description:**
{request_details}

Your response would be greatly appreciated to help us move forward with this research initiative. Please reply to this email with your input or let us know if you need any clarification.

If you have any questions or concerns, please don't hesitate to contact us.

Best regards,
Agentic Intelligence Research Team

---

## First Reminder Template

**Subject:** Reminder: Research Request #{request_id} - Response Needed

Dear {name},

This is a friendly reminder about the research request we sent on {original_date}.

**Request Details:**
- Request ID: {request_id}
- Event ID: {event_id}
- Company: {company}
- Priority: {priority}
- Original Deadline: {deadline}

We understand you may be busy, but your input is valuable for our research. Could you please take a moment to review the request and provide your response?

**Original Request:**
{request_details}

If you need additional time or have any questions, please let us know so we can adjust our timeline accordingly.

Thank you for your time and cooperation.

Best regards,
Agentic Intelligence Research Team

---

## Second Reminder Template

**Subject:** Urgent: Research Request #{request_id} - Response Required

Dear {name},

We are following up on our research request sent on {original_date}, which is now {days_overdue} days overdue.

**Request Details:**
- Request ID: {request_id}
- Event ID: {event_id}
- Company: {company}
- Priority: {priority}
- Days Overdue: {days_overdue}

This request is important for our ongoing research, and we would greatly appreciate your prompt attention to this matter.

**Original Request:**
{request_details}

Please respond at your earliest convenience. If there are any issues preventing you from responding, please let us know so we can assist or make alternative arrangements.

Time is of the essence, and your cooperation is highly valued.

Best regards,
Agentic Intelligence Research Team

---

## Escalation Template

**Subject:** ESCALATION: Research Request #{request_id} - Immediate Action Required

Dear {name},

This is an escalation notice for research request #{request_id}, which was originally sent on {original_date} and is now {days_overdue} days overdue.

**Escalation Level:** {escalation_level}

**Request Details:**
- Request ID: {request_id}
- Event ID: {event_id}
- Company: {company}
- Priority: {priority}
- Days Overdue: {days_overdue}

Despite multiple attempts to reach you, we have not received a response to this critical research request:

{request_details}

**Immediate Action Required:**
Due to the critical nature of this request and the extended delay, we need an immediate response. If we do not hear from you within 24 hours, this matter will be escalated to the next level.

**Escalation Contact:**
- Name: {contact_person}
- Phone: {phone}
- Email: Please reply to this email

We value our relationship and hope to resolve this matter promptly. Please contact us immediately to discuss this request.

Urgent attention required.

Best regards,
Agentic Intelligence Research Team
Senior Management

---

## No Response Final Notice Template

**Subject:** FINAL NOTICE: Research Request #{request_id} - Account Review

Dear {name},

This is a final notice regarding research request #{request_id}, originally sent on {original_date}.

**Request Status:**
- Request ID: {request_id}
- Event ID: {event_id}
- Company: {company}
- Priority: {priority}
- Days Overdue: {days_overdue}
- Escalation Level: FINAL

After multiple attempts and escalations, we have not received a response to this critical research request. This lack of response is concerning and may impact our future collaboration.

**Original Request:**
{request_details}

**Next Steps:**
If we do not receive a response within 48 hours, this matter will be marked as unresolved and may affect:
- Future research collaboration opportunities
- Account status review
- Partnership evaluation

We strongly encourage you to contact us immediately to resolve this matter.

**Emergency Contact:**
- Name: {contact_person}
- Phone: {phone}
- Email: Please reply to this email

This is your final opportunity to respond before account review procedures are initiated.

Best regards,
Agentic Intelligence Research Team
Executive Management

---

## Success/Thank You Template

**Subject:** Thank You: Research Request #{request_id} - Response Received

Dear {name},

Thank you for your response to research request #{request_id}. We greatly appreciate your cooperation and the time you took to provide the requested information.

**Request Details:**
- Request ID: {request_id}
- Event ID: {event_id}
- Company: {company}
- Status: Completed

Your input is valuable to our research and will contribute to meaningful insights. We look forward to continuing our collaboration on future research initiatives.

If you have any questions about this request or future opportunities, please don't hesitate to contact us.

Thank you again for your cooperation.

Best regards,
Agentic Intelligence Research Team