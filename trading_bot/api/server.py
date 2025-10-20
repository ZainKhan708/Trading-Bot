from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from fastapi import FastAPI

from trading_bot.account_state import AccountStateMirror
from trading_bot.analytics import AnalyticsEngine
from trading_bot.models import Currency
from trading_bot.storage import AnalyticsStorage


def decimal_to_str(value: Decimal) -> str:
    return format(value, 'f')


def create_app(
    account_state: AccountStateMirror,
    analytics_engine: AnalyticsEngine,
    storage: AnalyticsStorage,
) -> FastAPI:
    app = FastAPI(title="Trading Bot Analytics API", version="1.0.0")

    @app.on_event("startup")
    async def _startup() -> None:
        await account_state.start()
        await analytics_engine.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await analytics_engine.stop()
        await account_state.stop()
        await storage.close()

    @app.get("/metrics/live")
    async def get_live_metrics() -> Dict[str, Any]:
        metrics = analytics_engine.latest_metrics
        if metrics is None:
            metrics = await account_state.get_metrics()
        return {
            "equity": decimal_to_str(metrics.equity),
            "realized_pnl": decimal_to_str(metrics.realized_pnl),
            "unrealized_pnl": decimal_to_str(metrics.unrealized_pnl),
            "total_fees": decimal_to_str(metrics.total_fees),
            "exposures": {symbol: decimal_to_str(size) for symbol, size in metrics.exposures.items()},
            "turnover": decimal_to_str(metrics.turnover),
            "last_update": metrics.last_update.isoformat(),
        }

    @app.get("/metrics/equity")
    async def get_equity_curve(limit: int = 500) -> List[Dict[str, Any]]:
        points = await storage.fetch_equity_curve(limit=limit)
        return [
            {
                "timestamp": point.timestamp.isoformat(),
                "equity": decimal_to_str(point.equity),
                "realized_pnl": decimal_to_str(point.realized_pnl),
                "unrealized_pnl": decimal_to_str(point.unrealized_pnl),
            }
            for point in points
        ]

    @app.get("/metrics/exposures")
    async def get_exposures(limit: int = 500) -> List[Dict[str, Any]]:
        points = await storage.fetch_exposure_history(limit=limit)
        return [
            {
                "timestamp": point.timestamp.isoformat(),
                "symbol": point.symbol,
                "exposure": decimal_to_str(point.exposure),
            }
            for point in points
        ]

    @app.get("/metrics/turnover")
    async def get_turnover(limit: int = 500) -> List[Dict[str, Any]]:
        points = await storage.fetch_turnover_history(limit=limit)
        return [
            {
                "timestamp": point.timestamp.isoformat(),
                "notional_traded": decimal_to_str(point.notional_traded),
            }
            for point in points
        ]

    @app.get("/metrics/fills")
    async def get_fill_breakdown() -> List[Dict[str, Any]]:
        breakdown = account_state.fill_breakdown()
        return [
            {
                "fill_id": fill_id,
                "realized_pnl": decimal_to_str(values[0]),
                "fee": decimal_to_str(values[1]),
                "slippage": decimal_to_str(values[2]),
            }
            for fill_id, values in breakdown.items()
        ]

    @app.get("/account/balances")
    async def get_balances() -> Dict[str, Dict[str, str]]:
        balances = account_state.balances
        return {
            currency.value: {
                "total": decimal_to_str(balance.total),
                "available": decimal_to_str(balance.available),
            }
            for currency, balance in balances.items()
        }

    @app.get("/account/positions")
    async def get_positions() -> List[Dict[str, Any]]:
        positions = account_state.positions
        return [
            {
                "symbol": position.symbol,
                "size": decimal_to_str(position.size),
                "entry_price": decimal_to_str(position.entry_price),
                "side": position.side,
            }
            for position in positions.values()
        ]

    @app.get("/account/funding-rates")
    async def get_funding_rates() -> List[Dict[str, Any]]:
        funding_rates = account_state.funding_rates
        return [
            {
                "symbol": rate.symbol,
                "rate": decimal_to_str(rate.rate),
                "next_funding_time": rate.next_funding_time.isoformat(),
            }
            for rate in funding_rates.values()
        ]

    return app
