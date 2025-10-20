"""Drawdown monitoring utilities for trading risk management."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional


@dataclass
class DrawdownState:
    limit: float
    cool_off: timedelta
    peak_equity: float
    floor_equity: float
    cool_off_until: Optional[datetime] = None

    def update(self, equity: float, now: datetime) -> None:
        if self.peak_equity == 0:
            self.peak_equity = equity
            self.floor_equity = equity
            return
        self.peak_equity = max(self.peak_equity, equity)
        self.floor_equity = min(self.floor_equity, equity)
        drawdown = 1 - (equity / self.peak_equity if self.peak_equity > 0 else 0)
        if drawdown >= self.limit and self.cool_off_until is None:
            self.cool_off_until = now + self.cool_off

    def reset_period(self, equity: float) -> None:
        self.peak_equity = equity
        self.floor_equity = equity
        self.cool_off_until = None

    def trading_allowed(self, now: datetime) -> bool:
        if self.cool_off_until and now < self.cool_off_until:
            return False
        return True


@dataclass
class DrawdownMonitor:
    """Tracks daily and weekly drawdowns and enforces cool-off windows."""

    daily_limit: float
    weekly_limit: float
    daily_cool_off: timedelta
    weekly_cool_off: timedelta
    manual_override_until: Optional[datetime] = None
    _states: Dict[str, DrawdownState] = field(init=False)
    _last_daily_reset: datetime = field(init=False)
    _last_weekly_reset: datetime = field(init=False)

    def __post_init__(self) -> None:
        now = datetime.utcnow()
        self._states = {
            "daily": DrawdownState(
                limit=self.daily_limit,
                cool_off=self.daily_cool_off,
                peak_equity=0.0,
                floor_equity=0.0,
            ),
            "weekly": DrawdownState(
                limit=self.weekly_limit,
                cool_off=self.weekly_cool_off,
                peak_equity=0.0,
                floor_equity=0.0,
            ),
        }
        self._last_daily_reset = now
        self._last_weekly_reset = now

    def manual_override(self, until: datetime) -> None:
        """Temporarily allow trading despite drawdowns."""
        self.manual_override_until = until

    def clear_manual_override(self) -> None:
        self.manual_override_until = None

    def _maybe_reset(self, equity: float, now: datetime) -> None:
        if now.date() != self._last_daily_reset.date():
            self._states["daily"].reset_period(equity)
            self._last_daily_reset = now
        if now.isocalendar()[1] != self._last_weekly_reset.isocalendar()[1]:
            self._states["weekly"].reset_period(equity)
            self._last_weekly_reset = now

    def record_equity(self, equity: float, now: Optional[datetime] = None) -> None:
        if equity <= 0:
            raise ValueError("equity must be positive")
        now = now or datetime.utcnow()
        self._maybe_reset(equity, now)
        for state in self._states.values():
            state.update(equity, now)

    def trading_allowed(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.utcnow()
        if self.manual_override_until and now < self.manual_override_until:
            return True
        return all(state.trading_allowed(now) for state in self._states.values())

    def status(self, now: Optional[datetime] = None) -> Dict[str, Dict[str, float | bool | str]]:
        now = now or datetime.utcnow()
        summary: Dict[str, Dict[str, float | bool | str]] = {}
        for name, state in self._states.items():
            drawdown = 1 - (state.floor_equity / state.peak_equity if state.peak_equity > 0 else 0)
            summary[name] = {
                "drawdown": drawdown,
                "limit": state.limit,
                "cool_off_until": state.cool_off_until.isoformat() if state.cool_off_until else None,
                "trading_allowed": state.trading_allowed(now),
            }
        summary["override_active"] = bool(self.manual_override_until and now < self.manual_override_until)
        return summary
