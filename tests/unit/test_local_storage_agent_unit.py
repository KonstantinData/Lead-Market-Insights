import json
from unittest.mock import MagicMock

import pytest

from agents.local_storage_agent import LocalStorageAgent


@pytest.fixture
def storage_agent(tmp_path):
    agent = LocalStorageAgent(tmp_path)
    agent.logger = MagicMock()
    return agent


def test_load_audit_entries_returns_empty_when_missing(storage_agent):
    assert storage_agent.load_audit_entries("missing-run") == []


def test_load_audit_entries_skips_invalid_lines(storage_agent, tmp_path):
    audit_path = storage_agent.get_audit_log_path("run-1")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        "\n".join(
            [
                json.dumps({"id": 1}),
                "not-json",
                json.dumps({"id": 2}),
            ]
        ),
        encoding="utf-8",
    )

    entries = storage_agent.load_audit_entries("run-1")

    assert entries == [{"id": 1}, {"id": 2}]
    storage_agent.logger.warning.assert_called_once()


def test_record_run_writes_relative_path(storage_agent, tmp_path):
    run_dir = storage_agent.create_run_directory("run-1")
    log_path = run_dir / "audit_log.jsonl"
    log_path.write_text("{}", encoding="utf-8")

    storage_agent.record_run("run-1", log_path, metadata={"status": "ok"})

    index = json.loads(storage_agent._index_file.read_text(encoding="utf-8"))
    assert index[-1]["log_path"] == f"run-1/{log_path.name}"
    assert index[-1]["status"] == "ok"


def test_record_run_recovers_from_invalid_index(storage_agent, tmp_path_factory):
    storage_agent._index_file.write_text("not-json", encoding="utf-8")
    outside_dir = tmp_path_factory.mktemp("external")
    outside_log = outside_dir / "external.log"
    outside_log.write_text("{}", encoding="utf-8")

    storage_agent.record_run("run-2", outside_log)

    index = json.loads(storage_agent._index_file.read_text(encoding="utf-8"))
    assert index[-1]["log_path"] == outside_log.as_posix()
    storage_agent.logger.warning.assert_called_with(
        "Index file %s was invalid JSON. Rebuilding from scratch.",
        storage_agent._index_file,
    )


def test_increment_and_reset_failure_counts(storage_agent):
    count = storage_agent.increment_failure_count("calendar")
    assert count == 1
    count = storage_agent.increment_failure_count("calendar")
    assert count == 2

    storage_agent.reset_failure_count("calendar")
    state = json.loads(storage_agent._failure_state_file.read_text(encoding="utf-8"))
    assert "calendar" not in state


def test_load_failure_state_handles_invalid_json(storage_agent):
    storage_agent._failure_state_file.write_text("not-json", encoding="utf-8")
    state = storage_agent._load_failure_state()
    assert state == {}
    storage_agent.logger.warning.assert_called_with(
        "Failure state file %s was invalid JSON. Resetting state.",
        storage_agent._failure_state_file,
    )
