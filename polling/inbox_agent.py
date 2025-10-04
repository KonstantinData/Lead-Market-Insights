"""IMAP inbox polling agent used for manual review workflows."""

from __future__ import annotations

import asyncio
import imaplib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from typing import Awaitable, Callable, Dict, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)


AuditHandler = Callable[["InboxMessage", Optional[str]], Awaitable[None]]


_APPROVED_DECISIONS = {
    "approve",
    "approved",
    "ok",
    "okay",
    "yes",
    "ja",
    "sure",
}
_DECLINED_DECISIONS = {
    "decline",
    "declined",
    "no",
    "nope",
    "reject",
    "rejected",
    "nein",
}
_FIELD_KEY_WHITELIST = {"company_name", "web_domain"}
_FIELD_KEY_ALIASES = {
    "company_domain": "web_domain",
    "domain": "web_domain",
    "website": "web_domain",
}


def parse_dossier_decision(body: str) -> Optional[str]:
    """Return the organiser's dossier decision extracted from *body*."""

    if not body:
        return None

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        for token in _APPROVED_DECISIONS:
            if re.search(rf"\b{re.escape(token)}\b", lowered):
                return "approved"
        for token in _DECLINED_DECISIONS:
            if re.search(rf"\b{re.escape(token)}\b", lowered):
                return "declined"
        return None
    return None


def parse_missing_info_key_values(body: str) -> Dict[str, str]:
    """Return normalised key/value pairs extracted from *body*."""

    if not body:
        return {}

    fields: Dict[str, str] = {}
    for raw_line in body.splitlines():
        if ":" not in raw_line:
            continue
        key_part, value_part = raw_line.split(":", 1)
        normalised_key = re.sub(r"[^a-z0-9]+", "_", key_part.strip().lower()).strip("_")
        if not normalised_key:
            continue
        mapped_key = _FIELD_KEY_ALIASES.get(normalised_key, normalised_key)
        if mapped_key not in _FIELD_KEY_WHITELIST:
            continue
        value = value_part.strip()
        if value:
            fields[mapped_key] = value
    return fields


@dataclass(slots=True)
class InboxMessage:
    """Normalized representation of an inbound email message."""

    id: str
    subject: str
    sender: str
    body: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    received_at: Optional[datetime] = None

    def header(self, name: str) -> Optional[str]:
        """Return the value for *name* (case-insensitive)."""

        if not self.headers:
            return None
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value
        return None


