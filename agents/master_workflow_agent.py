"""
MasterWorkflowAgent: Pure logic agent for polling and event-processing.

# Notes:
# - This agent contains only the polling, trigger detection, extraction, human-in-the-loop, and CRM logic.
# - It exposes process_all_events(), but does NOT handle orchestration, status, or logging setup.
# - All business logic is encapsulated here, orchestration is handled in WorkflowOrchestrator.
"""

import logging
from typing import Dict, Any

from agents.event_polling_agent import EventPollingAgent
from agents.trigger_detection_agent import TriggerDetectionAgent
from agents.extraction_agent import ExtractionAgent
from agents.human_in_loop_agent import HumanInLoopAgent
from agents.s3_storage_agent import S3StorageAgent
from config.config import settings
from utils.trigger_loader import load_trigger_words

from pathlib import Path

logger = logging.getLogger("MasterWorkflowAgent")


class MasterWorkflowAgent:
    def __init__(self) -> None:
        # Initialize configuration and all agents.
        self.event_agent = EventPollingAgent(config=settings)
        trigger_words_file = (
            Path(__file__).resolve().parents[1] / "config" / "trigger_words.txt"
        )
        self.trigger_words = load_trigger_words(
            settings.trigger_words, triggers_file=trigger_words_file, logger=logger
        )
        self.trigger_agent = TriggerDetectionAgent(trigger_words=self.trigger_words)
        self.extraction_agent = ExtractionAgent()
        self.human_agent = HumanInLoopAgent()

        # S3 agent setup (optional)
        self.s3_agent = None
        if all(
            [
                settings.aws_access_key_id,
                settings.aws_secret_access_key,
                settings.aws_default_region,
                settings.s3_bucket,
            ]
        ):
            self.s3_agent = S3StorageAgent(
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_default_region,
                bucket_name=settings.s3_bucket,
                logger=logger,
            )
        self.log_filename = "polling_trigger.log"

    def process_all_events(self) -> None:
        """
        Loops through all events, applies trigger detection, extraction, HITL, and CRM logic.
        Decision tree follows the requirements (hard/soft trigger, info completeness, etc).
        """
        logger.info("MasterWorkflowAgent: Processing events...")

        for event in self.event_agent.poll():
            logger.info(f"Polled event: {event}")
            event_id = event.get("id")

            # Step 1: Trigger detection (check both summary and description, hard/soft)
            trigger_result = self._detect_trigger(event)
            if not trigger_result["trigger"]:
                logger.info(f"No trigger detected for event {event_id}")
                continue

            logger.info(
                f"{trigger_result['type'].capitalize()} trigger detected in event {event_id} "
                f"(matched: {trigger_result['matched_word']} in {trigger_result['matched_field']})"
            )

            # Step 2: Extraction of required info (company_name, web_domain)
            extracted = self.extraction_agent.extract(event)
            info = extracted.get("info", {})
            is_complete = extracted.get("is_complete", False)

            # Step 3: Decide actions based on trigger type and info completeness
            if trigger_result["type"] == "hard" and is_complete:
                self._send_to_crm_agent(event, info)
            elif trigger_result["type"] == "soft" and is_complete:
                # Human-in-the-loop: Ask organizer if dossier is needed
                response = self.human_agent.request_dossier_confirmation(event, info)
                if response.get("dossier_required"):
                    self._send_to_crm_agent(event, info)
                else:
                    logger.info(f"Organizer declined dossier for event {event_id}.")
            elif trigger_result["type"] == "hard" and not is_complete:
                # Human-in-the-loop: Ask for missing company_name/web_domain
                filled = self.human_agent.request_info(event, extracted)
                if filled.get("is_complete"):
                    self._send_to_crm_agent(event, filled.get("info", {}))
                else:
                    logger.warning(f"Required info still missing for event {event_id}.")
            elif trigger_result["type"] == "soft" and not is_complete:
                # Human-in-the-loop: First ask organizer, then ask for missing info if needed
                response = self.human_agent.request_dossier_confirmation(event, info)
                if response.get("dossier_required"):
                    filled = self.human_agent.request_info(event, extracted)
                    if filled.get("is_complete"):
                        self._send_to_crm_agent(event, filled.get("info", {}))
                    else:
                        logger.warning(
                            f"Required info still missing after HITL for event {event_id}."
                        )
                else:
                    logger.info(f"Organizer declined dossier for event {event_id}.")
            else:
                logger.warning(f"Unhandled trigger/info state for event {event_id}")

    def _detect_trigger(self, event: Dict[str, Any]) -> Dict[str, Any]:
        # Delegates to trigger agent, checks both summary and description
        return self.trigger_agent.check(event)

    def _send_to_crm_agent(self, event: Dict[str, Any], info: Dict[str, Any]) -> None:
        # TODO: Replace with real CRM agent logic
        logger.info(f"Sending event {event.get('id')} to CRM with info: {info}")

    def upload_log_to_s3(self) -> None:
        if self.s3_agent:
            success = self.s3_agent.upload_file(
                self.log_filename, f"logs/{self.log_filename}"
            )
            if success:
                logger.info(f"Log file uploaded to S3: {self.log_filename}")
            else:
                logger.warning("Log file upload to S3 failed.")
        else:
            logger.warning("S3 agent not configured. Skipping log upload.")
