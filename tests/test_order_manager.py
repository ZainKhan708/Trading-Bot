import asyncio

import pytest

from trading_bot.exchange_client import InMemoryExchangeClient
from trading_bot.order import OrderRequest, OrderStatus, OrderType, TimeInForce, TriggerType
from trading_bot.order_manager import OrderManager


def run(coro):
    return asyncio.run(coro)


def test_place_order_idempotent():
    async def _run() -> None:
        rest_ws = InMemoryExchangeClient(fill_latency=0.5)
        manager = OrderManager(rest_ws, rest_ws)
        await manager.start()

        request = OrderRequest(symbol="BTC-USDT", side="buy", quantity=2.0, order_type=OrderType.LIMIT, price=25000.0)
        state = await manager.place_order(request)
        assert state.request.client_order_id == request.client_order_id
        assert state.status in {OrderStatus.PENDING_ACK, OrderStatus.ACKED}

        with pytest.raises(ValueError):
            await manager.place_order(request)

        await manager.stop()

    run(_run())


def test_child_order_slicing():
    async def _run() -> None:
        rest_ws = InMemoryExchangeClient(fill_latency=1.0)
        manager = OrderManager(rest_ws, rest_ws)
        await manager.start()

        parent_request = OrderRequest(
            symbol="ETH-USDT",
            side="sell",
            quantity=10.0,
            order_type=OrderType.LIMIT,
            price=2000.0,
            time_in_force=TimeInForce.GTX,
            post_only=True,
        )
        children = await manager.place_child_orders(parent_request, max_child_qty=4.0, child_spacing=1.0)
        assert len(children) == 3
        assert all(child.request.parent_client_order_id == parent_request.client_order_id for child in children)
        assert all(child.request.post_only for child in children)

        await manager.stop()

    run(_run())


def test_oco_bracket_reduce_only():
    async def _run() -> None:
        rest_ws = InMemoryExchangeClient(fill_latency=1.0)
        manager = OrderManager(rest_ws, rest_ws)
        await manager.start()

        primary = OrderRequest(symbol="SOL-USDT", side="buy", quantity=5.0, order_type=OrderType.LIMIT, price=25.0)
        contingent = [
            (TriggerType.TAKE_PROFIT, 30.0, 5.0),
            (TriggerType.STOP_LOSS, 22.0, 5.0),
        ]
        states = await manager.place_oco_order(primary, contingent)
        assert len(states) == 3
        for cid, state in states.items():
            if cid == primary.client_order_id:
                continue
            assert state.request.reduce_only
            assert state.request.parent_client_order_id == primary.client_order_id

        await manager.stop()

    run(_run())


def test_cancel_on_stop():
    async def _run() -> None:
        rest_ws = InMemoryExchangeClient(fill_latency=5.0)
        manager = OrderManager(rest_ws, rest_ws, cancel_on_disconnect=True)
        await manager.start()

        request = OrderRequest(symbol="BTC-USDT", side="buy", quantity=1.0, order_type=OrderType.LIMIT, price=20000.0)
        state = await manager.place_order(request)
        assert state.status in {OrderStatus.PENDING_ACK, OrderStatus.ACKED}

        await manager.stop()

        refreshed = await rest_ws.get_order_status(request.client_order_id)
        assert refreshed.status is OrderStatus.CANCELED

    run(_run())


def test_latency_tracking_records_ack_and_fill():
    async def _run() -> None:
        rest_ws = InMemoryExchangeClient(fill_latency=0.1)
        manager = OrderManager(rest_ws, rest_ws)
        await manager.start()

        request = OrderRequest(symbol="BTC-USDT", side="buy", quantity=1.0, order_type=OrderType.LIMIT, price=20500.0)
        await manager.place_order(request)

        await asyncio.sleep(0.4)

        snapshot = await manager.snapshot()
        latency = snapshot["latency"]
        assert "ack" in latency
        assert "first_fill" in latency

        await manager.stop()

    run(_run())
