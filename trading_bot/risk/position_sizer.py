"""Position sizing utilities based on account risk constraints."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass
class DepthLevel:
    price: float
    size: float


@dataclass
class DepthSnapshot:
    """Represents a simplified order book snapshot."""

    bids: Sequence[DepthLevel]
    asks: Sequence[DepthLevel]

    def side(self, is_buy: bool) -> Sequence[DepthLevel]:
        return self.asks if is_buy else self.bids


@dataclass
class PositionSizeResult:
    """Details about the calculated order size."""

    size: float
    risk_limit_size: float
    slippage_limit_size: float
    risk_amount: float


class PositionSizer:
    """Calculates trade sizes using risk percentage and liquidity constraints."""

    def __init__(
        self,
        equity: float,
        risk_percent: float,
        atr_stop_multiple: float = 1.0,
        slippage_cap: float = 0.001,
    ) -> None:
        if equity <= 0:
            raise ValueError("equity must be positive")
        if risk_percent <= 0:
            raise ValueError("risk_percent must be positive")
        self.equity = equity
        self.risk_percent = risk_percent
        self.atr_stop_multiple = atr_stop_multiple
        self.slippage_cap = slippage_cap

    def _risk_amount(self) -> float:
        return self.equity * self.risk_percent

    def risk_based_size(self, entry_price: float, atr: float) -> Tuple[float, float]:
        """Return (size, risk_amount) from equity and ATR derived stop distance."""
        if entry_price <= 0:
            raise ValueError("entry_price must be positive")
        if atr <= 0:
            raise ValueError("atr must be positive")
        stop_distance = atr * self.atr_stop_multiple
        risk_per_unit = stop_distance
        risk_amount = self._risk_amount()
        max_units = risk_amount / risk_per_unit
        return max_units, risk_amount

    def slippage_limited_size(self, is_buy: bool, entry_price: float, depth: DepthSnapshot) -> float:
        """Compute the maximum size allowed by the slippage cap using depth data."""
        levels = depth.side(is_buy)
        if not levels:
            return 0.0

        max_slip_price = entry_price * (1 + self.slippage_cap if is_buy else 1 - self.slippage_cap)
        epsilon = entry_price * 1e-9
        total_size = 0.0
        for level in levels:
            if is_buy and level.price - max_slip_price > epsilon:
                break
            if not is_buy and max_slip_price - level.price > epsilon:
                break
            total_size += level.size
        return total_size

    def size_order(
        self,
        entry_price: float,
        atr: float,
        is_buy: bool,
        depth: DepthSnapshot,
    ) -> PositionSizeResult:
        risk_size, risk_amount = self.risk_based_size(entry_price, atr)
        slippage_size = self.slippage_limited_size(is_buy=is_buy, entry_price=entry_price, depth=depth)
        size = min(risk_size, slippage_size)
        return PositionSizeResult(
            size=size,
            risk_limit_size=risk_size,
            slippage_limit_size=slippage_size,
            risk_amount=risk_amount,
        )
