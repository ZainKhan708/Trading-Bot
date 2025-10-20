from __future__ import annotations

import asyncio
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Iterable, List

from trading_bot.models import AccountEquityPoint, ExposurePoint, TurnoverPoint


class AnalyticsStorage:
    async def store_equity_point(self, point: AccountEquityPoint) -> None:
        raise NotImplementedError

    async def store_exposure_points(self, points: Iterable[ExposurePoint]) -> None:
        raise NotImplementedError

    async def store_turnover_point(self, point: TurnoverPoint) -> None:
        raise NotImplementedError

    async def fetch_equity_curve(self, limit: int = 1000) -> List[AccountEquityPoint]:
        raise NotImplementedError

    async def fetch_exposure_history(self, limit: int = 1000) -> List[ExposurePoint]:
        raise NotImplementedError

    async def fetch_turnover_history(self, limit: int = 1000) -> List[TurnoverPoint]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class SQLiteAnalyticsStorage(AnalyticsStorage):
    def __init__(self, path: Path | str = "analytics.db") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS equity_curve (
                timestamp TEXT PRIMARY KEY,
                equity TEXT NOT NULL,
                realized_pnl TEXT NOT NULL,
                unrealized_pnl TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exposures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                exposure TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turnover (
                timestamp TEXT PRIMARY KEY,
                notional_traded TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        self._lock = asyncio.Lock()

    async def store_equity_point(self, point: AccountEquityPoint) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO equity_curve(timestamp, equity, realized_pnl, unrealized_pnl) VALUES (?, ?, ?, ?)",
                (
                    point.timestamp.isoformat(),
                    str(point.equity),
                    str(point.realized_pnl),
                    str(point.unrealized_pnl),
                ),
            )
            await asyncio.to_thread(self._conn.commit)

    async def store_exposure_points(self, points: Iterable[ExposurePoint]) -> None:
        rows = [
            (point.timestamp.isoformat(), point.symbol, str(point.exposure))
            for point in points
        ]
        if not rows:
            return
        async with self._lock:
            await asyncio.to_thread(
                self._conn.executemany,
                "INSERT INTO exposures(timestamp, symbol, exposure) VALUES (?, ?, ?)",
                rows,
            )
            await asyncio.to_thread(self._conn.commit)

    async def store_turnover_point(self, point: TurnoverPoint) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO turnover(timestamp, notional_traded) VALUES (?, ?)",
                (point.timestamp.isoformat(), str(point.notional_traded)),
            )
            await asyncio.to_thread(self._conn.commit)

    async def fetch_equity_curve(self, limit: int = 1000) -> List[AccountEquityPoint]:
        cursor = await asyncio.to_thread(
            self._conn.execute,
            "SELECT timestamp, equity, realized_pnl, unrealized_pnl FROM equity_curve ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await asyncio.to_thread(cursor.fetchall)
        return [
            AccountEquityPoint(
                timestamp=_parse_ts(row[0]),
                equity=Decimal(row[1]),
                realized_pnl=Decimal(row[2]),
                unrealized_pnl=Decimal(row[3]),
            )
            for row in rows
        ]

    async def fetch_exposure_history(self, limit: int = 1000) -> List[ExposurePoint]:
        cursor = await asyncio.to_thread(
            self._conn.execute,
            "SELECT timestamp, symbol, exposure FROM exposures ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await asyncio.to_thread(cursor.fetchall)
        return [
            ExposurePoint(
                timestamp=_parse_ts(row[0]),
                symbol=row[1],
                exposure=Decimal(row[2]),
            )
            for row in rows
        ]

    async def fetch_turnover_history(self, limit: int = 1000) -> List[TurnoverPoint]:
        cursor = await asyncio.to_thread(
            self._conn.execute,
            "SELECT timestamp, notional_traded FROM turnover ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await asyncio.to_thread(cursor.fetchall)
        return [
            TurnoverPoint(
                timestamp=_parse_ts(row[0]),
                notional_traded=Decimal(row[1]),
            )
            for row in rows
        ]

    async def close(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._conn.close)


def _parse_ts(value: str) -> "datetime.datetime":
    import datetime as dt

    return dt.datetime.fromisoformat(value)
