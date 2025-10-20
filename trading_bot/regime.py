"""Regime filters that modulate strategy behaviour."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .indicators.streaming import ADX, EMA


@dataclass
class BreadthProxy:
    """Tracks market breadth as an exponentially weighted average."""

    period: int = 20
    ema: EMA = field(init=False)
    latest: Optional[float] = None

    def __post_init__(self) -> None:
        self.ema = EMA(self.period)

    def update(self, value: float) -> float:
        self.latest = self.ema.update(value)
        return self.latest


@dataclass
class RegimeFilter:
    """Combines ADX and breadth filters to gate mean-reversion strategies."""

    adx_period: int = 14
    adx_threshold: float = 25.0
    breadth_period: int = 20
    breadth_threshold: float = 0.6
    adx_indicator: ADX = field(init=False)
    breadth_proxy: BreadthProxy = field(init=False)
    trending: bool = False

    def __post_init__(self) -> None:
        self.adx_indicator = ADX(self.adx_period)
        self.breadth_proxy = BreadthProxy(self.breadth_period)

    def update(self, high: float, low: float, close: float, breadth_value: float) -> bool:
        adx = self.adx_indicator.update(high, low, close)
        breadth = self.breadth_proxy.update(breadth_value)

        adx_trending = adx is not None and adx >= self.adx_threshold
        breadth_trending = breadth is not None and breadth >= self.breadth_threshold
        self.trending = adx_trending or breadth_trending
        return not self.trending

    def allow_mean_reversion(self) -> bool:
        return not self.trending

    @property
    def adx(self) -> Optional[float]:
        return self.adx_indicator.value

    @property
    def breadth(self) -> Optional[float]:
        return self.breadth_proxy.latest
