from __future__ import annotations

import asyncio
import contextlib
from decimal import Decimal
from typing import Optional

from trading_bot.account_state import AccountStateMirror
from trading_bot.models import AccountEquityPoint, AccountMetrics, ExposurePoint, TurnoverPoint
from trading_bot.storage import AnalyticsStorage


class AnalyticsEngine:
    """Consumes account updates to persist analytics artefacts."""

    def __init__(self, account_state: AccountStateMirror, storage: AnalyticsStorage) -> None:
        self._account_state = account_state
        self._storage = storage
        self._task: Optional[asyncio.Task[None]] = None
        self._last_turnover: Decimal = Decimal("0")
        self._latest_metrics: Optional[AccountMetrics] = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        async for _ in self._account_state.subscribe_events():
            metrics = await self._account_state.get_metrics()
            self._latest_metrics = metrics
            equity_point = AccountEquityPoint(
                timestamp=metrics.last_update,
                equity=metrics.equity,
                realized_pnl=metrics.realized_pnl,
                unrealized_pnl=metrics.unrealized_pnl,
            )
            await self._storage.store_equity_point(equity_point)

            exposures = [
                ExposurePoint(timestamp=metrics.last_update, symbol=symbol, exposure=exposure)
                for symbol, exposure in metrics.exposures.items()
            ]
            await self._storage.store_exposure_points(exposures)

            turnover_delta = metrics.turnover - self._last_turnover
            if turnover_delta != 0:
                await self._storage.store_turnover_point(
                    TurnoverPoint(timestamp=metrics.last_update, notional_traded=turnover_delta)
                )
                self._last_turnover = metrics.turnover

    @property
    def latest_metrics(self) -> Optional[AccountMetrics]:
        return self._latest_metrics
