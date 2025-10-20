"""Event models for the trading bot data pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


SerializableTuple = Tuple[float, float]
SerializableBook = Tuple[SerializableTuple, ...]


@dataclass(frozen=True, slots=True)
class TradeEvent:
    """Immutable representation of a trade coming from an exchange feed."""

    symbol: str
    trade_id: str
    side: str
    price: float
    size: float
    ts_ns: int
    received_ts_ns: int

    def to_dict(self) -> Dict[str, object]:
        """Convert the event into a JSON-serialisable dictionary."""

        return {
            "type": "trade",
            "symbol": self.symbol,
            "trade_id": self.trade_id,
            "side": self.side,
            "price": self.price,
            "size": self.size,
            "ts_ns": self.ts_ns,
            "received_ts_ns": self.received_ts_ns,
        }


@dataclass(frozen=True, slots=True)
class L2Update:
    """Immutable level 2 order-book update."""

    symbol: str
    bids: SerializableBook
    asks: SerializableBook
    sequence_start: int
    sequence_end: int
    ts_ns: int
    received_ts_ns: int

    def to_dict(self) -> Dict[str, object]:
        """Convert the update into a JSON-serialisable dictionary."""

        return {
            "type": "l2",
            "symbol": self.symbol,
            "bids": [list(level) for level in self.bids],
            "asks": [list(level) for level in self.asks],
            "sequence_start": self.sequence_start,
            "sequence_end": self.sequence_end,
            "ts_ns": self.ts_ns,
            "received_ts_ns": self.received_ts_ns,
        }


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    """Immutable best bid/ask snapshot."""

    symbol: str
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    ts_ns: int
    received_ts_ns: int

    def to_dict(self) -> Dict[str, object]:
        """Convert the snapshot into a JSON-serialisable dictionary."""

        return {
            "type": "quote",
            "symbol": self.symbol,
            "bid_price": self.bid_price,
            "bid_size": self.bid_size,
            "ask_price": self.ask_price,
            "ask_size": self.ask_size,
            "ts_ns": self.ts_ns,
            "received_ts_ns": self.received_ts_ns,
        }


def normalise_book(levels: Sequence[Sequence[object]]) -> SerializableBook:
    """Normalise book levels to immutable tuples of floats."""

    normalised: List[SerializableTuple] = []
    for price, size, *_ in levels:
        normalised.append((float(price), float(size)))
    return tuple(normalised)


def empty_book() -> SerializableBook:
    """Return an empty book representation."""

    return tuple()


def book_top(levels: SerializableBook) -> SerializableTuple:
    """Return the best level from a book."""

    if not levels:
        return 0.0, 0.0
    return levels[0]
