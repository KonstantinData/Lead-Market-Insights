"""Runtime guard for tracking API spend and enforcing budget limits."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Deque, Dict, List, Mapping, MutableMapping, Optional

from agents.alert_agent import AlertAgent, AlertSeverity

from utils import observability


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BudgetExceededError(RuntimeError):
    """Raised when a cost guard check determines the budget has been exceeded."""


@dataclass
class CostDecision:
    """Outcome of a cost guard evaluation."""

    allowed: bool
    blocked_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    daily_spend: float = 0.0
    monthly_spend: float = 0.0


class CostGuard:
    """Track cumulative spend and rate limits for downstream services."""

    def __init__(
        self,
        *,
        daily_cap: float,
        monthly_cap: float,
        service_rate_limits: Optional[Mapping[str, int]] = None,
        alert_agent: Optional[AlertAgent] = None,
        logger: Optional[logging.Logger] = None,
        warning_threshold: float = 0.9,
        rate_limit_window: timedelta = timedelta(minutes=1),
        time_provider: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.daily_cap = max(float(daily_cap), 0.0)
        self.monthly_cap = max(float(monthly_cap), 0.0)
        self.alert_agent = alert_agent
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.warning_threshold = warning_threshold
        self.rate_limit_window = rate_limit_window
        self._now = time_provider

        limits = service_rate_limits or {}
        self.service_rate_limits: Dict[str, int] = {
            self._normalise_service(name): int(limit)
            for name, limit in limits.items()
            if int(limit) > 0
        }

        start = self._now()
        self._daily_anchor = start.date()
        self._monthly_anchor = (start.year, start.month)
        self._daily_spend = 0.0
        self._monthly_spend = 0.0
        self._service_spend: Dict[str, float] = defaultdict(float)
        self._service_invocations: Dict[str, Deque[datetime]] = defaultdict(deque)
        self._warned_limits: MutableMapping[str, bool] = {"daily": False, "monthly": False}

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_settings(
        cls,
        settings: Any,
        *,
        alert_agent: Optional[AlertAgent] = None,
        logger: Optional[logging.Logger] = None,
        warning_threshold: float = 0.9,
        rate_limit_window: timedelta = timedelta(minutes=1),
        time_provider: Callable[[], datetime] = _utc_now,
    ) -> "CostGuard":
        """Instantiate a cost guard using attributes exposed on settings."""

        return cls(
            daily_cap=float(getattr(settings, "daily_cost_cap", 0.0)),
            monthly_cap=float(getattr(settings, "monthly_cost_cap", 0.0)),
            service_rate_limits=getattr(settings, "service_rate_limits", None),
            alert_agent=alert_agent,
            logger=logger,
            warning_threshold=warning_threshold,
            rate_limit_window=rate_limit_window,
            time_provider=time_provider,
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------
    def authorise(
        self,
        service: str,
        cost: float,
        *,
        metadata: Optional[Mapping[str, object]] = None,
        raise_on_block: bool = False,
    ) -> CostDecision:
        """Check whether a service call may proceed and record the spend."""

        normalised_service = self._normalise_service(service)
        now = self._now()
        self._reset_if_needed(now)

        cost = max(float(cost), 0.0)
        warnings: List[str] = []
        blocked_reason: Optional[str] = None

        rate_limit_reason = self._check_rate_limit(normalised_service, now)
        if rate_limit_reason:
            blocked_reason = rate_limit_reason
        else:
            blocked_reason = self._evaluate_costs(normalised_service, cost, metadata)

        if blocked_reason:
            if raise_on_block:
                raise BudgetExceededError(blocked_reason)
            return CostDecision(
                allowed=False,
                blocked_reason=blocked_reason,
                warnings=warnings,
                daily_spend=self._daily_spend,
                monthly_spend=self._monthly_spend,
            )

        self._service_invocations[normalised_service].append(now)
        self._service_spend[normalised_service] += cost
        self._daily_spend += cost
        self._monthly_spend += cost
        observability.record_cost_spend(normalised_service, cost)

        warnings.extend(
            self._evaluate_thresholds(normalised_service, metadata)
        )

        return CostDecision(
            allowed=True,
            warnings=warnings,
            daily_spend=self._daily_spend,
            monthly_spend=self._monthly_spend,
        )

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------
    @property
    def daily_spend(self) -> float:
        return self._daily_spend

    @property
    def monthly_spend(self) -> float:
        return self._monthly_spend

    @property
    def service_spend(self) -> Mapping[str, float]:
        return dict(self._service_spend)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _normalise_service(self, service: str) -> str:
        return (service or "unknown").strip().lower() or "unknown"

    def _reset_if_needed(self, now: datetime) -> None:
        if now.date() != self._daily_anchor:
            self.logger.debug("Resetting daily spend window: %s -> %s", self._daily_anchor, now.date())
            self._daily_anchor = now.date()
            self._daily_spend = 0.0
            self._warned_limits["daily"] = False

        month_anchor = (now.year, now.month)
        if month_anchor != self._monthly_anchor:
            self.logger.debug(
                "Resetting monthly spend window: %s -> %s", self._monthly_anchor, month_anchor
            )
            self._monthly_anchor = month_anchor
            self._monthly_spend = 0.0
            self._warned_limits["monthly"] = False

    def _check_rate_limit(self, service: str, now: datetime) -> Optional[str]:
        limit = self.service_rate_limits.get(service)
        if not limit:
            return None

        window_start = now - self.rate_limit_window
        invocations = self._service_invocations[service]
        while invocations and invocations[0] <= window_start:
            invocations.popleft()

        if len(invocations) >= limit:
            message = (
                f"Rate limit exceeded for {service}: {len(invocations)} calls in "
                f"{self.rate_limit_window.total_seconds():.0f}s window (limit {limit})."
            )
            self.logger.warning(message)
            observability.record_cost_limit_event(
                "rate_limit_breach", service, limit=limit
            )
            return message

        return None

    def _evaluate_costs(
        self,
        service: str,
        cost: float,
        metadata: Optional[Mapping[str, object]],
    ) -> Optional[str]:
        projected_daily = self._daily_spend + cost
        projected_monthly = self._monthly_spend + cost

        if self.daily_cap and projected_daily > self.daily_cap:
            message = (
                f"Daily cost cap of ${self.daily_cap:.2f} exceeded by service {service}."
            )
            self._emit_breach_alert("daily", service, projected_daily, self.daily_cap, metadata)
            return message

        if self.monthly_cap and projected_monthly > self.monthly_cap:
            message = (
                f"Monthly cost cap of ${self.monthly_cap:.2f} exceeded by service {service}."
            )
            self._emit_breach_alert(
                "monthly", service, projected_monthly, self.monthly_cap, metadata
            )
            return message

        return None

    def _evaluate_thresholds(
        self,
        service: str,
        metadata: Optional[Mapping[str, object]],
    ) -> List[str]:
        messages: List[str] = []

        if self.daily_cap:
            ratio = self._daily_spend / self.daily_cap if self.daily_cap else 0.0
            if ratio >= self.warning_threshold and not self._warned_limits["daily"]:
                messages.append(
                    self._emit_warning("daily", service, self._daily_spend, self.daily_cap, metadata)
                )

        if self.monthly_cap:
            ratio = self._monthly_spend / self.monthly_cap if self.monthly_cap else 0.0
            if ratio >= self.warning_threshold and not self._warned_limits["monthly"]:
                messages.append(
                    self._emit_warning(
                        "monthly", service, self._monthly_spend, self.monthly_cap, metadata
                    )
                )

        return [msg for msg in messages if msg]

    def _emit_warning(
        self,
        scope: str,
        service: str,
        spend: float,
        limit: float,
        metadata: Optional[Mapping[str, object]],
    ) -> str:
        self._warned_limits[scope] = True
        message = (
            f"{scope.capitalize()} spend for {service} is approaching the limit: "
            f"${spend:.2f} of ${limit:.2f}."
        )
        self.logger.warning(message)
        observability.record_cost_limit_event("warning", service, limit=limit)
        self._send_alert(message, AlertSeverity.WARNING, metadata, scope, spend, limit)
        return message

    def _emit_breach_alert(
        self,
        scope: str,
        service: str,
        spend: float,
        limit: float,
        metadata: Optional[Mapping[str, object]],
    ) -> None:
        observability.record_cost_limit_event("breach", service, limit=limit)
        message = (
            f"{scope.capitalize()} cost limit hit for {service}: ${spend:.2f} exceeds ${limit:.2f}."
        )
        self.logger.error(message)
        self._send_alert(message, AlertSeverity.ERROR, metadata, scope, spend, limit)

    def _send_alert(
        self,
        message: str,
        severity: AlertSeverity,
        metadata: Optional[Mapping[str, object]],
        scope: str,
        spend: float,
        limit: float,
    ) -> None:
        if not self.alert_agent:
            return

        context = {
            "scope": scope,
            "spend": spend,
            "limit": limit,
        }
        if metadata:
            context.update(metadata)

        try:
            self.alert_agent.send_alert(message, severity, context=context)
        except Exception:  # pragma: no cover - defensive alerting
            self.logger.exception("Failed to dispatch %s alert", severity.value)
