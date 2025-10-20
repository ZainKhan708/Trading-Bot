"""Kill switch logic for halting trading when safety checks fail."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

from trading_bot.core.position_tracker import PositionTracker


class KillSwitch:
    """Monitors infrastructure and trading state for fatal conditions."""

    def __init__(
        self,
        heartbeat_interval: timedelta,
        heartbeat_grace: timedelta,
        clock_skew_limit: timedelta,
        error_window: timedelta,
        error_threshold: int,
        position_tolerance: float,
        on_halt: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_grace = heartbeat_grace
        self.clock_skew_limit = clock_skew_limit
        self.error_window = error_window
        self.error_threshold = error_threshold
        self.position_tolerance = position_tolerance
        self.on_halt = on_halt

        self._last_heartbeat: Optional[datetime] = None
        self._halted: bool = False
        self._halt_reason: Optional[str] = None
        self._error_events: Dict[datetime, int] = {}

    def _trigger(self, reason: str) -> None:
        if self._halted:
            return
        self._halted = True
        self._halt_reason = reason
        if self.on_halt:
            self.on_halt(reason)

    def report_heartbeat(self, timestamp: datetime) -> None:
        self._last_heartbeat = timestamp

    def check_heartbeat(self, now: Optional[datetime] = None) -> None:
        now = now or datetime.utcnow()
        if self._last_heartbeat is None:
            self._trigger("heartbeat_missing")
            return
        if now - self._last_heartbeat > self.heartbeat_interval + self.heartbeat_grace:
            self._trigger("heartbeat_timeout")

    def check_clock_skew(self, exchange_time: datetime, local_time: Optional[datetime] = None) -> None:
        local_time = local_time or datetime.utcnow()
        skew = abs(local_time - exchange_time)
        if skew > self.clock_skew_limit:
            self._trigger("clock_skew")

    def record_api_error(self, status_code: int, timestamp: Optional[datetime] = None) -> None:
        if status_code not in {429} and status_code // 100 != 5:
            return
        timestamp = timestamp or datetime.utcnow()
        self._error_events[timestamp] = self._error_events.get(timestamp, 0) + 1
        self._prune_errors(timestamp)
        if sum(self._error_events.values()) >= self.error_threshold:
            self._trigger("api_errors")

    def _prune_errors(self, now: datetime) -> None:
        window_start = now - self.error_window
        self._error_events = {ts: count for ts, count in self._error_events.items() if ts >= window_start}

    def check_position_sync(
        self,
        tracker: PositionTracker,
        exchange_positions: Dict[str, float],
    ) -> None:
        for symbol, local_net in ((s, tracker.net_position(s)) for s in tracker.positions.keys()):
            remote_net = exchange_positions.get(symbol, 0.0)
            if abs(local_net - remote_net) > self.position_tolerance:
                self._trigger(f"position_desync:{symbol}")
                break

    def halt_trading(self, reason: str) -> None:
        self._trigger(reason)

    def reset(self) -> None:
        self._halted = False
        self._halt_reason = None
        self._error_events.clear()

    @property
    def halted(self) -> bool:
        return self._halted

    @property
    def halt_reason(self) -> Optional[str]:
        return self._halt_reason
