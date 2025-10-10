"""
TLS SMTP sender. Writes logs to log_storage.
"""
from __future__ import annotations
import os, smtplib
from email.message import EmailMessage
from typing import Optional
from .logging_setup import get_logger


log = get_logger("hitl.smtp", "smtp.log")


SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@example.com")


class SmtpClient:
# Explanation: STARTTLS + optional auth
def __init__(self, host: str = SMTP_HOST, port: int = SMTP_PORT):
self.host, self.port = host, port


def send(self, to: str, subject: str, body: str, in_reply_to: Optional[str] = None) -> str:
msg = EmailMessage()
msg["From"], msg["To"], msg["Subject"] = SMTP_FROM, to, subject
if in_reply_to:
msg["In-Reply-To"] = in_reply_to
msg.set_content(body)
with smtplib.SMTP(self.host, self.port, timeout=30) as s:
s.starttls()
if SMTP_USER:
s.login(SMTP_USER, SMTP_PASS)
s.send_message(msg)
mid = msg.get("Message-ID", "generated-message-id")
log.info("smtp_sent", extra={"to": to, "mid": mid})
return mid