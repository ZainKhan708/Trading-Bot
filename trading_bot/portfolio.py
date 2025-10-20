"""Portfolio and PnL accounting utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple

from .events import FillEvent, MarketEvent, Side


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0

    def update(self, fill: FillEvent) -> float:
        direction = 1 if fill.side == Side.BUY else -1
        new_qty = self.quantity + direction * fill.quantity
        realized_pnl = 0.0

        if self.quantity == 0 or self.quantity * new_qty >= 0:
            # Increasing exposure or staying on same side
            total_cost = self.avg_price * abs(self.quantity) + fill.price * fill.quantity
            total_qty = abs(self.quantity) + fill.quantity
            self.avg_price = total_cost / total_qty if total_qty else 0.0
            self.quantity = new_qty
        else:
            # Closing or flipping position
            closing_qty = min(abs(self.quantity), fill.quantity)
            pnl_per_unit = self.avg_price - fill.price if fill.side == Side.SELL else fill.price - self.avg_price
            realized_pnl = closing_qty * pnl_per_unit
            residual_qty = direction * (fill.quantity - closing_qty)
            if residual_qty == 0:
                self.quantity = 0.0
                self.avg_price = 0.0
            else:
                self.quantity = residual_qty
                self.avg_price = fill.price
        return realized_pnl


@dataclass
class PortfolioState:
    """Tracks cash, positions, and trade history."""

    starting_cash: float
    cash: float = field(init=False)
    positions: Dict[str, Position] = field(default_factory=dict, init=False)
    realized_pnl: float = field(default=0.0, init=False)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list, init=False)
    trade_log: List[Dict[str, float]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.cash = self.starting_cash

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        return self.positions[symbol]

    def update_on_fill(self, fill: FillEvent) -> None:
        position = self.get_position(fill.symbol)
        pnl = position.update(fill)
        direction = 1 if fill.side == Side.SELL else -1
        self.cash += direction * fill.quantity * fill.price - fill.fees
        self.realized_pnl += pnl - fill.fees
        self.trade_log.append(
            {
                "timestamp": fill.timestamp.timestamp(),
                "symbol": fill.symbol,
                "side": 1 if fill.side == Side.BUY else -1,
                "quantity": fill.quantity,
                "price": fill.price,
                "fees": fill.fees,
                "realized_pnl": pnl - fill.fees,
            }
        )

    def mark_to_market(self, event: MarketEvent) -> None:
        equity = self.cash
        for position in self.positions.values():
            if position.quantity != 0:
                mid = event.midpoint
                equity += position.quantity * mid
        self.equity_curve.append((event.timestamp, equity))

    def snapshot(self) -> Dict[str, float]:
        latest_equity = self.equity_curve[-1][1] if self.equity_curve else self.cash
        return {
            "cash": self.cash,
            "equity": latest_equity,
            "realized_pnl": self.realized_pnl,
        }

    def reset(self) -> None:
        self.cash = self.starting_cash
        self.positions.clear()
        self.realized_pnl = 0.0
        self.equity_curve.clear()
        self.trade_log.clear()
