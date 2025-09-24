import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging


class EmailAgent:
    """
    Central agent for all email workflows (request, reminder, escalation).
    SMTP configuration is set during instantiation.
    """

    def __init__(self, smtp_server, smtp_port, username, password, sender_email):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender_email = sender_email

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
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.username, self.password)
                server.sendmail(self.sender_email, recipient, msg.as_string())
            logging.info(f"Email sent to {recipient} with subject '{subject}'")
            return True
        except Exception as e:
            logging.error(f"Failed to send email to {recipient}: {e}")
            return False


# Example usage:
# agent = EmailAgent("smtp.example.com", 465, "user", "pass",
# "noreply@example.com")
# agent.send_email("recipient@example.com", "Subject", "Body")
