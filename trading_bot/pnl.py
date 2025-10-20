from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Dict, Tuple

from trading_bot.models import Fill, Position

getcontext().prec = 16


class PnLCalculator:
    """Calculates realized and unrealized PnL, fees, and slippage for fills."""

    def __init__(self) -> None:
        self._realized_pnl: Decimal = Decimal("0")
        self._position_sizes: Dict[str, Decimal] = {}
        self._avg_prices: Dict[str, Decimal] = {}
        self._mid_prices: Dict[str, Decimal] = {}
        self._fees: Dict[str, Decimal] = {}
        self._fill_breakdown: Dict[str, Tuple[Decimal, Decimal, Decimal]] = {}

    def update_mid_price(self, symbol: str, mid_price: Decimal) -> None:
        self._mid_prices[symbol] = mid_price

    def process_fill(self, fill: Fill) -> Tuple[Decimal, Decimal, Decimal]:
        """Process a fill and return realized pnl, fee, slippage."""

        signed_size = fill.size if fill.side.lower() == "buy" else -fill.size
        prior_size = self._position_sizes.get(fill.symbol, Decimal("0"))
        avg_price = self._avg_prices.get(fill.symbol, Decimal("0"))

        same_direction = prior_size == 0 or (prior_size > 0 and signed_size > 0) or (prior_size < 0 and signed_size < 0)

        realized_pnl = Decimal("0")
        if same_direction:
            new_size = prior_size + signed_size
            total_notional = avg_price * prior_size + fill.price * signed_size
            if new_size != 0:
                self._avg_prices[fill.symbol] = total_notional / new_size
            else:
                self._avg_prices[fill.symbol] = Decimal("0")
        else:
            closing_qty = min(abs(signed_size), abs(prior_size))
            direction = Decimal("1") if prior_size > 0 else Decimal("-1")
            realized_pnl = (fill.price - avg_price) * closing_qty * direction
            self._realized_pnl += realized_pnl - fill.fee

            if abs(signed_size) > abs(prior_size):
                residual = prior_size + signed_size
                new_size = residual
                self._avg_prices[fill.symbol] = fill.price if residual != 0 else Decimal("0")
            else:
                new_size = prior_size + signed_size
                self._avg_prices[fill.symbol] = avg_price if new_size != 0 else Decimal("0")

        self._position_sizes[fill.symbol] = new_size
        self._fees[fill.symbol] = self._fees.get(fill.symbol, Decimal("0")) + fill.fee

        mid_price = self._mid_prices.get(fill.symbol, fill.price)
        side_multiplier = Decimal("1") if fill.side.lower() == "buy" else Decimal("-1")
        slippage = (fill.price - mid_price) * side_multiplier

        breakdown = (realized_pnl, fill.fee, slippage)
        self._fill_breakdown[fill.fill_id] = breakdown
        return breakdown

    def current_pnl(self, positions: Dict[str, Position], mid_prices: Dict[str, Decimal]) -> Tuple[Decimal, Decimal]:
        unrealized = Decimal("0")
        for symbol, position in positions.items():
            mid_price = mid_prices.get(symbol) or self._mid_prices.get(symbol)
            if mid_price is None:
                continue
            direction = Decimal("1") if position.side.lower() == "long" else Decimal("-1")
            unrealized += (mid_price - position.entry_price) * position.size * direction
        return self._realized_pnl, unrealized

    def fill_breakdown(self) -> Dict[str, Tuple[Decimal, Decimal, Decimal]]:
        """Return cached realized PnL, fee, and slippage per fill."""

        return dict(self._fill_breakdown)
