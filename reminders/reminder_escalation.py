import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Set


class ReminderEscalation:
    """Module for sending reminders and escalation notifications."""

    def __init__(
        self,
        email_agent,
        workflow_log_manager=None,
        run_id=None,
        *,
        task_scheduler: Optional[
            Callable[[asyncio.Task[Any]], asyncio.Task[Any]]
        ] = None,
        hitl_dir: Optional[Path] = None,
    ):
        self.email_agent = email_agent
        self.workflow_log_manager = workflow_log_manager
        self.run_id = run_id
        self._task_scheduler = task_scheduler
        self._tasks: Set[asyncio.Task[Any]] = set()
        self._audit_tasks: Dict[str, Set[asyncio.Task[Any]]] = {}
        self.hitl_dir: Optional[Path] = Path(hitl_dir) if hitl_dir else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def send_reminder(
        self,
        recipient,
        subject,
        body,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self.email_agent:
            self._append_log(
                "reminder_skipped",
                f"Reminder not sent (email agent unavailable) for {recipient}",
                metadata=metadata,
                error="email_agent_missing",
            )
            return False

        try:
            send_email = getattr(self.email_agent, "send_email_async", None)
            if not callable(send_email):
                raise AttributeError("email_agent must expose 'send_email_async'")
            sent = await send_email(recipient, subject, body)
            step = "reminder_sent" if sent else "reminder_failed"
            error = None if sent else "send_failed"
            self._append_log(
                step,
                f"Reminder {'sent' if sent else 'failed'} to {recipient}: {subject}",
                metadata=metadata,
                error=error,
            )
            return bool(sent)
        except Exception as exc:  # pragma: no cover - defensive logging
            logging.error("Error sending reminder: %s", exc)
            self._append_log(
                "reminder_exception",
                f"Exception during reminder to {recipient}: {exc}",
                metadata=metadata,
                error=str(exc),
            )
            raise

    async def escalate(
        self,
        admin_email,
        subject,
        body,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self.email_agent:
            self._append_log(
                "escalation_skipped",
                f"Escalation not sent (email agent unavailable) for {admin_email}",
                metadata=metadata,
                error="email_agent_missing",
            )
            return False

        try:
            send_email = getattr(self.email_agent, "send_email_async", None)
            if not callable(send_email):
                raise AttributeError("email_agent must expose 'send_email_async'")
            sent = await send_email(admin_email, subject, body)
            step = "escalation_sent" if sent else "escalation_failed"
            error = None if sent else "send_failed"
            self._append_log(
                step,
                f"Escalation {'sent' if sent else 'failed'} to {admin_email}: {subject}",
                metadata=metadata,
                error=error,
            )
            return bool(sent)
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
    ) -> asyncio.Task[bool]:
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
    ) -> asyncio.Task[bool]:
        return self._schedule_action(
            "escalation",
            lambda: self.escalate(admin_email, subject, body, metadata=metadata),
            delay_seconds,
            admin_email,
            subject,
            metadata,
        )

    def schedule_admin_recurring_reminders(
        self,
        admin_email: str,
        subject: str,
        body: str,
        interval_hours: float,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> asyncio.Task[None]:
        interval_seconds = max(float(interval_hours), 0.0) * 3600.0
        if interval_seconds <= 0:
            raise ValueError("interval_hours must be greater than 0 for recurring reminders")

        metadata = dict(metadata or {})
        due_time = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
        self._append_log(
            "admin_recurring_reminder_scheduled",
            (
                "Recurring admin reminder scheduled for "
                f"{admin_email} starting at {due_time.isoformat()} ({subject})"
            ),
            metadata=metadata,
        )

        async def _recurring() -> None:
            try:
                while True:
                    await asyncio.sleep(interval_seconds)
                    await self.send_reminder(
                        admin_email,
                        subject,
                        body,
                        metadata=metadata,
                    )
            except asyncio.CancelledError:
                raise

        audit_id = metadata.get("audit_id") if metadata else None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError(
                "ReminderEscalation scheduling requires an active asyncio event loop"
            ) from exc

        task = loop.create_task(_recurring())
        tracked = self._register_task(task, audit_id=audit_id)
        return tracked

    def cancel_pending(self) -> None:
        tasks = list(self._tasks)
        self._tasks.clear()
        self._audit_tasks.clear()
        for task in tasks:
            task.cancel()

    def cancel_for_audit(self, audit_id: str) -> None:
        """Cancel reminders associated with *audit_id*."""

        tasks = self._audit_tasks.pop(audit_id, set())
        if not tasks:
            return

        for task in list(tasks):
            task.cancel()
            self._tasks.discard(task)

    # ------------------------------------------------------------------
    # HITL reminder scheduling helpers
    # ------------------------------------------------------------------
    def schedule(self, operator_email: str, run_id: str) -> None:
        """Schedule an immediate HITL reminder and update run state on success."""

        if not self.hitl_dir:
            raise RuntimeError(
                "ReminderEscalation requires 'hitl_dir' to schedule HITL reminders"
            )

        path = self._hitl_state_path(run_id)
        try:
            state = json.loads(path.read_text())
        except FileNotFoundError:
            logging.warning("HITL state missing for run %s; reminder skipped", run_id)
            return
        except json.JSONDecodeError as exc:
            logging.error("Invalid HITL state for run %s: %s", run_id, exc)
            return

        if state.get("status") != "pending":
            return

        subject = self._build_subject(run_id, state)
        body = self._build_body(run_id, state)
        metadata = {
            "run_id": run_id,
            "workflow_step": "hitl_followup",
        }

        task = self.schedule_reminder(
            operator_email,
            subject,
            body,
            0,
            metadata=metadata,
        )

        def _after(task_result: asyncio.Task[bool]) -> None:
            try:
                sent = task_result.result()
            except Exception:  # pragma: no cover - defensive logging
                logging.exception("HITL reminder task failed for run %s", run_id)
                return
            if sent:
                self._increment_reminder_count(run_id)

        task.add_done_callback(_after)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _schedule_action(
        self,
        action: str,
        sender: Callable[[], Awaitable[bool]],
        delay_seconds: float,
        recipient: str,
        subject: str,
        metadata: Optional[Dict[str, Any]],
    ) -> asyncio.Task[bool]:
        metadata = dict(metadata or {})
        due_time = datetime.now(timezone.utc) + timedelta(seconds=max(delay_seconds, 0))
        self._append_log(
            f"{action}_scheduled",
            f"{action.capitalize()} scheduled for {recipient} at {due_time.isoformat()} ({subject})",
            metadata=metadata,
        )

        async def _execute() -> bool:
            try:
                await asyncio.sleep(max(delay_seconds, 0))
                return await sender()
            except Exception as exc:  # pragma: no cover - defensive logging
                logging.error("Scheduled %s failed for %s: %s", action, recipient, exc)
                raise

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError(
                "ReminderEscalation scheduling requires an active asyncio event loop"
            ) from exc

        task = loop.create_task(_execute())
        tracked = self._register_task(
            task,
            audit_id=metadata.get("audit_id") if metadata else None,
        )
        return tracked

    def _register_task(
        self,
        task: asyncio.Task[Any],
        *,
        audit_id: Optional[str] = None,
    ) -> asyncio.Task[Any]:
        tracked = task
        if self._task_scheduler:
            try:
                scheduled = self._task_scheduler(task)
            except Exception as exc:  # pragma: no cover - defensive logging
                logging.error("Task scheduler failed: %s", exc)
            else:
                if scheduled is not None:
                    tracked = scheduled

        self._tasks.add(tracked)

        def _remove_from_tasks(completed: asyncio.Task[Any]) -> None:
            self._tasks.discard(completed)

        tracked.add_done_callback(_remove_from_tasks)

        normalized_audit_id: Optional[str] = None
        if audit_id:
            text_id = str(audit_id)
            if text_id.lower() != "n/a":
                normalized_audit_id = text_id

        if normalized_audit_id:
            audit_tasks = self._audit_tasks.setdefault(normalized_audit_id, set())
            audit_tasks.add(tracked)

            def _remove_from_audit(completed: asyncio.Task[Any]) -> None:
                tasks = self._audit_tasks.get(normalized_audit_id)
                if not tasks:
                    return
                tasks.discard(completed)
                if not tasks:
                    self._audit_tasks.pop(normalized_audit_id, None)

            tracked.add_done_callback(_remove_from_audit)
        return tracked

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

    # ------------------------------------------------------------------
    # HITL helper utilities
    # ------------------------------------------------------------------
    def _hitl_state_path(self, run_id: str) -> Path:
        if not self.hitl_dir:
            raise RuntimeError("hitl_dir is not configured for ReminderEscalation")
        return Path(self.hitl_dir) / f"{run_id}_hitl.json"

    def _increment_reminder_count(self, run_id: str) -> None:
        path = self._hitl_state_path(run_id)
        try:
            state = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return
        if state.get("status") != "pending":
            return
        count = state.get("reminders_sent") or 0
        try:
            count_int = int(count)
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            count_int = 0
        state["reminders_sent"] = count_int + 1
        state["last_reminder_at"] = datetime.now(timezone.utc).isoformat()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        tmp.replace(path)

    def _build_subject(self, run_id: str, state: Dict[str, Any]) -> str:
        return f"HITL Reminder · {run_id}"

    def _build_body(self, run_id: str, state: Dict[str, Any]) -> str:
        context = state.get("context") or {}
        company = (
            context.get("company_name")
            or context.get("company")
            or context.get("company_domain")
            or "the company"
        )
        lines = [
            "Hello,",
            "",
            f"This is a reminder regarding the pending HITL request for {company}.",
            f"Run ID: {run_id}",
        ]
        missing = context.get("missing_fields")
        if missing:
            if isinstance(missing, (list, tuple, set)):
                missing_text = ", ".join(str(item) for item in missing)
            else:
                missing_text = str(missing)
            lines.extend(["", f"Missing fields: {missing_text}"])
        lines.extend(
            [
                "",
                "Please reply with APPROVE, DECLINE, or CHANGE instructions.",
                "Thank you!",
            ]
        )
        return "\n".join(lines)
