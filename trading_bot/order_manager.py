"""Order management orchestrating REST/WS interactions for advanced flows."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import uuid
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional, Tuple

from .exchange_client import ExchangeRestClient, ExchangeWebsocketClient, LatencyTracker
from .order import (
    OrderRequest,
    OrderState,
    OrderStatus,
    OrderType,
    TimeInForce,
    TriggerType,
)

logger = logging.getLogger(__name__)


class OrderManager:
    """Coordinates REST and websocket clients to maintain live order state."""

    def __init__(
        self,
        rest_client: ExchangeRestClient,
        ws_client: ExchangeWebsocketClient,
        cancel_on_disconnect: bool = True,
    ) -> None:
        self._rest_client = rest_client
        self._ws_client = ws_client
        self._cancel_on_disconnect = cancel_on_disconnect
        self._orders: Dict[str, OrderState] = {}
        self._ws_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._latency_tracker = LatencyTracker()
        self._lock = asyncio.Lock()

    @property
    def latency_tracker(self) -> LatencyTracker:
        return self._latency_tracker

    async def start(self) -> None:
        """Start background websocket consumer and recover open orders."""

        await self.recover_open_orders()
        self._stop_event.clear()
        self._ws_task = asyncio.create_task(self._consume_private_ws())

    async def stop(self) -> None:
        """Stop background tasks and optionally cancel open orders."""

        self._stop_event.set()
        if self._ws_task:
            await self._ws_client.close()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ws_task
        if self._cancel_on_disconnect:
            await self._cancel_all_open_orders()

    async def _cancel_all_open_orders(self) -> None:
        async with self._lock:
            open_orders = [state for state in self._orders.values() if state.status not in {OrderStatus.FILLED, OrderStatus.CANCELED}]
        for state in open_orders:
            try:
                await self._rest_client.cancel_order(state.request.client_order_id)
            except Exception:  # pragma: no cover - log but ignore
                logger.exception("Failed to cancel order %s during shutdown", state.request.client_order_id)

    async def _consume_private_ws(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                async for message in self._ws_client.listen_private_orders():
                    await self._handle_ws_message(message)
                # Clean exit if generator finishes
                break
            except Exception as exc:  # pragma: no cover - network exceptions
                logger.warning("Websocket consumer error: %s", exc)
                if self._cancel_on_disconnect:
                    await self._cancel_all_open_orders()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def _handle_ws_message(self, message: Dict[str, Any]) -> None:
        client_order_id = message.get("client_order_id")
        if client_order_id is None:
            return
        async with self._lock:
            state = self._orders.get(client_order_id)
        if state is None:
            return
        msg_type = message.get("type")
        timestamp = message.get("timestamp")
        if msg_type == "ack":
            exchange_order_id = message.get("exchange_order_id", state.exchange_order_id or uuid.uuid4().hex)
            state.mark_acknowledged(exchange_order_id, timestamp)
            self._latency_tracker.record("ack", state.latency_to_ack())
        elif msg_type == "fill":
            fill_qty = float(message.get("filled_qty", 0))
            fill_price = float(message.get("fill_price", message.get("avg_fill_price", state.request.price or 0.0)))
            state.apply_fill(fill_qty, fill_price, timestamp)
            self._latency_tracker.record("first_fill", state.latency_to_fill())
        elif msg_type in {"canceled", "done"}:
            state.mark_canceled(timestamp)
        elif msg_type == "rejected":
            state.mark_rejected(timestamp)
        async with self._lock:
            self._orders[state.request.client_order_id] = state

    async def recover_open_orders(self) -> None:
        """Recover exchange open orders and seed the local cache."""

        open_orders = await self._rest_client.list_open_orders()
        async with self._lock:
            for state in open_orders:
                self._orders[state.request.client_order_id] = state

    async def place_order(self, request: OrderRequest) -> OrderState:
        """Place a single order ensuring idempotent client IDs."""

        async with self._lock:
            if request.client_order_id in self._orders:
                raise ValueError(f"Duplicate client order id {request.client_order_id}")
            self._orders[request.client_order_id] = OrderState(request=request, status=OrderStatus.PENDING_ACK)
        response = await self._rest_client.place_order(request)
        state = await self._sync_status_from_rest(response)
        return state

    async def cancel_order(self, client_order_id: str) -> OrderState:
        response = await self._rest_client.cancel_order(client_order_id)
        return await self._sync_status_from_rest(response)

    async def get_order(self, client_order_id: str) -> OrderState:
        response = await self._rest_client.get_order_status(client_order_id)
        return await self._sync_status_from_rest(response)

    async def _sync_status_from_rest(self, response: Any) -> OrderState:
        async with self._lock:
            state = self._orders.get(response.client_order_id)
            if not state:
                raise ValueError(f"Unknown client order id {response.client_order_id}")
            if response.status == OrderStatus.CANCELED:
                state.mark_canceled()
            elif response.status == OrderStatus.REJECTED:
                state.mark_rejected()
            elif response.status == OrderStatus.ACKED:
                state.mark_acknowledged(response.exchange_order_id)
            return state

    async def place_child_orders(
        self,
        base_request: OrderRequest,
        max_child_qty: float,
        child_spacing: float = 0.0,
    ) -> List[OrderState]:
        """Slice a large order into child orders honoring idempotency."""

        num_children = max(1, math.ceil(base_request.quantity / max_child_qty))
        child_qty = base_request.quantity / num_children
        child_states: List[OrderState] = []
        for index in range(num_children):
            child_request = OrderRequest(
                symbol=base_request.symbol,
                side=base_request.side,
                quantity=round(child_qty, 8),
                order_type=base_request.order_type,
                price=(base_request.price + index * child_spacing) if base_request.price is not None else None,
                time_in_force=base_request.time_in_force,
                post_only=base_request.post_only,
                reduce_only=base_request.reduce_only,
                trigger_type=base_request.trigger_type,
                trigger_price=base_request.trigger_price,
                parent_client_order_id=base_request.client_order_id,
            )
            state = await self.place_order(child_request)
            child_states.append(state)
        return child_states

    async def place_oco_order(
        self,
        primary: OrderRequest,
        contingent: Iterable[Tuple[TriggerType, float, float]],
    ) -> Dict[str, OrderState]:
        """Submit an OCO bracket with optional TP/SL legs."""

        states: Dict[str, OrderState] = {}
        primary_state = await self.place_order(primary)
        states[primary_state.request.client_order_id] = primary_state
        for trigger_type, trigger_price, qty in contingent:
            leg_request = OrderRequest(
                symbol=primary.symbol,
                side="sell" if primary.side == "buy" else "buy",
                quantity=qty,
                order_type=OrderType.STOP_LIMIT if trigger_type is TriggerType.STOP_LOSS else OrderType.LIMIT,
                price=trigger_price,
                trigger_type=trigger_type,
                trigger_price=trigger_price,
                time_in_force=TimeInForce.GTC,
                reduce_only=True,
                parent_client_order_id=primary.client_order_id,
            )
            leg_state = await self.place_order(leg_request)
            states[leg_request.client_order_id] = leg_state
        return states

    async def order_stream(self) -> AsyncIterator[OrderState]:
        """Yield state updates for observers."""

        queue: "asyncio.Queue[str]" = asyncio.Queue()

        async def _listen() -> None:
            while True:
                await asyncio.sleep(0.5)
                async with self._lock:
                    for state in self._orders.values():
                        await queue.put(state.request.client_order_id)
                if self._stop_event.is_set():
                    break

        listener = asyncio.create_task(_listen())
        try:
            while True:
                client_order_id = await queue.get()
                async with self._lock:
                    state = self._orders.get(client_order_id)
                if state:
                    yield state
        finally:
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener

    async def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of order states and latencies."""

        async with self._lock:
            return {
                "orders": {
                    cid: {
                        "status": state.status.value,
                        "filled": state.cumulative_filled,
                        "avg_fill_price": state.avg_fill_price,
                        "reduce_only": state.request.reduce_only,
                        "post_only": state.request.post_only,
                        "trigger_type": state.request.trigger_type.value,
                    }
                    for cid, state in self._orders.items()
                },
                "latency": self._latency_tracker.snapshot(),
            }


