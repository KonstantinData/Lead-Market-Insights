# -*- coding: utf-8 -*-
"""
agents/inbox_poller.py

# Explanation
# Minimal IMAP poller that scans INBOX for fresh HITL replies and turns them
# into structured decisions for MasterWorkflowAgent via WorkflowOrchestrator.on_inbox_decision().

# Commands (first line of the mail body):
#   APPROVE
#   DECLINE
#   CHANGE: key=value; key2=value2
#
# Features:
# - IMAP SSL (e.g., OVH): host/port/user/pass from .env/settings
# - Filters by subject containing "HITL" (narrow scope)
# - Extracts run_id from X-Run-Id header or subject (run-<uuid>)
# - Idempotent via local seen-store; does not reprocess same message
# - Privacy-conscious: does not persist full email content
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from pathlib import Path
from typing import Dict, Iterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class _ImapConfig:
    host: str
    port: int
    user: str
    password: str
    folder: str = "INBOX"
    use_ssl: bool = True
    subject_filter_token: str = "HITL"


class InboxPoller:
    """# Explanation
    # Narrow IMAP poller for HITL replies.
    """

    def __init__(self, settings: object) -> None:
        self.settings = settings
        self.cfg = self._load_config(settings)
        self._seen_dir = (
            Path(
                getattr(
                    settings, "workflow_log_dir", "log_storage/run_history/workflows"
                )
            )
            / "inbox_seen"
        )
        self._seen_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "InboxPoller: using folder=%s host=%s", self.cfg.folder, self.cfg.host
        )

    def _load_config(self, settings: object) -> _ImapConfig:
        host = getattr(settings, "IMAP_HOST", None) or os.getenv("IMAP_HOST")
        port = getattr(settings, "IMAP_PORT", None) or os.getenv("IMAP_PORT", "993")
        user = getattr(settings, "IMAP_USER", None) or os.getenv("IMAP_USER")
        pwd = getattr(settings, "IMAP_PASS", None) or os.getenv("IMAP_PASS")
        folder = getattr(settings, "IMAP_FOLDER", None) or os.getenv(
            "IMAP_FOLDER", "INBOX"
        )

        if not host or not user or not pwd:
            raise RuntimeError(
                "IMAP configuration incomplete (IMAP_HOST/IMAP_USER/IMAP_PASS)"
            )

        try:
            port = int(port)
        except Exception:
            port = 993

        return _ImapConfig(
            host=str(host),
            port=port,
            user=str(user),
            password=str(pwd),
            folder=str(folder),
            use_ssl=True,
        )

    # ---------------- public API ----------------

    def poll(self, max_items: int = 25) -> Iterator[Dict]:
        """# Explanation
        # Iterate over parsed HITL decisions (<= max_items).
        # Decision shape: {"status": "...", "extra": {...}, "run_id": "...", "source_msg_id": "..."}
        """
        try:
            conn = imaplib.IMAP4_SSL(self.cfg.host, self.cfg.port)
            conn.login(self.cfg.user, self.cfg.password)
        except Exception as exc:
            logger.error("IMAP connect/login failed: %s", exc)
            return iter(())

        try:
            conn.select(self.cfg.folder, readonly=True)
            typ, data = conn.search(None, "UNSEEN")
            if typ != "OK":
                return iter(())

            ids = (data[0] or b"").split()
            ids = ids[-max_items:]
            for msg_id in reversed(ids):
                try:
                    uid = self._fetch_uid(conn, msg_id)
                    if uid and self._is_seen(uid):
                        continue

                    typ, msg_data = conn.fetch(msg_id, "(RFC822)")
                    if typ != "OK" or not msg_data:
                        self._mark_seen(uid)
                        continue
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    subject = self._decoded_subject(msg)
                    if self.cfg.subject_filter_token not in subject:
                        self._mark_seen(uid)
                        continue

                    run_id = self._extract_run_id(msg)
                    body = self._extract_text_body(msg)
                    decision = self._parse_decision(body, run_id)
                    if decision:
                        decision["source_msg_id"] = (
                            msg.get("Message-ID") or ""
                        ).strip()
                        yield decision

                    self._mark_seen(uid)

                except Exception:
                    logger.exception("IMAP parsing failed for message id=%s", msg_id)
                    try:
                        uid = self._fetch_uid(conn, msg_id)
                        self._mark_seen(uid)
                    except Exception:
                        pass
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    # ---------------- helpers ----------------

    def _fetch_uid(self, conn: imaplib.IMAP4_SSL, msg_id: bytes) -> Optional[str]:
        typ, data = conn.fetch(msg_id, "(UID)")
        if typ != "OK" or not data or not isinstance(data[0], bytes):
            return None
        parts = data[0].decode("utf-8", errors="ignore").split()
        try:
            idx = parts.index("UID")
            return parts[idx + 1].rstrip(")")
        except Exception:
            return None

    def _is_seen(self, uid: Optional[str]) -> bool:
        return bool(uid) and (self._seen_dir / f"{uid}.seen").exists()

    def _mark_seen(self, uid: Optional[str]) -> None:
        if uid:
            (self._seen_dir / f"{uid}.seen").write_text("1", encoding="utf-8")

    def _decoded_subject(self, msg: email.message.Message) -> str:
        try:
            return str(make_header(decode_header(msg.get("Subject") or "")))
        except Exception:
            return msg.get("Subject") or ""

    def _extract_run_id(self, msg: email.message.Message) -> Optional[str]:
        rid = (msg.get("X-Run-Id") or msg.get("X-Run-ID") or "").strip()
        if rid:
            return rid
        subj = self._decoded_subject(msg)
        m = re.search(r"run-([a-f0-9\-]{8,})", subj, re.I)
        return m.group(0) if m else None

    def _extract_text_body(self, msg: email.message.Message) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = (part.get("Content-Disposition") or "").lower()
                if ctype == "text/plain" and "attachment" not in disp:
                    try:
                        return part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="ignore"
                        )
                    except Exception:
                        continue
        else:
            try:
                return msg.get_payload(decode=True).decode(
                    msg.get_content_charset() or "utf-8", errors="ignore"
                )
            except Exception:
                pass
        return ""

    def _parse_decision(self, body: str, run_id: Optional[str]) -> Optional[Dict]:
        text = (body or "").strip()
        if not text:
            return None

        first_line = text.splitlines()[0].strip().upper()

        if first_line.startswith("APPROVE"):
            return {"status": "approved", "extra": {}, "run_id": run_id or "unknown"}
        if first_line.startswith("DECLINE"):
            return {"status": "declined", "extra": {}, "run_id": run_id or "unknown"}

        if first_line.startswith("CHANGE"):
            m = re.search(r"CHANGE\s*:\s*(.+)$", first_line, re.I)
            changes_str = m.group(1) if m else ""
            extra: Dict[str, str] = {}
            for pair in re.split(r"[;,\n]", changes_str):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k:
                        extra[k] = v
            return {
                "status": "change_requested",
                "extra": extra,
                "run_id": run_id or "unknown",
            }

        return None
