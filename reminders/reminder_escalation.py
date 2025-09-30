import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from utils.datetime_formatting import format_report_datetime


class ReminderEscalation:
    """Module for sending reminders and escalation notifications."""

    def __init__(self, email_agent, workflow_log_manager=None, run_id=None):
        self.email_agent = email_agent
        self.workflow_log_manager = workflow_log_manager
        self.run_id = run_id
        self._timers: List[threading.Timer] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def send_reminder(self, recipient, subject, body, *, metadata: Optional[Dict[str, Any]] = None):
        if not self.email_agent:
            self._append_log(
                "reminder_skipped",
                f"Reminder not sent (email agent unavailable) for {recipient}",
                metadata=metadata,
                error="email_agent_missing",
            )
            return False

        try:
            sent = self.email_agent.send_email(recipient, subject, body)
            step = "reminder_sent" if sent else "reminder_failed"
            error = None if sent else "send_failed"
            self._append_log(
                step,
                f"Reminder {'sent' if sent else 'failed'} to {recipient}: {subject}",
                metadata=metadata,
                error=error,
            )
            return sent
        except Exception as exc:  # pragma: no cover - defensive logging
            logging.error("Error sending reminder: %s", exc)
            self._append_log(
                "reminder_exception",
                f"Exception during reminder to {recipient}: {exc}",
                metadata=metadata,
                error=str(exc),
            )
            raise

    def escalate(
        self,
        admin_email,
        subject,
        body,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self.email_agent:
            self._append_log(
                "escalation_skipped",
                f"Escalation not sent (email agent unavailable) for {admin_email}",
                metadata=metadata,
                error="email_agent_missing",
            )
            return False

        try:
            sent = self.email_agent.send_email(admin_email, subject, body)
            step = "escalation_sent" if sent else "escalation_failed"
            error = None if sent else "send_failed"
            self._append_log(
                step,
                f"Escalation {'sent' if sent else 'failed'} to {admin_email}: {subject}",
                metadata=metadata,
                error=error,
            )
            return sent
        except Exception as exc:  # pragma: no cover - defensive logging
            logging.error("Error sending escalation: %s", exc)
            self._append_log(
                "escalation_exception",
                f"Exception during escalation to {admin_email}: {exc}",
                metadata=metadata,
                error=str(exc),
            )
            raise

    def schedule_reminder(
        self,
        recipient: str,
        subject: str,
        body: str,
        delay_seconds: float,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> threading.Timer:
        return self._schedule_action(
            "reminder",
            lambda: self.send_reminder(recipient, subject, body, metadata=metadata),
            delay_seconds,
            recipient,
            subject,
            metadata,
        )

    def schedule_escalation(
        self,
        admin_email: str,
        subject: str,
        body: str,
        delay_seconds: float,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> threading.Timer:
        return self._schedule_action(
            "escalation",
            lambda: self.escalate(admin_email, subject, body, metadata=metadata),
            delay_seconds,
            admin_email,
            subject,
            metadata,
        )

    def cancel_pending(self) -> None:
        with self._lock:
            timers = list(self._timers)
            self._timers.clear()
        for timer in timers:
            timer.cancel()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _schedule_action(
        self,
        action: str,
        sender: Callable[[], Any],
        delay_seconds: float,
        recipient: str,
        subject: str,
        metadata: Optional[Dict[str, Any]],
    ) -> threading.Timer:
        metadata = dict(metadata or {})
        due_time = datetime.now(timezone.utc) + timedelta(seconds=max(delay_seconds, 0))
        self._append_log(
            f"{action}_scheduled",
            f"{action.capitalize()} scheduled for {recipient} at {format_report_datetime(due_time)} ({subject})",
            metadata=metadata,
        )

        def _execute() -> None:
            try:
                sender()
            finally:
                self._unregister_timer(timer)

        timer = threading.Timer(max(delay_seconds, 0), _execute)
        timer.daemon = True
        self._register_timer(timer)
        timer.start()
        return timer

    def _register_timer(self, timer: threading.Timer) -> None:
        with self._lock:
            self._timers.append(timer)

    def _unregister_timer(self, timer: threading.Timer) -> None:
        with self._lock:
            if timer in self._timers:
                self._timers.remove(timer)

    def _append_log(
        self,
        step: str,
        message: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        if not (self.workflow_log_manager and self.run_id):
            return

        workflow_step = None
        if metadata is not None and "workflow_step" in metadata:
            workflow_step = metadata.get("workflow_step")
            metadata = dict(metadata)
            metadata.pop("workflow_step", None)
        suffix = self._format_metadata(metadata)
        step_name = step
        if workflow_step:
            step_name = f"{workflow_step}_{step}"
        self.workflow_log_manager.append_log(
            self.run_id,
            step_name,
            f"{message}{suffix}",
            error=error,
        )

    def _format_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        if not metadata:
            return ""
        formatted = []
        for key, value in metadata.items():
            if value is None:
                continue
            formatted.append(f"{key}={value}")
        if not formatted:
            return ""
        return " [" + ", ".join(formatted) + "]"
