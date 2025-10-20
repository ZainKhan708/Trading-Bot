"""Streaming technical indicators for algorithmic trading.

This module provides incremental update implementations of several
commonly used indicators. All indicators expose an :meth:`update`
method that accepts the latest market data and returns the newly
computed value. The classes are intentionally stateful so that they can
be wired into event-driven data pipelines without reprocessing history.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable, Optional, Tuple


class StreamingIndicator:
    """Base class for streaming indicators."""

    def update(self, *args, **kwargs):  # pragma: no cover - interface only
        raise NotImplementedError

    @property
    def value(self):  # pragma: no cover - interface only
        raise NotImplementedError


@dataclass
class EMA(StreamingIndicator):
    """Exponential Moving Average with streaming updates."""

    period: int
    value_: Optional[float] = None
    alpha: float = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("EMA period must be positive")
        # smoothing factor matching conventional EMA definition
        self.alpha = 2.0 / (self.period + 1.0)

    def update(self, price: float) -> float:
        if self.value_ is None:
            self.value_ = price
        else:
            self.value_ = (price - self.value_) * self.alpha + self.value_
        return self.value_

    @property
    def value(self) -> Optional[float]:
        return self.value_


@dataclass
class ATR(StreamingIndicator):
    """Average True Range using Wilder's smoothing."""

    period: int
    prev_close: Optional[float] = None
    value_: Optional[float] = None

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("ATR period must be positive")
        self.alpha = 1.0 / self.period

    def update(self, high: float, low: float, close: float) -> float:
        if self.prev_close is None:
            true_range = high - low
        else:
            true_range = max(
                high - low,
                abs(high - self.prev_close),
                abs(low - self.prev_close),
            )
        self.prev_close = close
        if self.value_ is None:
            self.value_ = true_range
        else:
            self.value_ = (1 - self.alpha) * self.value_ + self.alpha * true_range
        return self.value_

    @property
    def value(self) -> Optional[float]:
        return self.value_


@dataclass
class RSI(StreamingIndicator):
    """Relative Strength Index calculated incrementally."""

    period: int
    avg_gain: Optional[float] = None
    avg_loss: Optional[float] = None
    prev_close: Optional[float] = None
    value_: Optional[float] = None

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("RSI period must be positive")

    def update(self, close: float) -> float:
        if self.prev_close is None:
            self.prev_close = close
            self.value_ = 50.0
            return self.value_

        change = close - self.prev_close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if self.avg_gain is None:
            self.avg_gain = gain
            self.avg_loss = loss
        else:
            k = 1.0 / self.period
            self.avg_gain = (1 - k) * self.avg_gain + k * gain
            self.avg_loss = (1 - k) * self.avg_loss + k * loss

        self.prev_close = close

        if self.avg_loss == 0:
            self.value_ = 100.0
        else:
            rs = self.avg_gain / self.avg_loss
            self.value_ = 100 - (100 / (1 + rs))
        return self.value_

    @property
    def value(self) -> Optional[float]:
        return self.value_


@dataclass
class VWAP(StreamingIndicator):
    """Volume Weighted Average Price computed cumulatively."""

    cumulative_price_volume: float = 0.0
    cumulative_volume: float = 0.0

    def update(self, price: float, volume: float) -> float:
        if volume < 0:
            raise ValueError("Volume must be non-negative")
        self.cumulative_price_volume += price * volume
        self.cumulative_volume += volume
        if self.cumulative_volume == 0:
            return 0.0
        return self.cumulative_price_volume / self.cumulative_volume

    @property
    def value(self) -> Optional[float]:
        if self.cumulative_volume == 0:
            return None
        return self.cumulative_price_volume / self.cumulative_volume

    def reset_session(self) -> None:
        self.cumulative_price_volume = 0.0
        self.cumulative_volume = 0.0


@dataclass
class ZScore(StreamingIndicator):
    """Z-score of the most recent value against a rolling window."""

    window: int
    values: Deque[float] = field(default_factory=deque)
    value_: Optional[float] = None

    def __post_init__(self) -> None:
        if self.window <= 1:
            raise ValueError("Z-score window must be greater than 1")

    def update(self, value: float) -> float:
        self.values.append(value)
        if len(self.values) > self.window:
            self.values.popleft()
        if len(self.values) < 2:
            self.value_ = 0.0
            return self.value_
        mean = sum(self.values) / len(self.values)
        variance = sum((x - mean) ** 2 for x in self.values) / (len(self.values) - 1)
        std = variance ** 0.5 if variance > 0 else 0.0
        if std == 0:
            self.value_ = 0.0
        else:
            self.value_ = (value - mean) / std
        return self.value_

    @property
    def value(self) -> Optional[float]:
        return self.value_


