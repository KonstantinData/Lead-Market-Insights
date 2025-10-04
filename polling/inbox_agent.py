"""IMAP inbox polling agent used for manual review workflows."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
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

        raise NotImplementedError

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
