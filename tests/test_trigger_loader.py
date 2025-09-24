from pathlib import Path

import pytest

from utils.trigger_loader import load_trigger_words
from utils.text_normalization import normalize_text


@pytest.fixture
def trigger_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "trigger_words.txt"
    file_path.write_text(
        """
        # Comment line should be ignored
         Trigger
        demo
        TRIGGER
        küche
        
        meeting
        """,
        encoding="utf-8",
    )
    return file_path


def test_load_trigger_words_from_env_overrides_file(trigger_file: Path) -> None:
    words = load_trigger_words(
        "Alpha, Beta , ,Gamma", triggers_file=trigger_file
    )
    assert words == [normalize_text("Alpha"), normalize_text("Beta"), normalize_text("Gamma")]


def test_load_trigger_words_from_file_when_env_missing(trigger_file: Path) -> None:
    words = load_trigger_words(None, triggers_file=trigger_file)
    assert words == [
        normalize_text("Trigger"),
        normalize_text("demo"),
        normalize_text("küche"),
        normalize_text("meeting"),
    ]


def test_load_trigger_words_returns_empty_when_no_sources(tmp_path: Path) -> None:
    missing_file = tmp_path / "nonexistent.txt"
    assert load_trigger_words("", triggers_file=missing_file) == []
