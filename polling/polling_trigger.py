import time
import logging
import threading
import signal
from typing import Callable, Optional


class PollingTrigger:
    """
    Live-capable polling and trigger module.
    Supports interval-based polling with graceful shutdown, logging, and custom polling logic.
    """

    def __init__(
        self,
        poll_logic: Callable[[], None],
        interval_seconds: int = 60,
        workflow_log_manager=None,
        run_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        :param poll_logic: Function to execute each polling interval.
        :param interval_seconds: Seconds between polling runs.
        :param workflow_log_manager: Optional, for workflow logging (to S3 etc.).
        :param run_id: Optional, workflow run identifier.
        :param logger: Optional, custom logger instance.
        """
        self.poll_logic = poll_logic
        self.interval_seconds = interval_seconds
        self.workflow_log_manager = workflow_log_manager
        self.run_id = run_id
        self.logger = logger or logging.getLogger("PollingTrigger")
        self._running = False
        self._thread = None

    def _log(self, msg, level=logging.INFO):
        if self.logger:
            self.logger.log(level, msg)
        if self.workflow_log_manager and self.run_id:
            self.workflow_log_manager.append_log(self.run_id, "polling", msg)

    def _polling_loop(self):
        self._log("PollingTrigger started.")
        while self._running:
            try:
                self.poll_logic()
                self._log("Polling iteration complete.")
            except Exception as e:
                err_msg = f"Error during polling: {e}"
                self._log(err_msg, level=logging.ERROR)
                if self.workflow_log_manager and self.run_id:
                    self.workflow_log_manager.append_log(
                        self.run_id, "polling", "Error during polling", error=str(e)
                    )
            time.sleep(self.interval_seconds)
        self._log("PollingTrigger stopped.")

    def start(self):
        if self._running:
            self._log("PollingTrigger already running.", level=logging.WARNING)
            return
        self._running = True
        self._thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._thread.start()

        # Setup signal handlers for graceful shutdown if running in main thread
        try:
            signal.signal(signal.SIGTERM, self.stop)
            signal.signal(signal.SIGINT, self.stop)
        except Exception:
            pass  # Might not be supported in all environments

    def stop(self, signum=None, frame=None):
        if not self._running:
            return
        self._log("Stopping PollingTrigger...", level=logging.INFO)
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def is_running(self):
        return self._running

    def wait(self):
        """Block until the polling thread finishes"""
        if self._thread:
            self._thread.join()


# Example usage:
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def my_poll_logic():
        # Insert actual polling logic here, e.g. check for new events
        print("Polling for new events...")

    # Optionally provide workflow_log_manager and run_id here
    poller = PollingTrigger(poll_logic=my_poll_logic, interval_seconds=10)
    poller.start()
    try:
        while poller.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        poller.stop()
