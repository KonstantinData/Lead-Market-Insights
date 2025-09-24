import logging
import sys
import threading
from typing import Callable, Optional

from config.config import settings
from agents.event_polling_agent import EventPollingAgent
from agents.trigger_detection_agent import TriggerDetectionAgent
from agents.extraction_agent import ExtractionAgent
from agents.human_in_loop_agent import HumanInLoopAgent
from agents.s3_storage_agent import S3StorageAgent

# Notes: Set up basic logging to both file and stdout
log_filename = "polling_trigger.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("PollingTrigger")


class PollingTrigger:
    """Run polling logic on a background thread at a fixed interval."""

    def __init__(
        self,
        poll_logic: Callable[[], None],
        interval_seconds: int,
        workflow_log_manager: Optional[object] = None,
        run_id: str = "default-run",
        shutdown_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._poll_logic = poll_logic
        self._interval_seconds = interval_seconds
        self._workflow_log_manager = workflow_log_manager
        self._run_id = run_id
        self._shutdown_callback = shutdown_callback

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _append_workflow_log(
        self, step: str, message: str, error: Optional[Exception] = None
    ) -> None:
        if not self._workflow_log_manager:
            return

        error_text = str(error) if error else None
        try:
            self._workflow_log_manager.append_log(
                run_id=self._run_id,
                step=step,
                message=message,
                error=error_text,
            )
        except Exception:  # pragma: no cover - logging should not break polling
            logger.exception("Workflow log manager failed to append a log entry.")

    def _run(self) -> None:
        logger.info("PollingTrigger thread started.")
        self._append_workflow_log("start", "Polling thread started")

        while not self._stop_event.is_set():
            try:
                self._poll_logic()
                self._append_workflow_log("poll", "Polling iteration completed")
            except Exception as exc:  # pragma: no cover - exercised in tests
                logger.exception("Polling logic raised an error.")
                self._append_workflow_log("poll", "Polling logic error", error=exc)

            if self._stop_event.wait(self._interval_seconds):
                break

        self._append_workflow_log("stop", "Polling thread stopped")
        logger.info("PollingTrigger thread stopped.")

        if self._shutdown_callback:
            try:
                self._shutdown_callback()
            except Exception:  # pragma: no cover - defensive cleanup
                logger.exception("Shutdown callback failed.")

    def start(self) -> None:
        """Start executing the polling logic on a background thread."""

        if self.is_running():
            logger.warning("PollingTrigger is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the polling thread to stop and wait for completion."""

        if not self._thread:
            return

        self._stop_event.set()
        self._thread.join()
        self._thread = None

    def is_running(self) -> bool:
        """Return ``True`` when the polling thread is active."""

        return self._thread is not None and self._thread.is_alive()


def main():
    # Notes: Initialize all agents with required configuration
    event_agent = EventPollingAgent(config=settings)
    trigger_agent = TriggerDetectionAgent(
        trigger_words=(
            settings.trigger_words.split(",") if settings.trigger_words else []
        )
    )
    extraction_agent = ExtractionAgent()
    human_agent = HumanInLoopAgent()

    # Notes: S3 agent is optional, only initialized if all config values are present
    s3_agent = None
    if all(
        [
            settings.aws_access_key_id,
            settings.aws_secret_access_key,
            settings.aws_default_region,
            settings.s3_bucket,
        ]
    ):
        s3_agent = S3StorageAgent(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_default_region,
            bucket_name=settings.s3_bucket,
            logger=logger,
        )

    logger.info("Polling workflow started.")

    for event in event_agent.poll():
        logger.info(f"Polled event: {event}")
        if trigger_agent.check(event):
            logger.info(f"Trigger detected in event {event.get('id')}")
            extracted = extraction_agent.extract(event)
            if not extracted["is_complete"]:
                logger.info(
                    f"Missing information detected for event {event.get('id')}, requesting human input."
                )
                filled = human_agent.request_info(event, extracted)
                logger.info(f"Finalized event info: {filled}")
            else:
                logger.info(
                    f"All required information extracted for event {event.get('id')}: {extracted}"
                )
        else:
            logger.info(f"No trigger detected for event {event.get('id')}")

    logger.info("Polling workflow finished.")

    # Notes: Upload the log file to S3 if agent is available
    if s3_agent:
        logger.info("Uploading log file to S3...")
        success = s3_agent.upload_file(log_filename, f"logs/{log_filename}")
        if success:
            logger.info("Log file uploaded successfully.")
        else:
            logger.warning("Log file upload failed.")
    else:
        logger.warning("S3 agent not configured. Skipping log upload.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Polling workflow failed: {e}", exc_info=True)
