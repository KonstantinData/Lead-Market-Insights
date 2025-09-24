"""
Email Agent for Agentic Intelligence Research System

This module provides central SMTP email sending capabilities and email management
for all workflows in the system. Includes template rendering, delivery tracking,
and comprehensive error handling.
"""

import smtplib
import ssl
import re
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# from email.mime.html import HTMLToText  # Not needed for basic functionality
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import json
import logging
from pathlib import Path


@dataclass
class EmailConfig:
    """Configuration for email sending"""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False
    sender_name: str = "Agentic Intelligence Research"
    sender_email: Optional[str] = None
    
    def __post_init__(self):
        if self.sender_email is None:
            self.sender_email = self.username


@dataclass
class EmailMessage:
    """Email message structure"""
    to_email: str
    subject: str
    body: str
    to_name: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    bcc_emails: Optional[List[str]] = None
    html_body: Optional[str] = None
    priority: str = "normal"  # low, normal, high
    template_name: Optional[str] = None
    template_variables: Optional[Dict[str, Any]] = None


@dataclass
class EmailDeliveryResult:
    """Result of email delivery attempt"""
    success: bool
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None
    recipient_email: str = ""
    smtp_response: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class EmailTemplateManager:
    """Manages email templates from markdown file"""
    
    def __init__(self, template_file_path: str = "email_templates.md"):
        self.template_file_path = Path(template_file_path)
        self._templates_cache = {}
        self._variables_cache = set()
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load templates from markdown file"""
        try:
            if not self.template_file_path.exists():
                logging.warning(f"Template file not found: {self.template_file_path}")
                return
                
            with open(self.template_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse templates from markdown
            self._parse_templates(content)
            self._extract_variables(content)
            
        except Exception as e:
            logging.error(f"Failed to load email templates: {str(e)}")
            self._templates_cache = {}
    
    def _parse_templates(self, content: str) -> None:
        """Parse email templates from markdown content"""
        template_pattern = r'### (.+?)\n\*\*Subject:\*\* (.+?)\n\n(.*?)(?=\n---|\n### |\Z)'
        
        matches = re.findall(template_pattern, content, re.DOTALL)
        
        for match in matches:
            template_name = match[0].strip().lower().replace(' ', '_')
            subject = match[1].strip()
            body = match[2].strip()
            
            self._templates_cache[template_name] = {
                'subject': subject,
                'body': body
            }
    
    def _extract_variables(self, content: str) -> None:
        """Extract template variables from content"""
        variable_pattern = r'\{([^}]+)\}'
        variables = re.findall(variable_pattern, content)
        self._variables_cache = set(variables)
    
    def get_template(self, template_name: str) -> Optional[Dict[str, str]]:
        """Get template by name"""
        return self._templates_cache.get(template_name.lower().replace(' ', '_'))
    
    def list_templates(self) -> List[str]:
        """List available template names"""
        return list(self._templates_cache.keys())
    
    def get_template_variables(self) -> List[str]:
        """Get list of all template variables"""
        return sorted(list(self._variables_cache))
    
    def render_template(self, template_name: str, variables: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """Render template with variables, returns (subject, body)"""
        template = self.get_template(template_name)
        if not template:
            logging.error(f"Template not found: {template_name}")
            return None
        
        try:
            # Convert all variables to strings
            str_variables = {k: str(v) for k, v in variables.items()}
            
            subject = template['subject'].format(**str_variables)
            body = template['body'].format(**str_variables)
            
            return subject, body
            
        except KeyError as e:
            logging.error(f"Missing template variable: {e}")
            return None
        except Exception as e:
            logging.error(f"Template rendering error: {str(e)}")
            return None


class EmailAgent:
    """Central email agent for SMTP sending and email management"""
    
    def __init__(self, config: EmailConfig, workflow_logger=None):
        self.config = config
        self.workflow_logger = workflow_logger
        self.template_manager = EmailTemplateManager()
        self.delivery_history: List[EmailDeliveryResult] = []
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _log_workflow_error(self, step: str, error: Exception, event_id: str = None) -> None:
        """Log error to workflow logger if available"""
        if self.workflow_logger:
            try:
                self.workflow_logger.log_error(
                    step=step,
                    error=error,
                    event_id=event_id,
                    timestamp=datetime.now(timezone.utc)
                )
            except Exception as log_error:
                self.logger.error(f"Failed to log workflow error: {log_error}")
    
    def validate_email(self, email: str) -> bool:
        """Validate email address format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def create_message_from_template(self, 
                                   template_name: str, 
                                   to_email: str, 
                                   template_variables: Dict[str, Any],
                                   to_name: str = None,
                                   cc_emails: List[str] = None,
                                   priority: str = "normal") -> Optional[EmailMessage]:
        """Create email message from template"""
        try:
            rendered = self.template_manager.render_template(template_name, template_variables)
            if not rendered:
                return None
            
            subject, body = rendered
            
            return EmailMessage(
                to_email=to_email,
                to_name=to_name,
                subject=subject,
                body=body,
                cc_emails=cc_emails,
                priority=priority,
                template_name=template_name,
                template_variables=template_variables
            )
            
        except Exception as e:
            self._log_workflow_error("create_message_from_template", e)
            self.logger.error(f"Failed to create message from template: {e}")
            return None
    
    def send_email(self, message: EmailMessage, event_id: str = None) -> EmailDeliveryResult:
        """Send email message via SMTP"""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Validate recipient email
            if not self.validate_email(message.to_email):
                error_msg = f"Invalid email address: {message.to_email}"
                self.logger.error(error_msg)
                result = EmailDeliveryResult(
                    success=False,
                    error_message=error_msg,
                    recipient_email=message.to_email,
                    timestamp=start_time
                )
                self.delivery_history.append(result)
                return result
            
            # Create MIME message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = message.subject
            msg['From'] = f"{message.from_name or self.config.sender_name} <{message.from_email or self.config.sender_email}>"
            msg['To'] = f"{message.to_name or ''} <{message.to_email}>".strip('<> ')
            
            if message.cc_emails:
                msg['Cc'] = ', '.join(message.cc_emails)
            
            # Set priority
            if message.priority == "high":
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
            elif message.priority == "low":
                msg['X-Priority'] = '5'
                msg['X-MSMail-Priority'] = 'Low'
            
            # Add body
            msg.attach(MIMEText(message.body, 'plain', 'utf-8'))
            
            if message.html_body:
                msg.attach(MIMEText(message.html_body, 'html', 'utf-8'))
            
            # Send email
            recipients = [message.to_email]
            if message.cc_emails:
                recipients.extend(message.cc_emails)
            if message.bcc_emails:
                recipients.extend(message.bcc_emails)
            
            smtp_response = self._send_via_smtp(msg, recipients)
            
            result = EmailDeliveryResult(
                success=True,
                message_id=msg.get('Message-ID'),
                recipient_email=message.to_email,
                smtp_response=smtp_response,
                timestamp=start_time
            )
            
            self.delivery_history.append(result)
            self.logger.info(f"Email sent successfully to {message.to_email}")
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to send email to {message.to_email}: {str(e)}"
            self.logger.error(error_msg)
            self._log_workflow_error("send_email", e, event_id)
            
            result = EmailDeliveryResult(
                success=False,
                error_message=error_msg,
                recipient_email=message.to_email,
                timestamp=start_time
            )
            
            self.delivery_history.append(result)
            return result
    
    def _send_via_smtp(self, msg: MIMEMultipart, recipients: List[str]) -> str:
        """Send message via SMTP server"""
        if self.config.use_ssl:
            # Use SSL connection
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port, context=context) as server:
                server.login(self.config.username, self.config.password)
                response = server.send_message(msg, to_addrs=recipients)
                return str(response)
        else:
            # Use TLS connection
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                
                server.login(self.config.username, self.config.password)
                response = server.send_message(msg, to_addrs=recipients)
                return str(response)
    
    def send_template_email(self, 
                          template_name: str,
                          to_email: str,
                          template_variables: Dict[str, Any],
                          to_name: str = None,
                          cc_emails: List[str] = None,
                          priority: str = "normal",
                          event_id: str = None) -> EmailDeliveryResult:
        """Send email using template"""
        try:
            message = self.create_message_from_template(
                template_name=template_name,
                to_email=to_email,
                template_variables=template_variables,
                to_name=to_name,
                cc_emails=cc_emails,
                priority=priority
            )
            
            if not message:
                return EmailDeliveryResult(
                    success=False,
                    error_message=f"Failed to create message from template: {template_name}",
                    recipient_email=to_email
                )
            
            return self.send_email(message, event_id)
            
        except Exception as e:
            error_msg = f"Failed to send template email: {str(e)}"
            self.logger.error(error_msg)
            self._log_workflow_error("send_template_email", e, event_id)
            
            return EmailDeliveryResult(
                success=False,
                error_message=error_msg,
                recipient_email=to_email
            )
    
    def get_delivery_history(self, limit: int = None) -> List[EmailDeliveryResult]:
        """Get email delivery history"""
        history = sorted(self.delivery_history, key=lambda x: x.timestamp, reverse=True)
        if limit:
            return history[:limit]
        return history
    
    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics"""
        total = len(self.delivery_history)
        successful = sum(1 for r in self.delivery_history if r.success)
        failed = total - successful
        
        return {
            'total_sent': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'last_sent': max([r.timestamp for r in self.delivery_history]) if self.delivery_history else None
        }
    
    def test_connection(self) -> bool:
        """Test SMTP connection"""
        try:
            if self.config.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port, context=context) as server:
                    server.login(self.config.username, self.config.password)
            else:
                with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                    if self.config.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    server.login(self.config.username, self.config.password)
            
            self.logger.info("SMTP connection test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"SMTP connection test failed: {e}")
            self._log_workflow_error("test_connection", e)
            return False


# Example usage and configuration helper
def create_gmail_config(email: str, password: str, sender_name: str = None) -> EmailConfig:
    """Create Gmail SMTP configuration"""
    return EmailConfig(
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        username=email,
        password=password,
        use_tls=True,
        sender_name=sender_name or "Agentic Intelligence Research",
        sender_email=email
    )


def create_outlook_config(email: str, password: str, sender_name: str = None) -> EmailConfig:
    """Create Outlook/Office365 SMTP configuration"""
    return EmailConfig(
        smtp_server="smtp-mail.outlook.com",
        smtp_port=587,
        username=email,
        password=password,
        use_tls=True,
        sender_name=sender_name or "Agentic Intelligence Research",
        sender_email=email
    )


if __name__ == "__main__":
    # Example usage
    import os
    
    # Example configuration (would typically be loaded from environment)
    config = EmailConfig(
        smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USERNAME", ""),
        password=os.getenv("SMTP_PASSWORD", ""),
        use_tls=True,
        sender_name="Agentic Intelligence Research System"
    )
    
    # Create email agent
    agent = EmailAgent(config)
    
    # Test connection
    if agent.test_connection():
        print("✓ SMTP connection successful")
        
        # List available templates
        templates = agent.template_manager.list_templates()
        print(f"Available templates: {templates}")
        
        # Get template variables
        variables = agent.template_manager.get_template_variables()
        print(f"Template variables: {variables}")
        
    else:
        print("✗ SMTP connection failed")