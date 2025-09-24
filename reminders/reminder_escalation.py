import logging


class ReminderEscalation:
    """
    Module for sending reminders and escalation notifications.
    """

    def __init__(self, email_agent, workflow_log_manager=None, run_id=None):
        self.email_agent = email_agent
        self.workflow_log_manager = workflow_log_manager
        self.run_id = run_id

    def send_reminder(self, recipient, subject, body):
        try:
            sent = self.email_agent.send_email(recipient, subject, body)
            if not sent and self.workflow_log_manager and self.run_id:
                self.workflow_log_manager.append_log(
                    self.run_id,
                    "reminder",
                    "Failed to send reminder email",
                    error="Send failed",
                )
            return sent
        except Exception as e:
            logging.error(f"Error sending reminder: {e}")
            if self.workflow_log_manager and self.run_id:
                self.workflow_log_manager.append_log(
                    self.run_id, "reminder", "Exception during reminder",
                    error=str(e)
                )
            raise

    def escalate(self, admin_email, subject, body):
        try:
            sent = self.email_agent.send_email(admin_email, subject, body)
            if not sent and self.workflow_log_manager and self.run_id:
                self.workflow_log_manager.append_log(
                    self.run_id,
                    "escalation",
                    "Failed to send escalation email",
                    error="Send failed",
                )
            return sent
        except Exception as e:
            logging.error(f"Error sending escalation: {e}")
            if self.workflow_log_manager and self.run_id:
                self.workflow_log_manager.append_log(
                    self.run_id,
                    "escalation",
                    "Exception during escalation",
                    error=str(e),
                )
            raise
