"""
Email Agent - Central SMTP agent for sending request, reminder, and escalation emails.

This module provides a centralized email sending service with template support,
error handling, and logging integration for the agentic intelligence workflow system.
"""

import smtplib
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging


class EmailTemplate:
    """Represents an email template with subject and body."""
    
    def __init__(self, subject: str, body: str):
        self.subject = subject
        self.body = body
    
    def format(self, **kwargs) -> tuple[str, str]:
        """Format the template with provided variables."""
        try:
            formatted_subject = self.subject.format(**kwargs)
            formatted_body = self.body.format(**kwargs)
            return formatted_subject, formatted_body
        except KeyError as e:
            raise ValueError(f"Missing required template variable: {e}")


class EmailTemplateManager:
    """Manages email templates from the markdown file."""
    
    def __init__(self, template_file_path: str = "email_templates.md"):
        self.template_file_path = template_file_path
        self.templates = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load templates from the markdown file."""
        try:
            if not os.path.exists(self.template_file_path):
                logging.warning(f"Template file {self.template_file_path} not found. Using empty templates.")
                return
            
            with open(self.template_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Parse templates using regex patterns
            self._parse_templates(content)
            
        except Exception as e:
            logging.error(f"Failed to load email templates: {e}")
            self.templates = {}
    
    def _parse_templates(self, content: str):
        """Parse templates from markdown content."""
        # Pattern to match template sections
        pattern = r'\*\*Subject:\*\* (.+?)\n\n\*\*Body:\*\*\n```\n(.*?)\n```'
        matches = re.findall(pattern, content, re.DOTALL)
        
        # Predefined template names mapping
        template_names = [
            'initial_request',
            'confirmation_request', 
            'first_reminder',
            'urgent_reminder',
            'first_escalation',
            'final_escalation',
            'system_error',
            'processing_failure',
            'success_notification'
        ]
        
        for i, (subject, body) in enumerate(matches):
            if i < len(template_names):
                template_name = template_names[i]
                self.templates[template_name] = EmailTemplate(subject.strip(), body.strip())
    
    def get_template(self, template_name: str) -> Optional[EmailTemplate]:
        """Get a template by name."""
        return self.templates.get(template_name)
    
    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())


class EmailAgent:
    """Central SMTP agent for sending emails with template support."""
    
    def __init__(self, 
                 smtp_server: str,
                 smtp_port: int,
                 username: str,
                 password: str,
                 from_email: str,
                 template_manager: Optional[EmailTemplateManager] = None,
                 workflow_logger: Optional[Any] = None):
        """
        Initialize the email agent.
        
        Args:
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port
            username: SMTP username
            password: SMTP password
            from_email: From email address
            template_manager: Email template manager instance
            workflow_logger: Workflow logger for error reporting
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.template_manager = template_manager or EmailTemplateManager()
        self.workflow_logger = workflow_logger
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    @classmethod
    def from_config(cls, config: Dict[str, Any], workflow_logger: Optional[Any] = None) -> 'EmailAgent':
        """Create EmailAgent from configuration dictionary."""
        smtp_config = config.get('smtp', {})
        return cls(
            smtp_server=smtp_config.get('server'),
            smtp_port=smtp_config.get('port', 587),
            username=smtp_config.get('username'),
            password=smtp_config.get('password'),
            from_email=smtp_config.get('from_email'),
            workflow_logger=workflow_logger
        )
    
    def send_email(self,
                   to_email: str,
                   subject: str,
                   body: str,
                   cc: Optional[List[str]] = None,
                   bcc: Optional[List[str]] = None,
                   reply_to: Optional[str] = None) -> bool:
        """
        Send an email with the specified parameters.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            reply_to: Reply-to address (optional)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = Header(subject, 'utf-8')
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            if reply_to:
                msg['Reply-To'] = reply_to
            
            # Add body
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Calculate all recipients
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                text = msg.as_string()
                server.sendmail(self.from_email, recipients, text)
            
            self.logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {e}"
            self.logger.error(error_msg)
            
            # Report to workflow logger if available
            if self.workflow_logger:
                try:
                    self.workflow_logger.log_error(
                        component="email_agent",
                        error=str(e),
                        context={
                            "to_email": to_email,
                            "subject": subject,
                            "action": "send_email"
                        }
                    )
                except Exception as log_error:
                    self.logger.error(f"Failed to log error to workflow logger: {log_error}")
            
            return False
    
    def send_templated_email(self,
                           to_email: str,
                           template_name: str,
                           template_vars: Dict[str, Any],
                           cc: Optional[List[str]] = None,
                           bcc: Optional[List[str]] = None,
                           reply_to: Optional[str] = None) -> bool:
        """
        Send an email using a predefined template.
        
        Args:
            to_email: Recipient email address
            template_name: Name of the template to use
            template_vars: Variables to substitute in the template
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            reply_to: Reply-to address (optional)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Get template
            template = self.template_manager.get_template(template_name)
            if not template:
                raise ValueError(f"Template '{template_name}' not found")
            
            # Add timestamp if not provided
            if 'timestamp' not in template_vars:
                template_vars['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            
            # Format template
            subject, body = template.format(**template_vars)
            
            # Send email
            return self.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to
            )
            
        except Exception as e:
            error_msg = f"Failed to send templated email '{template_name}' to {to_email}: {e}"
            self.logger.error(error_msg)
            
            # Report to workflow logger if available
            if self.workflow_logger:
                try:
                    self.workflow_logger.log_error(
                        component="email_agent",
                        error=str(e),
                        context={
                            "to_email": to_email,
                            "template_name": template_name,
                            "template_vars": template_vars,
                            "action": "send_templated_email"
                        }
                    )
                except Exception as log_error:
                    self.logger.error(f"Failed to log error to workflow logger: {log_error}")
            
            return False
    
    def send_request_email(self, to_email: str, event_data: Dict[str, Any], workflow_run_id: str) -> bool:
        """Send an initial event processing request email."""
        template_vars = {
            'recipient_email': to_email,
            'workflow_run_id': workflow_run_id,
            **event_data
        }
        return self.send_templated_email(to_email, 'initial_request', template_vars)
    
    def send_reminder_email(self, to_email: str, event_data: Dict[str, Any], urgent: bool = False) -> bool:
        """Send a reminder email."""
        template_name = 'urgent_reminder' if urgent else 'first_reminder'
        template_vars = {
            'recipient_email': to_email,
            **event_data
        }
        return self.send_templated_email(to_email, template_name, template_vars)
    
    def send_escalation_email(self, to_email: str, event_data: Dict[str, Any], 
                            workflow_run_id: str, final: bool = False) -> bool:
        """Send an escalation email."""
        template_name = 'final_escalation' if final else 'first_escalation'
        template_vars = {
            'recipient_email': event_data.get('recipient_email', ''),
            'recipient_name': event_data.get('recipient_name', ''),
            'workflow_run_id': workflow_run_id,
            **event_data
        }
        return self.send_templated_email(to_email, template_name, template_vars)
    
    def send_error_notification(self, to_email: str, error_details: str, 
                              workflow_run_id: str, event_id: Optional[str] = None) -> bool:
        """Send a system error notification email."""
        template_vars = {
            'workflow_run_id': workflow_run_id,
            'error_details': error_details,
            'event_id': event_id or 'N/A'
        }
        return self.send_templated_email(to_email, 'system_error', template_vars)
    
    def test_connection(self) -> bool:
        """Test the SMTP connection."""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
            
            self.logger.info("SMTP connection test successful")
            return True
            
        except Exception as e:
            error_msg = f"SMTP connection test failed: {e}"
            self.logger.error(error_msg)
            
            if self.workflow_logger:
                try:
                    self.workflow_logger.log_error(
                        component="email_agent",
                        error=str(e),
                        context={"action": "test_connection"}
                    )
                except Exception as log_error:
                    self.logger.error(f"Failed to log error to workflow logger: {log_error}")
            
            return False


# Configuration validation
def validate_email_config(config: Dict[str, Any]) -> List[str]:
    """Validate email configuration and return list of errors."""
    errors = []
    smtp_config = config.get('smtp', {})
    
    required_fields = ['server', 'username', 'password', 'from_email']
    for field in required_fields:
        if not smtp_config.get(field):
            errors.append(f"Missing required SMTP configuration: {field}")
    
    if smtp_config.get('port') and not isinstance(smtp_config['port'], int):
        errors.append("SMTP port must be an integer")
    
    return errors