import logging
import sys

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
