"""Execution engine implementations."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List

from .events import FillEvent, MarketEvent, OrderRequest, OrderType, Side
from .interfaces import ExecutionEngine


@dataclass
class PendingLimitOrder:
    order: OrderRequest
    arrival_time: datetime
    queue_position: float
    remaining_qty: float


class SimulatedExecutionEngine(ExecutionEngine):
    """Simulate execution with queue position and market impact modelling."""

    def __init__(
        self,
        latency_ms: float = 25.0,
        impact_coefficient: float = 0.15,
        queue_resilience: float = 0.6,
        random_seed: int | None = None,
    ) -> None:
        self.latency = timedelta(milliseconds=latency_ms)
        self.impact_coefficient = impact_coefficient
        self.queue_resilience = queue_resilience
        self.random = random.Random(random_seed)
        self.pending_limits: List[PendingLimitOrder] = []
        self.order_counter = 0

    def reset(self) -> None:
        self.pending_limits.clear()
        self.order_counter = 0

    def submit(self, order: OrderRequest, event: MarketEvent) -> Iterable[FillEvent]:
        if order.order_type == OrderType.MARKET:
            return [self._fill_market_order(order, event)]
        if order.order_type in {OrderType.LIMIT, OrderType.STOP}:
            queue_position = self._estimate_queue_position(order, event)
            self.pending_limits.append(
                PendingLimitOrder(
                    order=order,
                    arrival_time=event.timestamp + self.latency,
                    queue_position=queue_position,
                    remaining_qty=order.quantity,
                )
            )
            return []
        raise ValueError(f"Unsupported order type: {order.order_type}")

    def on_market_data(self, event: MarketEvent) -> Iterable[FillEvent]:
        fills: List[FillEvent] = []
        updated_pending: List[PendingLimitOrder] = []
        for pending in self.pending_limits:
            if pending.arrival_time > event.timestamp:
                updated_pending.append(pending)
                continue

            fill = self._maybe_fill_limit(pending, event)
            if fill is not None:
                fills.append(fill)
            else:
                updated_pending.append(pending)
        self.pending_limits = updated_pending
        return fills

    def _fill_market_order(self, order: OrderRequest, event: MarketEvent) -> FillEvent:
        side = order.side
        qty = order.quantity
        book_liquidity = event.ask_size if side == Side.BUY else event.bid_size
        price = event.ask if side == Side.BUY else event.bid
        impact = self.impact_coefficient * (qty / max(book_liquidity, 1e-6))
        adjusted_price = price * (1 + impact) if side == Side.BUY else price * (1 - impact)
        timestamp = event.timestamp + self.latency
        fees = price * qty * 0.0002
        liquidity_flag = "Taker"
        return FillEvent(
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=side,
            quantity=qty,
            price=adjusted_price,
            timestamp=timestamp,
            liquidity=liquidity_flag,
            fees=fees,
            metadata={
                "market_price": price,
                "impact": impact,
            },
        )

    def _estimate_queue_position(self, order: OrderRequest, event: MarketEvent) -> float:
        depth = event.ask_size if order.side == Side.BUY else event.bid_size
        # Estimate existing queue as a function of displayed depth plus latency leakage.
        queue = depth * (1 + self.queue_resilience * self.random.random())
        return queue

    def _maybe_fill_limit(self, pending: PendingLimitOrder, event: MarketEvent) -> FillEvent | None:
        order = pending.order
        price_crossed = (
            (order.side == Side.BUY and event.ask <= (order.price or event.ask))
            or (order.side == Side.SELL and event.bid >= (order.price or event.bid))
        )
        if not price_crossed and order.order_type == OrderType.LIMIT:
            return None
        executed_volume = self._estimate_executed_volume(order, event)
        if executed_volume <= pending.queue_position:
            pending.queue_position = max(pending.queue_position - executed_volume, 0.0)
            return None
        available = executed_volume - pending.queue_position
        filled_qty = min(pending.remaining_qty, max(available, 0.0))
        if filled_qty <= 0:
            return None
        fees = (order.price or event.midpoint) * filled_qty * 0.00005
        pending.remaining_qty -= filled_qty
        liquidity_flag = "Maker"
        fill_price = order.price if order.price is not None else event.midpoint
        if pending.remaining_qty > 0:
            pending.queue_position = 0.0
        else:
            pending.queue_position = math.inf
        return FillEvent(
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=filled_qty,
            price=fill_price,
            timestamp=max(event.timestamp, pending.arrival_time),
            liquidity=liquidity_flag,
            fees=fees,
            metadata={
                "executed_volume": executed_volume,
                "queue_position": pending.queue_position,
            },
        )

    def _estimate_executed_volume(self, order: OrderRequest, event: MarketEvent) -> float:
        traded = max(event.last_size, 0.0)
        if traded == 0:
            traded = (event.ask_size if order.side == Side.BUY else event.bid_size) * 0.05
        noise = 0.1 * traded * (self.random.random() - 0.5)
        return max(traded + noise, 0.0)


__all__ = ["SimulatedExecutionEngine"]
