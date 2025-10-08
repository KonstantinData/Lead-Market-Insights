import os
from importlib import reload


def test_hitl_threshold_default(monkeypatch):
    monkeypatch.delenv("HITL_CONFIDENCE_THRESHOLD", raising=False)
    import config.config as cfg

    reload(cfg)
    assert 0.79 < cfg.settings.HITL_CONFIDENCE_THRESHOLD < 0.81


def test_hitl_threshold_from_env(monkeypatch):
    monkeypatch.setenv("HITL_CONFIDENCE_THRESHOLD", "0.9")
    import config.config as cfg

    reload(cfg)
    assert abs(cfg.settings.HITL_CONFIDENCE_THRESHOLD - 0.9) < 1e-6

