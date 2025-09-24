import time
import logging


class PollingTrigger:
    """
    Module for polling and trigger logic.
    Replace the 'poll' method content with your custom logic (e.g., checking for new events).
    All exceptions are logged in the workflow log.
    """

    def __init__(self, interval_seconds=60, workflow_log_manager=None, run_id=None):
        self.interval_seconds = interval_seconds
        self.workflow_log_manager = workflow_log_manager
        self.run_id = run_id

    def poll(self):
        while True:
            try:
                # TODO: Insert polling/trigger logic here (e.g., new event detection)
                logging.info("Polling for new events...")
                time.sleep(self.interval_seconds)
            except Exception as e:
                logging.error(f"Error during polling: {e}")
                if self.workflow_log_manager and self.run_id:
                    self.workflow_log_manager.append_log(
                        self.run_id, "polling", "Error during polling", error=str(e)
                    )
