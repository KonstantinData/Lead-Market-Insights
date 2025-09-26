import json

from agents.local_storage_agent import LocalStorageAgent


def test_local_storage_agent_creates_directory(tmp_path):
    base_dir = tmp_path / "runs"
    agent = LocalStorageAgent(base_dir)

    run_dir = agent.create_run_directory("2024-01-01T00-00-00Z")

    assert run_dir.exists()
    assert run_dir.is_dir()
    assert run_dir.parent == base_dir


def test_local_storage_agent_records_run(tmp_path):
    base_dir = tmp_path / "runs"
    agent = LocalStorageAgent(base_dir)
    log_file = base_dir / "2024" / "log.txt"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("hello", encoding="utf-8")

    agent.record_run("run-1", log_file)

    index_path = base_dir / "index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))

    assert data[0]["run_id"] == "run-1"
    assert "log_path" in data[0]
    assert data[0]["log_path"].endswith("log.txt")
