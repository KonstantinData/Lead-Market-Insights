import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Optional
import sys
import os

# Add utils to path for config import
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.config import get_smtp_config, SMTPConfig


class EmailAgent:
    """
    Central agent for all email workflows (request, reminder, escalation).
    SMTP configuration is loaded from environment variables.
    """

    def __init__(self, smtp_config: Optional[SMTPConfig] = None):
        """
        Initialize EmailAgent with SMTP configuration.
        
        Args:
            smtp_config: Optional SMTPConfig object. If None, loads from environment variables.
        """
        if smtp_config is None:
            smtp_config = get_smtp_config()
        
        config = smtp_config.get_smtp_config()
        self.smtp_server = config["smtp_server"]
        self.smtp_port = config["smtp_port"]
        self.username = config["username"]
        self.password = config["password"]
        self.sender_email = config["sender_email"]
        self.secure = config["secure"]
    
    @classmethod
    def from_env(cls):
        """
        Create EmailAgent instance using environment variables.
        
        Returns:
            EmailAgent: Configured email agent
        """
        return cls()

    def send_email(self, recipient, subject, body, html_body=None):
        """
        Sends an email. Optionally, an HTML body can be provided.
        """
        msg = MIMEMultipart("alternative")
        msg["From"] = self.sender_email
        msg["To"] = recipient
        msg["Subject"] = subject

        part1 = MIMEText(body, "plain")
        msg.attach(part1)
        if html_body:
            part2 = MIMEText(html_body, "html")
            msg.attach(part2)

        try:
            if self.secure:
                # Use SMTP_SSL for secure connection (typically port 465)
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.username, self.password)
                    server.sendmail(self.sender_email, recipient, msg.as_string())
            else:
                # Use SMTP with STARTTLS (typically port 587)
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.username, self.password)
                    server.sendmail(self.sender_email, recipient, msg.as_string())
            
            logging.info(f"Email sent to {recipient} with subject '{subject}'")
            return True
        except Exception as e:
            logging.error(f"Failed to send email to {recipient}: {e}")
            return False


# Example usage:
# Ensure environment variables are set (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SECURE, MAIL_FROM)
# agent = EmailAgent.from_env()
# agent.send_email("recipient@example.com", "Subject", "Body")
