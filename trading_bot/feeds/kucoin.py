"""Feed handler for KuCoin websocket messages."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from ..events import (
    L2Update,
    QuoteSnapshot,
    TradeEvent,
    book_top,
    normalise_book,
)
from ..utils.time import MonotonicTimestampGuard

KuCoinMessage = Dict[str, Any]


def _parse_timestamp(raw: Any) -> int:
    """Return a nanosecond timestamp from KuCoin payloads."""

    if raw is None:
        return time.time_ns()

    value = int(raw)
    if value > 1_000_000_000_000_000_000:
        return value
    if value > 1_000_000_000_000_000:
        return value * 1_000
    return value * 1_000_000


@dataclass(slots=True)
class KuCoinFeedHandler:
    """Normalises KuCoin websocket messages into internal events."""

    guard: MonotonicTimestampGuard

    def __init__(self, guard: Optional[MonotonicTimestampGuard] = None) -> None:
        self.guard = guard or MonotonicTimestampGuard()

    def _received_ts(self, provided_ts_ns: Optional[int]) -> int:
        return provided_ts_ns or time.time_ns()

    def parse(self, message: KuCoinMessage, received_ts_ns: Optional[int] = None) -> Tuple[Any, ...]:
        """Parse a websocket message into strongly-typed events."""

        subject = message.get("subject")
        data = message.get("data", {})
        if subject == "trade.l3match":
            return (self._parse_trade(data, received_ts_ns),)
        if subject in {"level2", "level2depth5", "level2depth50"}:
            l2 = self._parse_l2(data, received_ts_ns)
            quote = self._quote_from_l2(l2)
            return (l2, quote)
        if subject == "ticker":
            return (self._parse_quote(data, received_ts_ns),)
        return tuple()

    def _parse_trade(self, data: Dict[str, Any], received_ts_ns: Optional[int]) -> TradeEvent:
        ts_ns = self.guard.normalise(_parse_timestamp(data.get("ts")))
        return TradeEvent(
            symbol=data["symbol"],
            trade_id=str(data.get("tradeId", data.get("sequence")) or ""),
            side=str(data.get("side", "")),
            price=float(data.get("price", 0.0)),
            size=float(data.get("size", 0.0)),
            ts_ns=ts_ns,
            received_ts_ns=self._received_ts(received_ts_ns),
        )

    def _parse_l2(self, data: Dict[str, Any], received_ts_ns: Optional[int]) -> L2Update:
        raw_timestamp = data.get("time") or data.get("ts")
        ts_ns = self.guard.normalise(_parse_timestamp(raw_timestamp))
        changes = data.get("changes", {})
        bids = normalise_book(changes.get("bids", []) or data.get("bids", []))
        asks = normalise_book(changes.get("asks", []) or data.get("asks", []))
        return L2Update(
            symbol=data["symbol"],
            bids=bids,
            asks=asks,
            sequence_start=int(data.get("sequenceStart", data.get("sequence", 0))),
            sequence_end=int(data.get("sequenceEnd", data.get("sequence", 0))),
            ts_ns=ts_ns,
            received_ts_ns=self._received_ts(received_ts_ns),
        )

    def _parse_quote(self, data: Dict[str, Any], received_ts_ns: Optional[int]) -> QuoteSnapshot:
        ts_ns = self.guard.normalise(_parse_timestamp(data.get("ts") or data.get("time")))
        return QuoteSnapshot(
            symbol=data["symbol"],
            bid_price=float(data.get("bestBid", data.get("buy", 0.0))),
            bid_size=float(data.get("bestBidSize", data.get("buySize", 0.0))),
            ask_price=float(data.get("bestAsk", data.get("sell", 0.0))),
            ask_size=float(data.get("bestAskSize", data.get("sellSize", 0.0))),
            ts_ns=ts_ns,
            received_ts_ns=self._received_ts(received_ts_ns),
        )

    def _quote_from_l2(self, update: L2Update) -> QuoteSnapshot:
        bid_price, bid_size = book_top(update.bids)
        ask_price, ask_size = book_top(update.asks)
        return QuoteSnapshot(
            symbol=update.symbol,
            bid_price=bid_price,
            bid_size=bid_size,
            ask_price=ask_price,
            ask_size=ask_size,
            ts_ns=update.ts_ns,
            received_ts_ns=update.received_ts_ns,
        )
