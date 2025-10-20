"""Abstract exchange client definitions and in-memory implementation."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional

from .order import OrderRequest, OrderState, OrderStatus


@dataclass(slots=True)
class RestOrderResponse:
    """Response payload returned by the :class:`ExchangeRestClient`."""

    exchange_order_id: str
    client_order_id: str
    status: OrderStatus


class ExchangeRestClient(ABC):
    """Abstract REST client used by :class:`OrderManager`."""

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> RestOrderResponse:
        """Submit an order via REST and return the initial exchange response."""

    @abstractmethod
    async def cancel_order(self, client_order_id: str) -> RestOrderResponse:
        """Cancel an order by ``client_order_id`` returning the latest state."""

    @abstractmethod
    async def get_order_status(self, client_order_id: str) -> RestOrderResponse:
        """Query the current order state by ``client_order_id``."""

    @abstractmethod
    async def list_open_orders(self) -> Iterable[OrderState]:
        """Return an iterable of currently open orders on the exchange."""


class ExchangeWebsocketClient(ABC):
    """Abstract websocket client streaming private order updates."""

    @abstractmethod
    async def listen_private_orders(self) -> AsyncIterator[Dict[str, Any]]:
        """Yield private order updates with ``client_order_id`` and other fields."""

    @abstractmethod
    async def close(self) -> None:
        """Close the websocket connection."""


class InMemoryExchangeClient(ExchangeRestClient, ExchangeWebsocketClient):
    """A deterministic in-memory exchange used for tests and dry-runs."""

    def __init__(self, fill_latency: float = 0.2) -> None:
        self._orders: Dict[str, OrderState] = {}
        self._client_index: Dict[str, str] = {}
        self._ws_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self._fill_latency = fill_latency
        self._fills_task: Optional[asyncio.Task[None]] = None
        self._listeners = 0
        self._lock = asyncio.Lock()

    async def _ensure_fill_task(self) -> None:
        if self._fills_task and not self._fills_task.done():
            return

        async def _fill_worker() -> None:
            while True:
                await asyncio.sleep(self._fill_latency)
                for state in list(self._orders.values()):
                    if state.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}:
                        continue
                    fill_qty = min(1.0, state.request.quantity - state.cumulative_filled)
                    if fill_qty <= 0:
                        continue
                    state.apply_fill(fill_qty, state.request.price or 1.0)
                    await self._ws_queue.put(
                        {
                            "type": "fill",
                            "client_order_id": state.request.client_order_id,
                            "filled_qty": fill_qty,
                            "status": state.status.value,
                            "avg_fill_price": state.avg_fill_price,
                            "timestamp": time.time(),
                        }
                    )
                    if state.status is OrderStatus.FILLED:
                        await self._ws_queue.put(
                            {
                                "type": "done",
                                "client_order_id": state.request.client_order_id,
                                "status": state.status.value,
                                "timestamp": time.time(),
                            }
                        )

        self._fills_task = asyncio.create_task(_fill_worker())

    async def place_order(self, request: OrderRequest) -> RestOrderResponse:
        async with self._lock:
            exchange_id = uuid.uuid4().hex
            state = OrderState(request=request, exchange_order_id=exchange_id, status=OrderStatus.ACKED)
            state.acknowledged_at = time.time()
            state.last_update_ts = state.acknowledged_at
            self._orders[exchange_id] = state
            self._client_index[request.client_order_id] = exchange_id
        await self._ws_queue.put(
            {
                "type": "ack",
                "client_order_id": request.client_order_id,
                "exchange_order_id": exchange_id,
                "status": OrderStatus.ACKED.value,
                "timestamp": state.acknowledged_at,
            }
        )
        await self._ensure_fill_task()
        return RestOrderResponse(exchange_order_id=exchange_id, client_order_id=request.client_order_id, status=state.status)

    async def cancel_order(self, client_order_id: str) -> RestOrderResponse:
        async with self._lock:
            exchange_id = self._client_index.get(client_order_id)
            if exchange_id is None:
                raise ValueError(f"unknown client_order_id {client_order_id}")
            state = self._orders[exchange_id]
            state.mark_canceled()
        await self._ws_queue.put(
            {
                "type": "canceled",
                "client_order_id": client_order_id,
                "status": state.status.value,
                "timestamp": time.time(),
            }
        )
        return RestOrderResponse(exchange_order_id=exchange_id, client_order_id=client_order_id, status=state.status)

    async def get_order_status(self, client_order_id: str) -> RestOrderResponse:
        async with self._lock:
            exchange_id = self._client_index.get(client_order_id)
            if exchange_id is None:
                raise ValueError(f"unknown client_order_id {client_order_id}")
            state = self._orders[exchange_id]
            return RestOrderResponse(exchange_order_id=exchange_id, client_order_id=client_order_id, status=state.status)

    async def list_open_orders(self) -> Iterable[OrderState]:
        async with self._lock:
            return [state for state in self._orders.values() if state.status not in {OrderStatus.FILLED, OrderStatus.CANCELED}]

    async def listen_private_orders(self) -> AsyncIterator[Dict[str, Any]]:
        self._listeners += 1
        try:
            while True:
                update = await self._ws_queue.get()
                if update.get("type") == "closed":
                    break
                yield update
        finally:
            self._listeners -= 1

    async def close(self) -> None:
        if self._fills_task:
            self._fills_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._fills_task
        await self._ws_queue.put({"type": "closed"})


class LatencyTracker:
    """Keeps aggregated latency metrics across orders."""

    def __init__(self) -> None:
        self._latencies: Dict[str, List[float]] = defaultdict(list)

    def record(self, metric: str, latency: Optional[float]) -> None:
        if latency is None:
            return
        self._latencies[metric].append(latency)

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        result: Dict[str, Dict[str, float]] = {}
        for metric, values in self._latencies.items():
            if not values:
                continue
            result[metric] = {
                "count": len(values),
                "avg": sum(values) / len(values),
                "max": max(values),
                "min": min(values),
            }
        return result
