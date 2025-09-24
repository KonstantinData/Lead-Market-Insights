import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polling.polling_trigger import PollingTrigger


class DummyWorkflowLogManager:
    def __init__(self):
        self.logs = []

    def append_log(self, run_id, step, message, error=None):
        entry = {
            "run_id": run_id,
            "step": step,
            "message": message,
            "error": error,
        }
        self.logs.append(entry)
        print(f"WORKFLOW LOG: {entry}")


def successful_poll_logic():
    print("Polling logic executed (no error).")


def failing_poll_logic():
    print("Polling logic about to raise an error.")
    raise RuntimeError("Simulated polling error!")


def main():
    logging.basicConfig(level=logging.INFO)
    workflow_log_manager = DummyWorkflowLogManager()

    print(
        "\n--- Test 1: Start and Stop PollingTrigger with successful poll logic ---"
    )
    poller = PollingTrigger(
        poll_logic=successful_poll_logic,
        interval_seconds=2,
        workflow_log_manager=workflow_log_manager,
        run_id="test_run_success",
    )
    poller.start()
    time.sleep(5)  # Let it run for a couple of intervals
    poller.stop()
    assert not poller.is_running(), "Poller should be stopped."
    print("Test 1 passed.\n")

    print("\n--- Test 2: PollingTrigger catches and logs exceptions ---")
    poller = PollingTrigger(
        poll_logic=failing_poll_logic,
        interval_seconds=2,
        workflow_log_manager=workflow_log_manager,
        run_id="test_run_fail",
    )
    poller.start()
    time.sleep(3)  # Only one iteration needed to trigger error
    poller.stop()
    error_logs = [
        log for log in workflow_log_manager.logs if log["error"] is not None
    ]
    assert error_logs, "Should log errors from failing polling logic."
    print("Test 2 passed.\n")

    print("--- All tests completed successfully. ---")


if __name__ == "__main__":
    main()
