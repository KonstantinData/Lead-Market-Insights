"""Unit tests for the cost guard utility."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from agents.alert_agent import AlertSeverity
from utils.cost_guard import BudgetExceededError, CostGuard


class DummyAlertAgent:
    def __init__(self) -> None:
        self.calls = []

    def send_alert(self, message, severity, context=None):  # pragma: no cover - exercised in tests
        self.calls.append((message, severity, context or {}))


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta

    def set(self, value: datetime) -> None:
        self.current = value


def test_cost_guard_warns_before_limits():
    alert_agent = DummyAlertAgent()
    guard = CostGuard(
        daily_cap=10.0,
        monthly_cap=100.0,
        service_rate_limits=None,
        alert_agent=alert_agent,
    )

    decision = guard.authorise("openai", 9.0)

    assert decision.allowed
    assert guard.daily_spend == pytest.approx(9.0)
    assert decision.warnings
    assert alert_agent.calls
    message, severity, context = alert_agent.calls[-1]
    assert "approaching" in message
    assert severity == AlertSeverity.WARNING
    assert context["scope"] == "daily"


def test_cost_guard_blocks_and_alerts_on_daily_cap():
    alert_agent = DummyAlertAgent()
    guard = CostGuard(
        daily_cap=10.0,
        monthly_cap=20.0,
        service_rate_limits=None,
        alert_agent=alert_agent,
    )

    guard.authorise("openai", 9.0)
    decision = guard.authorise("openai", 2.0)

    assert not decision.allowed
    assert "Daily cost cap" in (decision.blocked_reason or "")
    assert guard.daily_spend == pytest.approx(9.0)
    assert alert_agent.calls
    message, severity, context = alert_agent.calls[-1]
    assert "limit hit" in message
    assert severity == AlertSeverity.ERROR
    assert context["scope"] == "daily"

    with pytest.raises(BudgetExceededError):
        guard.authorise("openai", 2.0, raise_on_block=True)


def test_cost_guard_enforces_rate_limit():
    clock = FakeClock(datetime(2024, 1, 1, 12, 0, 0))
    guard = CostGuard(
        daily_cap=100.0,
        monthly_cap=100.0,
        service_rate_limits={"openai": 2},
        alert_agent=None,
        time_provider=clock.now,
    )

    assert guard.authorise("openai", 1.0).allowed
    clock.advance(timedelta(seconds=5))
    assert guard.authorise("openai", 1.0).allowed
    clock.advance(timedelta(seconds=5))
    decision = guard.authorise("openai", 1.0)

    assert not decision.allowed
    assert "Rate limit" in (decision.blocked_reason or "")

    clock.advance(timedelta(minutes=1))
    decision = guard.authorise("openai", 1.0)
    assert decision.allowed


def test_cost_guard_resets_daily_and_monthly_windows():
    clock = FakeClock(datetime(2024, 1, 30, 23, 30, 0))
    guard = CostGuard(
        daily_cap=10.0,
        monthly_cap=20.0,
        service_rate_limits=None,
        alert_agent=None,
        time_provider=clock.now,
    )

    guard.authorise("openai", 5.0)
    assert guard.daily_spend == pytest.approx(5.0)
    assert guard.monthly_spend == pytest.approx(5.0)

    clock.advance(timedelta(hours=2))  # move into next day but same month
    guard.authorise("openai", 5.0)
    assert guard.daily_spend == pytest.approx(5.0)
    assert guard.monthly_spend == pytest.approx(10.0)

    clock.set(datetime(2024, 2, 1, 1, 0, 0))
    guard.authorise("openai", 5.0)
    assert guard.daily_spend == pytest.approx(5.0)
    assert guard.monthly_spend == pytest.approx(5.0)