@dataclass
class OrderBookImbalance(StreamingIndicator):
    """Measures bid/ask volume imbalance in the order book."""

    depth: int
    last_value: Optional[float] = None

    def __post_init__(self) -> None:
        if self.depth <= 0:
            raise ValueError("Depth must be positive")

    def update(
        self,
        bids: Iterable[Tuple[float, float]],
        asks: Iterable[Tuple[float, float]],
    ) -> float:
        bid_volume = sum(volume for _, volume in list(bids)[: self.depth])
        ask_volume = sum(volume for _, volume in list(asks)[: self.depth])
        total = bid_volume + ask_volume
        if total == 0:
            self.last_value = 0.0
        else:
            self.last_value = (bid_volume - ask_volume) / total
        return self.last_value

    @property
    def value(self) -> Optional[float]:
        return self.last_value


@dataclass
class ADX(StreamingIndicator):
    """Average Directional Index for regime detection."""

    period: int
    prev_high: Optional[float] = None
    prev_low: Optional[float] = None
    prev_close: Optional[float] = None

    tr_values: Deque[float] = field(default_factory=deque)
    plus_dm_values: Deque[float] = field(default_factory=deque)
    minus_dm_values: Deque[float] = field(default_factory=deque)
    dx_values: Deque[float] = field(default_factory=deque)

    tr_sum: float = 0.0
    plus_dm_sum: float = 0.0
    minus_dm_sum: float = 0.0
    dx_sum: float = 0.0

    adx_value: Optional[float] = None

    def __post_init__(self) -> None:
        if self.period <= 1:
            raise ValueError("ADX period must be greater than 1")

    def update(self, high: float, low: float, close: float) -> Optional[float]:
        tr = self._true_range(high, low, close)
        plus_dm, minus_dm = self._directional_movement(high, low)

        self._push(self.tr_values, tr, "tr_sum")
        self._push(self.plus_dm_values, plus_dm, "plus_dm_sum")
        self._push(self.minus_dm_values, minus_dm, "minus_dm_sum")

        di_plus, di_minus = self._directional_indicators()
        dx = 100 * abs(di_plus - di_minus) / max(di_plus + di_minus, 1e-9)

        self._push(self.dx_values, dx, "dx_sum")

        self.prev_high, self.prev_low, self.prev_close = high, low, close

        if len(self.tr_values) < self.period:
            return None

        if self.adx_value is None:
            if len(self.dx_values) < self.period:
                return None
            self.adx_value = self.dx_sum / len(self.dx_values)
        else:
            self.adx_value = (self.adx_value * (self.period - 1) + dx) / self.period
        return self.adx_value

    def _push(self, queue: Deque[float], value: float, attr: str) -> None:
        queue.append(value)
        setattr(self, attr, getattr(self, attr) + value)
        if len(queue) > self.period:
            dropped = queue.popleft()
            setattr(self, attr, getattr(self, attr) - dropped)

    def _directional_indicators(self) -> Tuple[float, float]:
        if self.tr_sum == 0:
            return 0.0, 0.0
        di_plus = 100 * (self.plus_dm_sum / self.tr_sum)
        di_minus = 100 * (self.minus_dm_sum / self.tr_sum)
        return di_plus, di_minus

    def _true_range(self, high: float, low: float, close: float) -> float:
        if self.prev_close is None:
            return high - low
        return max(
            high - low,
            abs(high - self.prev_close),
            abs(low - self.prev_close),
        )

    def _directional_movement(self, high: float, low: float) -> Tuple[float, float]:
        if self.prev_high is None or self.prev_low is None:
            return 0.0, 0.0
        up_move = high - self.prev_high
        down_move = self.prev_low - low
        plus_dm = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0.0
        return plus_dm, minus_dm

    @property
    def value(self) -> Optional[float]:
        return self.adx_value
