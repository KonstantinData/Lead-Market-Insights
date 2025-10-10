"""
Simple IMAP poller (UNSEEN → list of dicts).
"""
from __future__ import annotations
import os, imaplib, email
from typing import List, Dict, Any
from .logging_setup import get_logger


log = get_logger("hitl.imap", "imap.log")


IMAP_HOST = os.getenv("IMAP_HOST", "localhost")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")


class InboxPoller:
# Explanation: readonly poll of UNSEEN messages
def __init__(self, host: str = IMAP_HOST, port: int = IMAP_PORT):
self.host, self.port = host, port


def poll_once(self, limit: int = 10) -> List[Dict[str, Any]]:
out: List[Dict[str, Any]] = []
with imaplib.IMAP4_SSL(self.host, self.port) as M:
M.login(IMAP_USER, IMAP_PASS)
M.select(IMAP_FOLDER, readonly=True)
typ, data = M.search(None, "UNSEEN")
if typ != "OK":
return out
ids = data[0].split()[:limit]
for num in ids:
typ, msg_data = M.fetch(num, "(RFC822)")
if typ != "OK":
continue
msg = email.message_from_bytes(msg_data[0][1])
body = ""
if msg.is_multipart():
for part in msg.walk():
if part.get_content_type() == "text/plain":
body = part.get_payload(decode=True).decode(errors="ignore")
break
else:
body = msg.get_payload(decode=True).decode(errors="ignore")
out.append({
"message_id": msg.get("Message-ID"),
"subject": msg.get("Subject"),
"from": msg.get("From"),
"body": body,
})
log.info("imap_polled", extra={"count": len(out)})
return out