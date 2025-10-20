"""Simple lock-free publish/subscribe utilities."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Iterator, List, MutableMapping, Optional, Tuple, TypeVar

from .events import L2Update, QuoteSnapshot, TradeEvent

T = TypeVar("T")


class EventBus:
    """A minimal lock-free queue based event bus."""

    def __init__(self) -> None:
        self._queue: "queue.SimpleQueue[T]" = queue.SimpleQueue()
        self._subscribers: List["queue.SimpleQueue[T]"] = []
        self._sub_lock = threading.Lock()

    def publish(self, event: T) -> None:
        """Publish an event to all subscribers."""

        self._queue.put(event)
        with self._sub_lock:
            subscribers = list(self._subscribers)
        for sub in subscribers:
            sub.put(event)

    def subscribe(self) -> Iterator[T]:
        """Create an iterator that yields events as they are published."""

        local_queue: "queue.SimpleQueue[T]" = queue.SimpleQueue()
        with self._sub_lock:
            self._subscribers.append(local_queue)
            while True:
                try:
                    local_queue.put(self._queue.get_nowait())
                except queue.Empty:
                    break
        try:
            while True:
                yield local_queue.get()
        finally:
            with self._sub_lock:
                self._subscribers.remove(local_queue)

    def drain(self) -> Iterator[T]:
        """Iterate over events that were emitted before any subscription existed."""

        while True:
            try:
                yield self._queue.get_nowait()
            except queue.Empty:
                break


@dataclass(slots=True)
class QuoteSnapshotBuilder:
    """Build quote snapshots from trade and level 2 events."""

    quotes: MutableMapping[str, QuoteSnapshot] = field(default_factory=dict)

    def apply(self, event: object) -> Optional[QuoteSnapshot]:
        if isinstance(event, QuoteSnapshot):
            self.quotes[event.symbol] = event
            return event
        if isinstance(event, L2Update):
            snapshot = QuoteSnapshot(
                symbol=event.symbol,
                bid_price=event.bids[0][0] if event.bids else 0.0,
                bid_size=event.bids[0][1] if event.bids else 0.0,
                ask_price=event.asks[0][0] if event.asks else 0.0,
                ask_size=event.asks[0][1] if event.asks else 0.0,
                ts_ns=event.ts_ns,
                received_ts_ns=event.received_ts_ns,
            )
            self.quotes[event.symbol] = snapshot
            return snapshot
        return None


@dataclass(slots=True)
class TradeAccumulator:
    """Aggregate the most recent trade per symbol."""

    trades: MutableMapping[str, TradeEvent] = field(default_factory=dict)

    def apply(self, event: object) -> Optional[TradeEvent]:
        if isinstance(event, TradeEvent):
            self.trades[event.symbol] = event
            return event
        return None


def snapshot_stream(bus: EventBus, *builders: QuoteSnapshotBuilder | TradeAccumulator) -> Iterator[Tuple[object, Tuple[Optional[QuoteSnapshot], Optional[TradeEvent]]]]:
    """Yield events alongside the latest snapshots."""

    quote_builder = next((b for b in builders if isinstance(b, QuoteSnapshotBuilder)), QuoteSnapshotBuilder())
    trade_builder = next((b for b in builders if isinstance(b, TradeAccumulator)), TradeAccumulator())

    for historical in bus.drain():
        quote_builder.apply(historical)
        trade_builder.apply(historical)
        yield historical, (quote_builder.quotes.get(getattr(historical, "symbol", "")), trade_builder.trades.get(getattr(historical, "symbol", "")))

    for event in bus.subscribe():
        quote_builder.apply(event)
        trade_builder.apply(event)
        yield event, (quote_builder.quotes.get(getattr(event, "symbol", "")), trade_builder.trades.get(getattr(event, "symbol", "")))
