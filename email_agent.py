"""
Email Agent - Central SMTP Email Sending Module

This module provides centralized email functionality for the Google Calendar event processing system.
It handles all email types: requests, reminders, escalations, and error notifications.
"""

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
import re
from jinja2 import Template
from email_validator import validate_email, EmailNotValidError


class EmailAgent:
    """Central email agent for sending all system emails."""
    
    def __init__(self, smtp_server: str = None, smtp_port: int = None, 
                 smtp_username: str = None, smtp_password: str = None,
                 admin_email: str = None, from_email: str = None):
        """
        Initialize EmailAgent with SMTP configuration.
        
        Args:
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port (default: 587 for TLS)
            smtp_username: SMTP authentication username
            smtp_password: SMTP authentication password
            admin_email: Administrator email for escalations
            from_email: From email address for outgoing emails
        """
        # SMTP Configuration - can be overridden by environment variables
        self.smtp_server = smtp_server or os.getenv('SMTP_SERVER', 'localhost')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = smtp_username or os.getenv('SMTP_USERNAME')
        self.smtp_password = smtp_password or os.getenv('SMTP_PASSWORD')
        self.admin_email = admin_email or os.getenv('ADMIN_EMAIL')
        self.from_email = from_email or os.getenv('FROM_EMAIL', self.smtp_username)
        
        # Load email templates
        self.templates = self._load_templates()
        
    def _load_templates(self) -> Dict[str, Dict[str, str]]:
        """Load email templates from email_templates.md file."""
        templates = {}
        
        try:
            with open('email_templates.md', 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse templates using regex
            template_pattern = r'### (\w+)\n\*\*Subject:\*\* (.*?)\n\n\*\*Body:\*\*\n```\n(.*?)\n```'
            matches = re.findall(template_pattern, content, re.DOTALL)
            
            for template_name, subject, body in matches:
                templates[template_name] = {
                    'subject': subject.strip(),
                    'body': body.strip()
                }
                
        except FileNotFoundError:
            # Default templates if file not found
            templates = self._get_default_templates()
            
        return templates
    
    def _get_default_templates(self) -> Dict[str, Dict[str, str]]:
        """Get default email templates if template file is not found."""
        return {
            'HUMAN_IN_LOOP_REQUEST': {
                'subject': 'Action Required: Validate Company Information for Calendar Event',
                'body': 'Hello,\n\nWe need your help to validate company information for event {{ event_id }}.\n\nEvent: {{ event_summary }}\nDate: {{ event_datetime }}\n\nPlease reply with the correct information.\n\nBest regards,\nSystem'
            },
            'REMINDER_TO_ORGANIZER': {
                'subject': 'Reminder: Follow-up Required for {{ event_summary }}',
                'body': 'Hello {{ organizer_email }},\n\nReminder for your event:\n{{ event_summary }}\nDate: {{ event_datetime }}\n\nBest regards,\nSystem'
            },
            'ESCALATION_TO_ADMIN': {
                'subject': 'Escalation: No Response for Event {{ event_id }}',
                'body': 'Hello Admin,\n\nEscalation for event {{ event_id }}: {{ event_summary }}\nOrganizer: {{ organizer_email }}\n\nBest regards,\nSystem'
            },
            'ERROR_NOTIFICATION': {
                'subject': 'System Error in Calendar Event Processing',
                'body': 'Hello Admin,\n\nError in processing:\nRun ID: {{ run_id }}\nError: {{ error_message }}\n\nBest regards,\nSystem'
            }
        }
    
    def _validate_email(self, email: str) -> bool:
        """Validate email address format."""
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False
    
    def _render_template(self, template_name: str, variables: Dict[str, Any]) -> Dict[str, str]:
        """Render email template with provided variables."""
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        template_data = self.templates[template_name]
        
        # Render subject and body with Jinja2
        subject_template = Template(template_data['subject'])
        body_template = Template(template_data['body'])
        
        rendered_subject = subject_template.render(**variables)
        rendered_body = body_template.render(**variables)
        
        return {
            'subject': rendered_subject,
            'body': rendered_body
        }
    
    def send_email(self, to_email: str, template_name: str, variables: Dict[str, Any],
                   cc_emails: Optional[List[str]] = None, bcc_emails: Optional[List[str]] = None) -> bool:
        """
        Send email using specified template and variables.
        
        Args:
            to_email: Recipient email address
            template_name: Name of template to use
            variables: Dictionary of variables for template rendering
            cc_emails: List of CC email addresses
            bcc_emails: List of BCC email addresses
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Validate recipient email
            if not self._validate_email(to_email):
                raise ValueError(f"Invalid recipient email: {to_email}")
            
            # Validate CC emails
            if cc_emails:
                for email in cc_emails:
                    if not self._validate_email(email):
                        raise ValueError(f"Invalid CC email: {email}")
            
            # Validate BCC emails
            if bcc_emails:
                for email in bcc_emails:
                    if not self._validate_email(email):
                        raise ValueError(f"Invalid BCC email: {email}")
            
            # Render template
            rendered = self._render_template(template_name, variables)
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = rendered['subject']
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Add timestamp to variables for logging
            variables['email_sent_timestamp'] = datetime.utcnow().isoformat()
            
            # Attach body
            msg.attach(MIMEText(rendered['body'], 'plain', 'utf-8'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                recipients = [to_email]
                if cc_emails:
                    recipients.extend(cc_emails)
                if bcc_emails:
                    recipients.extend(bcc_emails)
                
                server.send_message(msg, to_addrs=recipients)
            
            return True
            
        except Exception as e:
            # Log error (this would be logged to workflow log in real implementation)
            print(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_human_in_loop_request(self, event_data: Dict[str, Any], 
                                   company_name: str = None, web_domain: str = None) -> bool:
        """Send human-in-the-loop validation request email."""
        variables = {
            'event_id': event_data.get('id', ''),
            'event_summary': event_data.get('summary', ''),
            'event_description': event_data.get('description', ''),
            'event_datetime': event_data.get('dateTime', ''),
            'company_name': company_name,
            'web_domain': web_domain
        }
        
        return self.send_email(
            to_email=self.admin_email,
            template_name='HUMAN_IN_LOOP_REQUEST',
            variables=variables
        )
    
    def send_reminder_to_organizer(self, event_data: Dict[str, Any], 
                                   organizer_email: str, company_name: str = None, 
                                   web_domain: str = None) -> bool:
        """Send reminder email to event organizer."""
        variables = {
            'event_id': event_data.get('id', ''),
            'event_summary': event_data.get('summary', ''),
            'event_description': event_data.get('description', ''),
            'event_datetime': event_data.get('dateTime', ''),
            'organizer_email': organizer_email,
            'company_name': company_name,
            'web_domain': web_domain
        }
        
        return self.send_email(
            to_email=organizer_email,
            template_name='REMINDER_TO_ORGANIZER',
            variables=variables
        )
    
    def send_escalation_to_admin(self, event_data: Dict[str, Any], 
                                 organizer_email: str, reminder_sent_datetime: str,
                                 company_name: str = None, web_domain: str = None) -> bool:
        """Send escalation email to administrator."""
        variables = {
            'event_id': event_data.get('id', ''),
            'event_summary': event_data.get('summary', ''),
            'event_description': event_data.get('description', ''),
            'event_datetime': event_data.get('dateTime', ''),
            'organizer_email': organizer_email,
            'company_name': company_name,
            'web_domain': web_domain,
            'reminder_sent_datetime': reminder_sent_datetime
        }
        
        return self.send_email(
            to_email=self.admin_email,
            template_name='ESCALATION_TO_ADMIN',
            variables=variables
        )
    
    def send_error_notification(self, run_id: str, error_step: str, 
                               error_message: str, error_traceback: str = None,
                               event_id: str = None) -> bool:
        """Send error notification email to administrator."""
        variables = {
            'run_id': run_id,
            'event_id': event_id,
            'error_step': error_step,
            'error_message': error_message,
            'error_traceback': error_traceback,
            'error_timestamp': datetime.utcnow().isoformat()
        }
        
        return self.send_email(
            to_email=self.admin_email,
            template_name='ERROR_NOTIFICATION',
            variables=variables
        )
    
    def reload_templates(self):
        """Reload email templates from file."""
        self.templates = self._load_templates()


# Global email agent instance
email_agent = EmailAgent()