class InboxAgent:
    """Polls an IMAP mailbox and forwards relevant messages to handlers."""

    _AUDIT_HEADER_CANDIDATES = (
        "x-leadmi-audit-id",
        "x-leadmi-audit",
        "x-leadmi-auditid",
    )
    _AUDIT_SUBJECT_PATTERN = re.compile(
        r"\baudit(?:\s*id)?\s*[:#-]?\s*([A-Za-z0-9_-]{4,})",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        config: Mapping[str, object] | object,
        poll_interval: float = 60.0,
    ) -> None:
        self.config = config
        self.poll_interval = poll_interval
        self._handlers: list[AuditHandler] = []
        self._dedup_lock = asyncio.Lock()
        self._seen_audit_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Handler management
    # ------------------------------------------------------------------
    def register_handler(self, handler: AuditHandler) -> None:
        """Register *handler* to receive inbox messages."""

        if not callable(handler):
            raise TypeError("handler must be awaitable")
        self._handlers.append(handler)

    # ------------------------------------------------------------------
    async def _dispatch_message(self, message: InboxMessage) -> bool:
        """Dispatch *message* to registered handlers if any.

        Returns ``True`` when at least one handler has been invoked and the
        message wasn't dropped due to deduplication.
        """

        audit_id = self._detect_audit_id(message)

        async with self._dedup_lock:
            if audit_id and audit_id in self._seen_audit_ids:
                logger.debug("Duplicate audit_id detected: %s", audit_id)
                return False
            if audit_id:
                self._seen_audit_ids.add(audit_id)

        if not self._handlers:
            logger.debug("Dropping inbox message %s; no handlers registered.", message.id)
            return False

        for handler in list(self._handlers):
            try:
                await handler(message, audit_id)
            except Exception:  # pragma: no cover - surface exception paths
                logger.exception("Inbox handler %r failed for %s", handler, message.id)
        return True

    # ------------------------------------------------------------------
    def _detect_audit_id(self, message: InboxMessage) -> Optional[str]:
        """Extract an audit identifier from headers or the subject."""

        for candidate in self._AUDIT_HEADER_CANDIDATES:
            header_value = message.header(candidate)
            if header_value:
                return header_value.strip()

        subject = message.subject or ""
        match = self._AUDIT_SUBJECT_PATTERN.search(subject)
        if match:
            return match.group(1).strip()
        return None

    # ------------------------------------------------------------------
    async def fetch_new_messages(self) -> Sequence[InboxMessage]:
        """Return new inbox messages.

        Sub-classes can override this method to integrate with an IMAP client.
        """

        if not self._is_configured():
            return []

        return await asyncio.to_thread(self._fetch_new_messages_sync)

    # ------------------------------------------------------------------
    def _fetch_new_messages_sync(self) -> Sequence[InboxMessage]:
        """Synchronously retrieve unseen messages from the configured mailbox."""

        host = self._config_value("imap_host")
        username = self._config_value("imap_username") or self._config_value("imap_user")
        password = self._config_value("imap_password")

        def _config_attr(name: str, default: Optional[object] = None) -> Optional[object]:
            if isinstance(self.config, Mapping):
                return self.config.get(name, default)
            return getattr(self.config, name, default)

        port_value = _config_attr("imap_port", 993)
        try:
            port = int(port_value) if port_value is not None else 993
        except (TypeError, ValueError):
            port = 993

        use_ssl_value = _config_attr("imap_use_ssl", _config_attr("imap_ssl", True))

        def _as_bool(value: Optional[object]) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"1", "true", "yes", "on"}:
                    return True
                if lowered in {"0", "false", "no", "off"}:
                    return False
            return bool(value)

        use_ssl = _as_bool(use_ssl_value)
        mailbox = _config_attr("imap_mailbox", "INBOX") or "INBOX"

        if not (host and username and password):
            logger.debug("IMAP configuration incomplete; skipping fetch.")
            return []

        imap_factory: Callable[[str, int], imaplib.IMAP4] = (
            imaplib.IMAP4_SSL if use_ssl else imaplib.IMAP4
        )

        messages: list[InboxMessage] = []
        client: Optional[imaplib.IMAP4] = None

        try:
            client = imap_factory(host, port)
            client.login(username, password)
            status, _ = client.select(mailbox)
            if status != "OK":
                logger.warning("Unable to select mailbox %s", mailbox)
                return []

            status, search_data = client.search(None, "UNSEEN")
            if status != "OK" or not search_data:
                return []

            message_ids = search_data[0].split()

            for msg_id in message_ids:
                status, payload = client.fetch(msg_id, "(RFC822 UID)")
                if status != "OK" or not payload:
                    continue

                raw_email: Optional[bytes] = None
                response_header: Optional[bytes] = None
                for item in payload:
                    if isinstance(item, tuple) and len(item) >= 2:
                        response_header = item[0]
                        raw_email = item[1]
                        break

                if not raw_email:
                    continue

                message = message_from_bytes(raw_email)
                uid = None
                if isinstance(response_header, bytes):
                    uid_match = re.search(rb"UID\s+(\d+)", response_header)
                    if uid_match:
                        uid = uid_match.group(1).decode("ascii", errors="ignore")

                if not uid:
                    uid = msg_id.decode("ascii", errors="ignore")

                inbox_message = InboxMessage(
                    id=uid,
                    subject=self._decode_header_value(message.get("Subject")),
                    sender=self._parse_sender(message.get("From")),
                    body=self._extract_body(message),
                    headers=self._extract_headers(message),
                    received_at=self._parse_received_at(message),
                )

                messages.append(inbox_message)

                try:
                    client.store(msg_id, "+FLAGS", "(\\Seen)")
                except Exception:  # pragma: no cover - defensive best effort
                    logger.debug("Failed to mark message %s as seen", uid, exc_info=True)

        except imaplib.IMAP4.error:
            logger.exception("Failed to fetch IMAP messages from %s", host)
            return []
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:  # pragma: no cover - network cleanup best effort
                    logger.debug("Failed to logout from IMAP server", exc_info=True)

        return messages

    # ------------------------------------------------------------------
    @staticmethod
    def _decode_header_value(value: Optional[str]) -> str:
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:  # pragma: no cover - defensive
            return value

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_sender(value: Optional[str]) -> str:
        decoded = InboxAgent._decode_header_value(value)
        if not decoded:
            return ""
        name, address = parseaddr(decoded)
        return address or decoded

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_body(message: Message) -> str:
        if message.is_multipart():
            for part in message.walk():
                if part.is_multipart():
                    continue
                if part.get_content_disposition() == "attachment":
                    continue
                if part.get_content_type() == "text/plain":
                    text = InboxAgent._decode_payload(part)
                    if text:
                        return text
            # Fallback to first non-attachment part
            for part in message.walk():
                if part.is_multipart():
                    continue
                if part.get_content_disposition() == "attachment":
                    continue
                text = InboxAgent._decode_payload(part)
                if text:
                    return text
            return ""
        return InboxAgent._decode_payload(message)

    # ------------------------------------------------------------------
    @staticmethod
    def _decode_payload(part: Message) -> str:
        payload = part.get_payload(decode=True)
        if payload is None:
            if isinstance(part.get_payload(), str):
                return part.get_payload()
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return payload.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_headers(message: Message) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for key, value in message.items():
            headers[key] = InboxAgent._decode_header_value(value)
        return headers

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_received_at(message: Message) -> Optional[datetime]:
        date_header = message.get("Date")
        if not date_header:
            return None
        try:
            return parsedate_to_datetime(date_header)
        except (TypeError, ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    async def poll_once(self) -> int:
        """Fetch and dispatch messages once.

        Returns the number of dispatched messages.
        """

        if not self._is_configured():
            logger.info("Inbox agent disabled due to incomplete configuration.")
            return 0

        messages = await self.fetch_new_messages()
        dispatched = 0
        for message in messages:
            handled = await self._dispatch_message(message)
            if handled:
                dispatched += 1
        return dispatched

    # ------------------------------------------------------------------
    async def start_polling_loop(
        self, *, interval_seconds: Optional[float] = None
    ) -> None:
        """Continuously poll the inbox until cancelled.

        Parameters
        ----------
        interval_seconds:
            Optional override for the polling interval. When omitted, the
            instance's configured ``poll_interval`` is used.
        """

        try:
            while True:
                await self.poll_once()
                delay = self.poll_interval
                if interval_seconds is not None:
                    try:
                        delay = max(float(interval_seconds), 0.0)
                    except (TypeError, ValueError):
                        delay = self.poll_interval
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.info("Inbox polling loop cancelled.")
            raise

    # ------------------------------------------------------------------
    def _config_value(self, key: str) -> Optional[str]:
        if isinstance(self.config, Mapping):
            value = self.config.get(key)
        else:
            value = getattr(self.config, key, None)
        if value in {None, ""}:
            return None
        return str(value)

    # ------------------------------------------------------------------
    def _is_configured(self) -> bool:
        """Return whether IMAP configuration is available."""

        host = self._config_value("imap_host")
        user = self._config_value("imap_username") or self._config_value("imap_user")
        password = self._config_value("imap_password")
        return bool(host and user and password)


__all__ = [
    "InboxAgent",
    "InboxMessage",
    "AuditHandler",
    "parse_dossier_decision",
    "parse_missing_info_key_values",
]
