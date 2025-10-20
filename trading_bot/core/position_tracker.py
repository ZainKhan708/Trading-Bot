"""Position tracking and exposure calculation utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, Optional


class PositionType(str, Enum):
    """Supported position types."""

    SPOT = "spot"
    PERPETUAL = "perpetual"


@dataclass
class Position:
    """Represents a single trading position."""

    symbol: str
    position_type: PositionType
    quantity: float
    mark_price: float
    contract_size: float = 1.0

    @property
    def notional(self) -> float:
        """Return the notional exposure of the position in quote currency."""
        exposure = self.quantity * self.mark_price * self.contract_size
        return exposure

    def as_dict(self) -> Dict[str, float | str]:
        return {
            "symbol": self.symbol,
            "type": self.position_type.value,
            "quantity": self.quantity,
            "mark_price": self.mark_price,
            "contract_size": self.contract_size,
            "notional": self.notional,
        }


@dataclass
class PositionTracker:
    """Tracks positions across spot and derivatives markets."""

    positions: Dict[str, Dict[PositionType, Position]] = field(default_factory=dict)

    def upsert(self, position: Position) -> None:
        """Insert or update a position entry."""
        symbol_positions = self.positions.setdefault(position.symbol, {})
        symbol_positions[position.position_type] = position

    def remove(self, symbol: str, position_type: PositionType) -> None:
        """Remove a position. Deletes the symbol bucket if empty."""
        symbol_positions = self.positions.get(symbol)
        if not symbol_positions:
            return
        symbol_positions.pop(position_type, None)
        if not symbol_positions:
            self.positions.pop(symbol, None)

    def iter_positions(self) -> Iterable[Position]:
        for symbol_positions in self.positions.values():
            for position in symbol_positions.values():
                yield position

    def consolidated_notional(self, symbol: Optional[str] = None) -> float:
        """Return the total notional exposure for a symbol or entire book."""
        if symbol is not None:
            symbol_positions = self.positions.get(symbol, {})
            return sum(p.notional for p in symbol_positions.values())
        return sum(p.notional for p in self.iter_positions())

    def net_position(self, symbol: str) -> float:
        """Compute the net signed quantity across spot and derivatives."""
        symbol_positions = self.positions.get(symbol, {})
        return sum(p.quantity * p.contract_size for p in symbol_positions.values())

    def report(self) -> Dict[str, Dict[str, float]]:
        """Return a human-friendly summary of exposure per symbol."""
        summary: Dict[str, Dict[str, float]] = {}
        for symbol, symbol_positions in self.positions.items():
            summary[symbol] = {
                position_type.value: position.notional
                for position_type, position in symbol_positions.items()
            }
            summary[symbol]["total"] = sum(summary[symbol].values())
            summary[symbol]["net_quantity"] = self.net_position(symbol)
        summary["_total_notional"] = self.consolidated_notional()
        return summary
