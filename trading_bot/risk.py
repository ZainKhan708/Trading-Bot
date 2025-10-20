"""Risk management primitives."""
from __future__ import annotations

from dataclasses import dataclass

from .events import FillEvent, OrderRequest, Side
from .interfaces import RiskManager
from .portfolio import PortfolioState, Position


@dataclass
class BasicRiskManager(RiskManager):
    """Simple notional and position limits."""

    portfolio: PortfolioState
    max_position: float = 10_000.0
    max_notional: float = 250_000.0

    def reset(self) -> None:
        # No-op: portfolio reset is handled externally.
        return None

    def approve(self, order: OrderRequest) -> bool:
        position = self.portfolio.get_position(order.symbol)
        direction = 1 if order.side == Side.BUY else -1
        projected_qty = position.quantity + direction * order.quantity
        if abs(projected_qty) > self.max_position:
            return False
        price = order.price or self._infer_price(position)
        if price and price * order.quantity > self.max_notional:
            return False
        return True

    def _infer_price(self, position: Position) -> float:
        if position.avg_price > 0:
            return position.avg_price
        return 0.0

    def on_fill(self, fill: FillEvent) -> None:
        # Portfolio updates maintain risk metrics implicitly.
        return None


__all__ = ["BasicRiskManager"]
