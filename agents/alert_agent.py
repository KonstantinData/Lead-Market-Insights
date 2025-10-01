"""Alert agent capable of dispatching workflow alerts to multiple channels."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from enum import Enum
from typing import Any, Callable, Coroutine, Iterable, List, Mapping, MutableMapping, Optional, Set

import requests


def _maybe_sign(payload: dict, secret: Optional[str]) -> Mapping[str, str]:
    if not secret:
        return {}
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {"X-Signature": f"sha256={sig}"}


class AlertSeverity(str, Enum):
    """Severity levels supported by :class:`AlertAgent`."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


AlertContext = MutableMapping[str, Any]
AlertDispatcher = Callable[[str, AlertSeverity, AlertContext], None]


class AlertAgent:
    """Dispatch workflow alerts to configured channels.

    Parameters
    ----------
    channels:
        Iterable of channel configuration dictionaries. Each configuration
        must provide a ``type`` key describing the transport (``email``,
        ``slack`` or ``webhook``). A custom ``dispatcher`` callable may also
        be supplied for advanced routing or for testing.
    logger:
        Optional logger instance. Defaults to a module level logger.
    """

    def __init__(
        self,
        channels: Optional[Iterable[MutableMapping[str, Any]]] = None,
        *,
        logger: Optional[logging.Logger] = None,
        task_scheduler: Optional[Callable[[asyncio.Task[Any]], asyncio.Task[Any]]] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._channels: List[MutableMapping[str, Any]] = []
        self._task_scheduler = task_scheduler
        self._pending_tasks: Set[asyncio.Task[Any]] = set()

        if channels:
            for channel in channels:
                self.add_channel(channel)

    def add_channel(self, channel: MutableMapping[str, Any]) -> None:
        """Register an alert delivery channel."""

        channel_type = channel.get("type")
        if channel_type not in {"email", "slack", "webhook"} and not channel.get(
            "dispatcher"
        ):
            raise ValueError(f"Unsupported alert channel type: {channel_type}")

        self._channels.append(channel)

    def send_alert(
        self,
        message: str,
        severity: AlertSeverity,
        *,
        context: Optional[AlertContext] = None,
    ) -> None:
        """Send an alert using all configured channels."""

        alert_context: AlertContext = {"severity": severity.value}
        if context:
            alert_context.update(context)

        for channel in self._channels:
            dispatcher: Optional[AlertDispatcher] = channel.get("dispatcher")
            try:
                if dispatcher:
                    dispatcher(message, severity, alert_context)
                else:
                    self._send_via_channel(channel, message, severity, alert_context)
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.error(
                    "Failed to send alert via channel %s: %s",
                    channel.get("name", channel.get("type", "unknown")),
                    exc,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _send_via_channel(
        self,
        channel: MutableMapping[str, Any],
        message: str,
        severity: AlertSeverity,
        context: AlertContext,
    ) -> None:
        channel_type = channel.get("type")

        if channel_type == "email":
            self._dispatch_email(channel, message, severity, context)
        elif channel_type == "slack":
            self._dispatch_slack(channel, message, severity, context)
        elif channel_type == "webhook":
            self._dispatch_webhook(channel, message, severity, context)
        else:
            raise ValueError(f"Unsupported alert channel type: {channel_type}")

    def _dispatch_email(
        self,
        channel: MutableMapping[str, Any],
        message: str,
        severity: AlertSeverity,
        context: AlertContext,
    ) -> None:
        client = channel.get("client")
        recipients = channel.get("recipients", [])
        if not client or not recipients:
            self.logger.warning("Email channel misconfigured: %s", channel)
            return

        subject_template = channel.get(
            "subject_template", "[{severity}] Agentic Intelligence alert"
        )
        body_template = channel.get(
            "body_template", "Severity: {severity}\nMessage: {message}\n"
        )
        format_kwargs = dict(context)
        format_kwargs["severity"] = severity.name
        format_kwargs.setdefault("severity_value", severity.value)
        format_kwargs["message"] = message
        subject = subject_template.format(**format_kwargs)
        body = body_template.format(**format_kwargs)

        for recipient in recipients:
            send_async = getattr(client, "send_email_async", None)
            if not callable(send_async):
                raise AttributeError(
                    "Email alert channel client must provide 'send_email_async'"
                )
            task = self._schedule_coroutine(send_async(recipient, subject, body))
            if task is None:
                self.logger.warning(
                    "Failed to schedule email alert delivery for %s", recipient
                )

    def _dispatch_slack(
        self,
        channel: MutableMapping[str, Any],
        message: str,
        severity: AlertSeverity,
        context: AlertContext,
    ) -> None:
        webhook_url = channel.get("webhook_url")
        if not webhook_url:
            self.logger.warning("Slack channel missing webhook URL: %s", channel)
            return

        payload = {
            "text": channel.get(
                "message_template",
                "[{severity}] {message}",
            ).format(
                **{
                    **dict(context),
                    "severity": severity.name,
                    "severity_value": severity.value,
                    "message": message,
                }
            ),
        }
        requests.post(webhook_url, json=payload, timeout=5)

    def _dispatch_webhook(
        self,
        channel: MutableMapping[str, Any],
        message: str,
        severity: AlertSeverity,
        context: AlertContext,
    ) -> None:
        url = channel.get("url")
        if not url:
            self.logger.warning("Webhook channel missing URL: %s", channel)
            return

        payload = {
            "message": message,
            "severity": severity.value,
            "context": dict(context),
        }
        extra_headers = _maybe_sign(payload, channel.get("signature_key"))
        headers = {
            **(channel.get("headers") or {"Content-Type": "application/json"}),
            **extra_headers,
        }
        requests.post(url, json=payload, headers=headers, timeout=5)

    # ------------------------------------------------------------------
    # Async helpers
    # ------------------------------------------------------------------
    def _schedule_coroutine(
        self, coro: Coroutine[Any, Any, Any]
    ) -> Optional[asyncio.Task[Any]]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.logger.error(
                "Cannot dispatch email alert; no running asyncio event loop available"
            )
            return None

        task = loop.create_task(coro)
        tracked = task
        if self._task_scheduler:
            try:
                scheduled = self._task_scheduler(task)
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.error("Alert task scheduler failed: %s", exc)
            else:
                if scheduled is not None:
                    tracked = scheduled

        self._pending_tasks.add(tracked)
        tracked.add_done_callback(self._pending_tasks.discard)
        return tracked
