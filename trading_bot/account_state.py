from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
from decimal import Decimal
from typing import AsyncIterator, Dict, Optional, Tuple

from trading_bot.data.rest_client import RESTClientProtocol
from trading_bot.data.ws_client import WebSocketClientProtocol
from trading_bot.models import (
    AccountMetrics,
    AccountSnapshot,
    Balance,
    BalanceUpdate,
    Currency,
    Fill,
    FundingRate,
    FundingRateUpdate,
    MidPriceUpdate,
    Position,
    PositionUpdate,
)
from trading_bot.pnl import PnLCalculator


class AccountStateMirror:
    """Maintains account state using an initial REST snapshot and websocket deltas."""

    def __init__(
        self,
        rest_client: RESTClientProtocol,
        ws_client: WebSocketClientProtocol,
        pnl_calculator: PnLCalculator,
    ) -> None:
        self._rest_client = rest_client
        self._ws_client = ws_client
        self._pnl_calculator = pnl_calculator
        self._balances: Dict[Currency, Balance] = {}
        self._positions: Dict[str, Position] = {}
        self._funding_rates: Dict[str, FundingRate] = {}
        self._mid_prices: Dict[str, Decimal] = {}
        self._fees_paid: Decimal = Decimal("0")
        self._turnover: Decimal = Decimal("0")
        self._last_update: Optional[dt.datetime] = None
        self._task: Optional[asyncio.Task[None]] = None
        self._metrics_lock = asyncio.Lock()
        self._event_queue: asyncio.Queue[object] = asyncio.Queue()

    async def start(self) -> None:
        """Fetch the initial snapshot and start processing websocket deltas."""

        snapshot = await self._rest_client.fetch_account_snapshot()
        self._apply_snapshot(snapshot)
        self._event_queue.put_nowait(snapshot)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        async for update in self._ws_client.subscribe():
            await self._process_update(update)
            self._event_queue.put_nowait(update)

    async def _process_update(self, update: object) -> None:
        async with self._metrics_lock:
            if isinstance(update, BalanceUpdate):
                self._balances[update.balance.currency] = update.balance
            elif isinstance(update, PositionUpdate):
                self._positions[update.position.symbol] = update.position
            elif isinstance(update, FundingRateUpdate):
                self._funding_rates[update.funding_rate.symbol] = update.funding_rate
            elif isinstance(update, MidPriceUpdate):
                self._mid_prices[update.symbol] = update.mid_price
                self._pnl_calculator.update_mid_price(update.symbol, update.mid_price)
            elif isinstance(update, Fill):
                self._pnl_calculator.process_fill(update)
                self._turnover += abs(update.price * update.size)
                self._fees_paid += update.fee
            else:
                raise ValueError(f"Unsupported update type: {type(update)!r}")
            self._last_update = dt.datetime.utcnow()

    def _apply_snapshot(self, snapshot: AccountSnapshot) -> None:
        self._balances.update(snapshot.balances)
        self._positions.update(snapshot.positions)
        self._funding_rates.update(snapshot.funding_rates)

    async def get_metrics(self) -> AccountMetrics:
        async with self._metrics_lock:
            realized_pnl, unrealized_pnl = self._pnl_calculator.current_pnl(
                self._positions, self._mid_prices
            )
            equity = sum(balance.total for balance in self._balances.values()) + realized_pnl + unrealized_pnl
            exposures = {symbol: position.size for symbol, position in self._positions.items()}
            return AccountMetrics(
                equity=equity,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                total_fees=self._fees_paid,
                exposures=exposures,
                turnover=self._turnover,
                last_update=self._last_update or dt.datetime.utcnow(),
            )

    async def subscribe_events(self) -> AsyncIterator[object]:
        """Provide an async iterator of processed updates for downstream analytics."""

        while True:
            update = await self._event_queue.get()
            yield update

    def fill_breakdown(self) -> Dict[str, Tuple[Decimal, Decimal, Decimal]]:
        return self._pnl_calculator.fill_breakdown()


__all__ = ["AccountStateMirror"]
