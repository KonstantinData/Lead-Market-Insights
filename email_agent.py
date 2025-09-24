"""
Email Agent for Agentic Intelligence Research System

This module provides SMTP email functionality for sending research requests,
reminders, and escalations. It includes comprehensive error handling and
logging integration with the workflow management system.
"""

import smtplib
import logging
import os
import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class EmailType(Enum):
    """Email types for different communication stages."""
    INITIAL_REQUEST = "initial_request"
    FIRST_REMINDER = "first_reminder"
    SECOND_REMINDER = "second_reminder"
    ESCALATION = "escalation"
    FINAL_NOTICE = "final_notice"
    SUCCESS_THANK_YOU = "success_thank_you"


class EmailPriority(Enum):
    """Email priority levels."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass
class EmailConfig:
    """SMTP email configuration."""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30
    from_email: str = ""
    from_name: str = "Agentic Intelligence Research Team"
    
    def __post_init__(self):
        if not self.from_email:
            self.from_email = self.username


@dataclass
class EmailRecipient:
    """Email recipient information."""
    name: str
    email: str
    company: str = ""
    phone: str = ""


@dataclass
class EmailContext:
    """Context information for email template replacement."""
    request_id: str
    event_id: str
    recipient: EmailRecipient
    request_details: str
    deadline: str
    priority: EmailPriority = EmailPriority.MEDIUM
    escalation_level: int = 1
    original_date: str = ""
    days_overdue: int = 0
    contact_person: str = "Research Coordinator"
    contact_phone: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        """Convert context to dictionary for template replacement."""
        return {
            'name': self.recipient.name,
            'email': self.recipient.email,
            'company': self.recipient.company,
            'phone': self.recipient.phone,
            'request_id': self.request_id,
            'event_id': self.event_id,
            'request_details': self.request_details,
            'deadline': self.deadline,
            'priority': self.priority.value,
            'escalation_level': str(self.escalation_level),
            'original_date': self.original_date,
            'days_overdue': str(self.days_overdue),
            'contact_person': self.contact_person,
            'contact_phone': self.contact_phone
        }


class EmailTemplateManager:
    """Manages email templates and placeholder replacement."""
    
    def __init__(self, template_file_path: str = "email_templates.md"):
        self.template_file_path = template_file_path
        self._templates = {}
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load email templates from markdown file."""
        try:
            with open(self.template_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Parse templates based on markdown headers
            template_sections = {
                'initial_request': r'## Initial Request Template\n\n(.*?)(?=\n---\n|\n## |\Z)',
                'first_reminder': r'## First Reminder Template\n\n(.*?)(?=\n---\n|\n## |\Z)',
                'second_reminder': r'## Second Reminder Template\n\n(.*?)(?=\n---\n|\n## |\Z)',
                'escalation': r'## Escalation Template\n\n(.*?)(?=\n---\n|\n## |\Z)',
                'final_notice': r'## No Response Final Notice Template\n\n(.*?)(?=\n---\n|\n## |\Z)',
                'success_thank_you': r'## Success/Thank You Template\n\n(.*?)(?=\n---\n|\n## |\Z)'
            }
            
            for template_name, pattern in template_sections.items():
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    template_content = match.group(1).strip()
                    # Split subject and body
                    lines = template_content.split('\n', 2)
                    if len(lines) >= 3 and lines[0].startswith('**Subject:**'):
                        subject = lines[0].replace('**Subject:**', '').strip()
                        body = lines[2] if len(lines) > 2 else ""
                        self._templates[template_name] = {
                            'subject': subject,
                            'body': body.strip()
                        }
                    else:
                        logging.warning(f"Invalid template format for {template_name}")
                        
        except FileNotFoundError:
            logging.error(f"Template file not found: {self.template_file_path}")
            self._create_default_templates()
        except Exception as e:
            logging.error(f"Error loading templates: {str(e)}")
            self._create_default_templates()
    
    def _create_default_templates(self) -> None:
        """Create default templates if file is not found."""
        self._templates = {
            'initial_request': {
                'subject': 'Research Request #{request_id} - {company}',
                'body': 'Dear {name},\n\nWe are reaching out regarding research request {request_id}.\n\nRequest Details:\n{request_details}\n\nDeadline: {deadline}\n\nBest regards,\nResearch Team'
            },
            'first_reminder': {
                'subject': 'Reminder: Research Request #{request_id}',
                'body': 'Dear {name},\n\nThis is a friendly reminder about request {request_id} sent on {original_date}.\n\nBest regards,\nResearch Team'
            },
            'second_reminder': {
                'subject': 'Urgent: Research Request #{request_id}',
                'body': 'Dear {name},\n\nUrgent reminder for request {request_id}, now {days_overdue} days overdue.\n\nBest regards,\nResearch Team'
            },
            'escalation': {
                'subject': 'ESCALATION: Research Request #{request_id}',
                'body': 'Dear {name},\n\nEscalation Level {escalation_level} for request {request_id}.\n\nImmediate action required.\n\nBest regards,\nResearch Team'
            },
            'final_notice': {
                'subject': 'FINAL NOTICE: Research Request #{request_id}',
                'body': 'Dear {name},\n\nFinal notice for request {request_id}.\n\nAccount review may be initiated.\n\nBest regards,\nResearch Team'
            },
            'success_thank_you': {
                'subject': 'Thank You: Research Request #{request_id}',
                'body': 'Dear {name},\n\nThank you for your response to request {request_id}.\n\nBest regards,\nResearch Team'
            }
        }
    
    def get_template(self, email_type: EmailType) -> Dict[str, str]:
        """Get template by email type."""
        template_key = email_type.value
        if template_key not in self._templates:
            logging.error(f"Template not found: {template_key}")
            return {'subject': 'Research Request', 'body': 'Template not found.'}
        return self._templates[template_key]
    
    def render_template(self, email_type: EmailType, context: EmailContext) -> Tuple[str, str]:
        """Render template with context data."""
        template = self.get_template(email_type)
        context_dict = context.to_dict()
        
        try:
            subject = template['subject'].format(**context_dict)
            body = template['body'].format(**context_dict)
            return subject, body
        except KeyError as e:
            logging.error(f"Missing context key: {e}")
            return template['subject'], template['body']
        except Exception as e:
            logging.error(f"Error rendering template: {e}")
            return template['subject'], template['body']


class EmailAgent:
    """SMTP Email Agent for sending research requests, reminders, and escalations."""
    
    def __init__(self, config: EmailConfig, workflow_logger=None):
        self.config = config
        self.workflow_logger = workflow_logger
        self.template_manager = EmailTemplateManager()
        self.logger = logging.getLogger(__name__)
        
        # Configure logging if not already configured
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    
    def _log_workflow_event(self, event_type: str, details: Dict[str, Any], error: bool = False) -> None:
        """Log events to workflow logger if available."""
        if self.workflow_logger:
            try:
                log_entry = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'component': 'email_agent',
                    'event_type': event_type,
                    'details': details,
                    'error': error
                }
                self.workflow_logger.log_event(log_entry)
            except Exception as e:
                self.logger.error(f"Failed to log workflow event: {e}")
    
    def _create_smtp_connection(self) -> smtplib.SMTP:
        """Create and configure SMTP connection."""
        try:
            if self.config.use_ssl:
                server = smtplib.SMTP_SSL(
                    self.config.smtp_server, 
                    self.config.smtp_port, 
                    timeout=self.config.timeout
                )
            else:
                server = smtplib.SMTP(
                    self.config.smtp_server, 
                    self.config.smtp_port, 
                    timeout=self.config.timeout
                )
                if self.config.use_tls:
                    server.starttls()
            
            server.login(self.config.username, self.config.password)
            return server
            
        except Exception as e:
            self.logger.error(f"Failed to create SMTP connection: {e}")
            raise
    
    def _create_email_message(
        self, 
        recipient: EmailRecipient, 
        subject: str, 
        body: str, 
        attachments: Optional[List[str]] = None
    ) -> MIMEMultipart:
        """Create email message with optional attachments."""
        msg = MIMEMultipart()
        msg['From'] = f"{self.config.from_name} <{self.config.from_email}>"
        msg['To'] = f"{recipient.name} <{recipient.email}>"
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Add attachments if provided
        if attachments:
            for file_path in attachments:
                try:
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {os.path.basename(file_path)}'
                    )
                    msg.attach(part)
                except Exception as e:
                    self.logger.error(f"Failed to attach file {file_path}: {e}")
        
        return msg
    
    def send_email(
        self, 
        email_type: EmailType, 
        context: EmailContext, 
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Send email using specified type and context.
        
        Args:
            email_type: Type of email to send
            context: Email context with recipient and data
            attachments: Optional list of file paths to attach
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        start_time = datetime.utcnow()
        
        try:
            # Render template
            subject, body = self.template_manager.render_template(email_type, context)
            
            # Create email message
            msg = self._create_email_message(context.recipient, subject, body, attachments)
            
            # Send email
            with self._create_smtp_connection() as server:
                server.send_message(msg)
            
            # Log success
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(
                f"Email sent successfully - Type: {email_type.value}, "
                f"Recipient: {context.recipient.email}, "
                f"Request ID: {context.request_id}, "
                f"Duration: {duration:.2f}s"
            )
            
            self._log_workflow_event('email_sent', {
                'email_type': email_type.value,
                'recipient': context.recipient.email,
                'request_id': context.request_id,
                'event_id': context.event_id,
                'subject': subject,
                'duration_seconds': duration
            })
            
            return True
            
        except Exception as e:
            # Log error
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Failed to send email - Type: {email_type.value}, " \
                       f"Recipient: {context.recipient.email}, " \
                       f"Request ID: {context.request_id}, " \
                       f"Error: {str(e)}"
            
            self.logger.error(error_msg)
            
            self._log_workflow_event('email_send_failed', {
                'email_type': email_type.value,
                'recipient': context.recipient.email,
                'request_id': context.request_id,
                'event_id': context.event_id,
                'error': str(e),
                'duration_seconds': duration
            }, error=True)
            
            return False
    
    def send_initial_request(self, context: EmailContext, attachments: Optional[List[str]] = None) -> bool:
        """Send initial research request email."""
        return self.send_email(EmailType.INITIAL_REQUEST, context, attachments)
    
    def send_reminder(self, context: EmailContext, reminder_level: int = 1) -> bool:
        """Send reminder email based on level."""
        if reminder_level == 1:
            email_type = EmailType.FIRST_REMINDER
        elif reminder_level == 2:
            email_type = EmailType.SECOND_REMINDER
        else:
            email_type = EmailType.ESCALATION
            context.escalation_level = reminder_level - 2
        
        return self.send_email(email_type, context)
    
    def send_escalation(self, context: EmailContext, escalation_level: int = 1) -> bool:
        """Send escalation email."""
        context.escalation_level = escalation_level
        
        if escalation_level >= 3:
            email_type = EmailType.FINAL_NOTICE
        else:
            email_type = EmailType.ESCALATION
        
        return self.send_email(email_type, context)
    
    def send_thank_you(self, context: EmailContext) -> bool:
        """Send thank you email for successful response."""
        return self.send_email(EmailType.SUCCESS_THANK_YOU, context)
    
    def test_connection(self) -> bool:
        """Test SMTP connection."""
        try:
            with self._create_smtp_connection() as server:
                self.logger.info("SMTP connection test successful")
                return True
        except Exception as e:
            self.logger.error(f"SMTP connection test failed: {e}")
            return False


def create_email_config_from_env() -> EmailConfig:
    """Create email configuration from environment variables."""
    return EmailConfig(
        smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        smtp_port=int(os.getenv('SMTP_PORT', '587')),
        username=os.getenv('SMTP_USERNAME', ''),
        password=os.getenv('SMTP_PASSWORD', ''),
        use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
        use_ssl=os.getenv('SMTP_USE_SSL', 'false').lower() == 'true',
        timeout=int(os.getenv('SMTP_TIMEOUT', '30')),
        from_email=os.getenv('SMTP_FROM_EMAIL', ''),
        from_name=os.getenv('SMTP_FROM_NAME', 'Agentic Intelligence Research Team')
    )


# Example usage and testing
if __name__ == "__main__":
    # Example configuration (use environment variables in production)
    config = EmailConfig(
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        username="your_email@gmail.com",
        password="your_app_password",
        from_email="research@company.com",
        from_name="Research Team"
    )
    
    # Create email agent
    agent = EmailAgent(config)
    
    # Test connection
    if agent.test_connection():
        print("SMTP connection successful!")
    
    # Example recipient and context
    recipient = EmailRecipient(
        name="John Doe",
        email="john.doe@example.com",
        company="Example Corp",
        phone="+1-555-0123"
    )
    
    context = EmailContext(
        request_id="REQ-2024-001",
        event_id="EVT-001",
        recipient=recipient,
        request_details="We need your expertise on AI model evaluation for our research project.",
        deadline="2024-01-15",
        priority=EmailPriority.HIGH,
        original_date="2024-01-01",
        days_overdue=3,
        contact_person="Dr. Smith",
        contact_phone="+1-555-0456"
    )
    
    # Example: Send initial request
    print("Sending initial request...")
    success = agent.send_initial_request(context)
    print(f"Initial request sent: {success}")
    
    # Example: Send reminder
    print("Sending reminder...")
    success = agent.send_reminder(context, reminder_level=1)
    print(f"Reminder sent: {success}")
    
    # Example: Send escalation
    print("Sending escalation...")
    success = agent.send_escalation(context, escalation_level=2)
    print(f"Escalation sent: {success}")