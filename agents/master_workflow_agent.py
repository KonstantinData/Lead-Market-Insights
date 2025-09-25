"""
MasterWorkflowAgent: Central agent orchestrating the entire polling and event-processing workflow.

# Notes:
# - This agent is responsible for supervising the full Google Calendar polling, trigger detection,
#   extraction, human-in-the-loop, and logging/upload process.
# - It coordinates all sub-agents and manages the full decision tree as described in the requirements.
# - All processing logic, including hard/soft trigger matching, info extraction, HITL, and S3 upload,
#   is encapsulated here.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from agents.event_polling_agent import EventPollingAgent
from agents.trigger_detection_agent import TriggerDetectionAgent
from agents.extraction_agent import ExtractionAgent
from agents.human_in_loop_agent import HumanInLoopAgent
from agents.s3_storage_agent import S3StorageAgent
from config.config import settings
from utils.trigger_loader import load_trigger_words

import logging
from pathlib import Path

# Notes: Set up logging (could be further parameterized)
logger = logging.getLogger("MasterWorkflowAgent")


class MasterWorkflowAgent:
    """
    # Notes:
    # - Orchestrates all sub-agents and the full business logic.
    # - Implements the full workflow as a single entrypoint for polling and event handling.
    """

    def __init__(self) -> None:
        # Notes: Initialize configuration and all agents.
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

        # Notes: S3 agent setup (optional: only if all credentials are present)
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

    def run_workflow(self) -> None:
        """
        # Notes:
        # - Main entry for running the polling and processing workflow.
        # - Loops through all events, applies trigger detection, extraction, HITL, and logging.
        # - Decision tree follows the requirements (hard/soft trigger, info completeness, etc).
        """
        logger.info("Master workflow started.")

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
                    self._send_to_crm_agent(event, filled["info"])
                else:
                    logger.warning(
                        f"Event {event_id} missing required info after HITL, skipping."
                    )
            elif trigger_result["type"] == "soft" and not is_complete:
                # Human-in-the-loop: Ask if dossier needed, and for missing info
                response = self.human_agent.request_dossier_and_info(event, extracted)
                if response.get("dossier_required") and response.get("is_complete"):
                    self._send_to_crm_agent(event, response["info"])
                else:
                    logger.info(
                        f"Soft trigger event {event_id} did not result in CRM action."
                    )
            else:
                logger.info(
                    f"Unhandled event type for event {event_id} (should not occur)."
                )

        logger.info("Master workflow finished.")
        self._upload_log_to_s3()

    def _detect_trigger(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        # Notes:
        # - Checks both summary and description for hard or soft trigger matches.
        # - Returns a dict reporting trigger status, type, matched word, and field.
        """
        summary = event.get("summary", "")
        description = event.get("description", "")

        # Notes: Hard trigger (exact match, normalized)
        for field_name, value in [("summary", summary), ("description", description)]:
            if self.trigger_agent.check({field_name: value}):
                return {
                    "trigger": True,
                    "type": "hard",
                    "matched_word": self._find_matched_word(value),
                    "matched_field": field_name,
                }

        # Notes: Soft trigger placeholder (to be replaced by fuzzy/NLP logic)
        # For now, this always returns False until soft matching is implemented.
        # If you implement soft matching, set type="soft" and provide the best match.
        return {
            "trigger": False,
            "type": None,
            "matched_word": None,
            "matched_field": None,
        }

    def _find_matched_word(self, text: str) -> Optional[str]:
        """
        # Notes:
        # - Returns the first trigger word (normalized) found in the given text.
        # - Used for logging and audit purposes.
        """
        from utils.text_normalization import normalize_text

        norm_text = normalize_text(text)
        for word in self.trigger_agent.trigger_words:
            if word in norm_text:
                return word
        return None

    def _send_to_crm_agent(self, event: Dict[str, Any], info: Dict[str, Any]) -> None:
        """
        # Notes:
        # - Placeholder for CRM integration logic.
        # - This should send event and info to the CRM agent/system.
        # - Currently logs the action.
        """
        logger.info(f"Sending event {event.get('id')} with info {info} to CRM agent.")
        # TODO: Implement actual CRM integration here.

    def _upload_log_to_s3(self) -> None:
        """
        # Notes:
        # - Uploads the workflow log file to S3 if S3 agent is configured.
        # - Logs the result.
        """
        if not self.s3_agent:
            logger.warning("S3 agent not configured. Skipping log upload.")
            return
        success = self.s3_agent.upload_file(
            self.log_filename, f"logs/{self.log_filename}"
        )
        if success:
            logger.info("Log file uploaded successfully.")
        else:
            logger.warning("Log file upload failed.")
