"""Simplified IMAP poller used by the standalone HITL utilities."""

from __future__ import annotations

import email
import imaplib
import os
from email.message import Message
from typing import Any, Dict, List

from .logging_setup import get_logger


log = get_logger("hitl.imap", "imap.log")

IMAP_HOST = os.getenv("IMAP_HOST", "localhost")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")


class InboxPoller:
    """Read-only poller returning unseen messages as dictionaries."""

    def __init__(self, host: str = IMAP_HOST, port: int = IMAP_PORT) -> None:
        self.host = host
        self.port = port

    def poll_once(self, limit: int = 10) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if not (IMAP_USER and IMAP_PASS):
            log.debug("IMAP credentials missing; skipping poll")
            return messages

        try:
            with imaplib.IMAP4_SSL(self.host, self.port) as client:
                client.login(IMAP_USER, IMAP_PASS)
                client.select(IMAP_FOLDER, readonly=True)
                status, data = client.search(None, "UNSEEN")
                if status != "OK" or not data:
                    return messages

                ids = data[0].split()[:limit]
                for message_id in ids:
                    status, payload = client.fetch(message_id, "(RFC822)")
                    if status != "OK" or not payload:
                        continue

                    raw_bytes = payload[0][1]
                    message = email.message_from_bytes(raw_bytes)
                    messages.append(self._to_dict(message))
        except imaplib.IMAP4.error:
            log.exception("failed to poll IMAP inbox")
            return []

        log.info("imap_polled", extra={"count": len(messages)})
        return messages

    @staticmethod
    def _to_dict(message: Message) -> Dict[str, Any]:
        body = InboxPoller._extract_body(message)
        return {
            "message_id": message.get("Message-ID"),
            "subject": message.get("Subject"),
            "from": message.get("From"),
            "body": body,
        }

    @staticmethod
    def _extract_body(message: Message) -> str:
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload is not None:
                        return payload.decode(errors="ignore")
        payload = message.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode(errors="ignore")
        if isinstance(payload, str):
            return payload
        return ""