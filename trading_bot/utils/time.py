"""Time normalisation helpers."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(slots=True)
class MonotonicTimestampGuard:
    """Ensure timestamps emitted by a feed are monotonically increasing."""

    max_drift_ns: int = 5_000_000_000  # 5 seconds

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._last_wall_ns = 0
        self._last_monotonic_ns = 0

    def normalise(self, ts_ns: int) -> int:
        """Return a timestamp that never goes backwards."""

        now_monotonic = time.monotonic_ns()
        with self._lock:
            if self._last_wall_ns == 0:
                self._last_wall_ns = ts_ns
                self._last_monotonic_ns = now_monotonic
                return ts_ns

            if ts_ns >= self._last_wall_ns:
                self._last_wall_ns = ts_ns
                self._last_monotonic_ns = now_monotonic
                return ts_ns

            monotonic_delta = max(0, now_monotonic - self._last_monotonic_ns)
            candidate = self._last_wall_ns + monotonic_delta

            if candidate - ts_ns > self.max_drift_ns:
                candidate = ts_ns + self.max_drift_ns

            self._last_wall_ns = candidate
            self._last_monotonic_ns = now_monotonic
            return candidate
