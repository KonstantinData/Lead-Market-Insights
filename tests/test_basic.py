"""Basic tests to validate the setup."""

import pytest

from src import __version__


def test_version():
    """Test that version is defined and is a string."""
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"


def test_basic_math():
    """Test basic functionality."""
    assert 2 + 2 == 4


@pytest.mark.unit
def test_unit_marker():
    """Test that pytest markers work."""
    assert True


@pytest.mark.slow
def test_slow_marker():
    """Test slow marker (can be skipped with -m 'not slow')."""
    assert True
