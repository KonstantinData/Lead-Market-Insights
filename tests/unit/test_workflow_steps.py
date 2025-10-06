import logging

import pytest

from utils.workflow_steps import WorkflowStepRecorder


@pytest.fixture
def recorder():
    return WorkflowStepRecorder()


def test_record_step_logs_extra_and_blocks_duplicates(recorder, caplog):
    caplog.set_level(logging.INFO)

    assert recorder.record_step("run-1", "event-1", "initial", extra={"foo": "bar"}) is True
    assert "foo" in caplog.text

    # Duplicate step should be ignored and not append new log lines
    caplog.clear()
    assert recorder.record_step("run-1", "event-1", "initial", extra={"foo": "bar"}) is False
    assert caplog.text == ""


def test_record_step_with_missing_event(recorder, caplog):
    caplog.set_level(logging.INFO)

    assert recorder.record_step("run-1", None, "no-event") is True
    assert "_no_event_" not in caplog.text


def test_should_write_manifest_and_clear_run(recorder):
    assert recorder.should_write_manifest("run-1") is True
    assert recorder.should_write_manifest("run-1") is False

    recorder.record_step("run-1", "event-1", "step-a")
    recorder.record_step("run-2", "event-2", "step-b")

    recorder.clear_run("run-1")

    # After clearing run-1 we can log the same step again, run-2 remains untouched
    assert recorder.record_step("run-1", "event-1", "step-a") is True
    assert recorder.record_step("run-2", "event-2", "step-b") is False
