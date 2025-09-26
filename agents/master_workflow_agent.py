"""
MasterWorkflowAgent: Pure logic agent for polling and event-processing.

# Notes:
# - This agent contains only the polling, trigger detection, extraction, human-in-the-loop, and CRM logic.
# - It exposes process_all_events(), but does NOT handle orchestration, status, or logging setup.
# - All business logic is encapsulated here, orchestration is handled in WorkflowOrchestrator.
"""

import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agents.event_polling_agent import EventPollingAgent
from agents.trigger_detection_agent import TriggerDetectionAgent
from agents.extraction_agent import ExtractionAgent
from agents.human_in_loop_agent import HumanInLoopAgent
from agents.local_storage_agent import LocalStorageAgent
from config.config import settings
from utils.trigger_loader import load_trigger_words

logger = logging.getLogger("MasterWorkflowAgent")


class MasterWorkflowAgent:
    def __init__(
        self,
        communication_backend: Optional[Any] = None,
        event_agent: Optional[EventPollingAgent] = None,
        trigger_agent: Optional[TriggerDetectionAgent] = None,
        extraction_agent: Optional[ExtractionAgent] = None,
    ) -> None:
        # Initialize configuration and all agents.
        self.event_agent = event_agent or EventPollingAgent(config=settings)
        trigger_words_file = (
            Path(__file__).resolve().parents[1] / "config" / "trigger_words.txt"
        )
        self.trigger_words = load_trigger_words(
            settings.trigger_words, triggers_file=trigger_words_file, logger=logger
        )
        self.trigger_agent = trigger_agent or TriggerDetectionAgent(
            trigger_words=self.trigger_words
        )
        self.extraction_agent = extraction_agent or ExtractionAgent()
        self.human_agent = HumanInLoopAgent(communication_backend=communication_backend)

        # Local storage for log artefacts
        self.storage_agent = LocalStorageAgent(settings.run_log_dir, logger=logger)

        # Use a unique log directory per run using current UTC timestamp
        self.run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        self.run_directory = self.storage_agent.create_run_directory(self.run_id)
        self.log_file_path = self.run_directory / "polling_trigger.log"
        self.log_filename = str(self.log_file_path)

        # Configure logger to write to the unique per-run file
        file_handler = logging.FileHandler(
            self.log_file_path, mode="w", encoding="utf-8"
        )
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

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
                    logger.info(
                        "Organizer approved dossier for event %s: %s",
                        event_id,
                        response.get("details"),
                    )
                    self._send_to_crm_agent(event, info)
                else:
                    logger.info(
                        "Organizer declined dossier for event %s: %s",
                        event_id,
                        response.get("details"),
                    )
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
                    logger.info(
                        "Organizer approved dossier for event %s: %s",
                        event_id,
                        response.get("details"),
                    )
                    filled = self.human_agent.request_info(event, extracted)
                    if filled.get("is_complete"):
                        self._send_to_crm_agent(event, filled.get("info", {}))
                    else:
                        logger.warning(
                            f"Required info still missing after HITL for event {event_id}."
                        )
                else:
                    logger.info(
                        "Organizer declined dossier for event %s: %s",
                        event_id,
                        response.get("details"),
                    )
            else:
                logger.warning(f"Unhandled trigger/info state for event {event_id}")

    def _detect_trigger(self, event: Dict[str, Any]) -> Dict[str, Any]:
        # Delegates to trigger agent, checks both summary and description
        return self.trigger_agent.check(event)

    def _send_to_crm_agent(self, event: Dict[str, Any], info: Dict[str, Any]) -> None:
        # TODO: Replace with real CRM agent logic
        logger.info(f"Sending event {event.get('id')} to CRM with info: {info}")

    def finalize_run_logs(self) -> None:
        """Persist metadata about the generated log file to local storage."""

        log_size = 0
        if self.log_file_path.exists():
            log_size = self.log_file_path.stat().st_size

        self.storage_agent.record_run(
            self.run_id,
            self.log_file_path,
            metadata={"log_size_bytes": log_size},
        )
