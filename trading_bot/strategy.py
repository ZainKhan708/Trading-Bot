"""Example strategy implementations."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List

from .events import FillEvent, MarketEvent, OrderRequest, OrderType, Side
from .interfaces import Strategy


@dataclass
class MeanReversionStrategy(Strategy):
    """Simple mean reversion strategy using rolling z-score."""

    symbol: str
    lookback: int = 20
    entry_z: float = 1.5
    exit_z: float = 0.5
    size: float = 100.0
    prices: Deque[float] = field(default_factory=deque, init=False)
    current_position: float = field(default=0.0, init=False)

    def on_start(self) -> None:
        self.prices.clear()
        self.current_position = 0.0

    def on_market_data(self, event: MarketEvent) -> List[OrderRequest]:
        if event.symbol != self.symbol:
            return []
        self.prices.append(event.midpoint)
        if len(self.prices) > self.lookback:
            self.prices.popleft()
        if len(self.prices) < self.lookback:
            return []
        mean = sum(self.prices) / self.lookback
        variance = sum((p - mean) ** 2 for p in self.prices) / self.lookback
        std = variance ** 0.5
        if std == 0:
            return []
        z_score = (event.midpoint - mean) / std
        orders: List[OrderRequest] = []
        if z_score > self.entry_z and self.current_position >= 0:
            orders.append(
                OrderRequest(
                    client_order_id=f"{event.timestamp.timestamp()}-sell",
                    symbol=self.symbol,
                    side=Side.SELL,
                    quantity=self.size,
                    order_type=OrderType.MARKET,
                )
            )
        elif z_score < -self.entry_z and self.current_position <= 0:
            orders.append(
                OrderRequest(
                    client_order_id=f"{event.timestamp.timestamp()}-buy",
                    symbol=self.symbol,
                    side=Side.BUY,
                    quantity=self.size,
                    order_type=OrderType.MARKET,
                )
            )
        elif abs(z_score) < self.exit_z and abs(self.current_position) > 1e-6:
            # Flatten position by trading opposite side.
            orders.append(
                OrderRequest(
                    client_order_id=f"{event.timestamp.timestamp()}-exit",
                    symbol=self.symbol,
                    side=Side.BUY if self.current_position < 0 else Side.SELL,
                    quantity=abs(self.current_position),
                    order_type=OrderType.MARKET,
                )
            )
        return orders

    def on_fill(self, fill: FillEvent) -> None:
        direction = 1 if fill.side == Side.BUY else -1
        self.current_position += direction * fill.quantity

    def on_stop(self) -> None:
        self.prices.clear()
        self.current_position = 0.0


__all__ = ["MeanReversionStrategy"]
