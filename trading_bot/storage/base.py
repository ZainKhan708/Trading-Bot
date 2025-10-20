"""Shared logic for partitioned event persistence."""

from __future__ import annotations

import datetime as dt
import json
import re
import threading
from dataclasses import dataclass
from typing import Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from ..events import L2Update, QuoteSnapshot, TradeEvent

PARTITION_PATTERN = re.compile(r"^(?P<prefix>[a-z_]+)_(?P<symbol>[A-Z0-9_]+)_(?P<date>\d{8})$")


@dataclass(slots=True)
class PartitionedEventStore:
    """Base class for SQLite/DuckDB partitioned event stores."""

    connection: object

    def __post_init__(self) -> None:
        self._lock = threading.RLock()

    # ---- Public API -----------------------------------------------------------------
    def persist_trades(self, events: Sequence[TradeEvent]) -> None:
        if not events:
            return
        batches = self._partition(events, "trade_events", self._trade_row)
        self._bulk_insert(batches, self._trade_schema)

    def persist_l2_updates(self, events: Sequence[L2Update]) -> None:
        if not events:
            return
        batches = self._partition(events, "l2_updates", self._l2_row)
        self._bulk_insert(batches, self._l2_schema)

    def persist_quotes(self, events: Sequence[QuoteSnapshot]) -> None:
        if not events:
            return
        batches = self._partition(events, "quote_snapshots", self._quote_row)
        self._bulk_insert(batches, self._quote_schema)

    def enforce_retention(self, retention_days: int) -> None:
        if retention_days <= 0:
            return
        cutoff = (dt.date.today() - dt.timedelta(days=retention_days)).strftime("%Y%m%d")
        with self._lock:
            for table in self._list_tables():
                match = PARTITION_PATTERN.match(table)
                if not match:
                    continue
                if match.group("date") < cutoff:
                    self._drop_table(table)

    # ---- Internal helpers -----------------------------------------------------------
    def _partition(self, events: Sequence[object], prefix: str, row_fn) -> MutableMapping[str, List[Tuple]]:
        partitions: MutableMapping[str, List[Tuple]] = {}
        for event in events:
            table = self._table_name(prefix, getattr(event, "symbol"), getattr(event, "ts_ns"))
            partitions.setdefault(table, []).append(row_fn(event))
        return partitions

    def _table_name(self, prefix: str, symbol: str, ts_ns: int) -> str:
        date = dt.datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=dt.timezone.utc).strftime("%Y%m%d")
        safe_symbol = re.sub(r"[^A-Z0-9_]", "_", symbol.upper())
        return f"{prefix}_{safe_symbol}_{date}"

    def _trade_row(self, event: TradeEvent) -> Tuple:
        return (
            event.ts_ns,
            event.received_ts_ns,
            event.trade_id,
            event.side,
            event.price,
            event.size,
        )

    def _l2_row(self, event: L2Update) -> Tuple:
        return (
            event.ts_ns,
            event.received_ts_ns,
            json.dumps(event.bids),
            json.dumps(event.asks),
            event.sequence_start,
            event.sequence_end,
        )

    def _quote_row(self, event: QuoteSnapshot) -> Tuple:
        return (
            event.ts_ns,
            event.received_ts_ns,
            event.bid_price,
            event.bid_size,
            event.ask_price,
            event.ask_size,
        )

    # -- Abstract methods -------------------------------------------------------------
    def _bulk_insert(self, batches: Mapping[str, List[Tuple]], schema_fn) -> None:
        raise NotImplementedError

    def _ensure_table(self, table: str, schema_sql: str) -> None:
        raise NotImplementedError

    def _trade_schema(self, table: str) -> str:
        return (
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "ts_ns BIGINT,"
            "received_ts_ns BIGINT,"
            "trade_id TEXT,"
            "side TEXT,"
            "price DOUBLE,"
            "size DOUBLE"
            ")"
        )

    def _l2_schema(self, table: str) -> str:
        return (
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "ts_ns BIGINT,"
            "received_ts_ns BIGINT,"
            "bids TEXT,"
            "asks TEXT,"
            "sequence_start BIGINT,"
            "sequence_end BIGINT"
            ")"
        )

    def _quote_schema(self, table: str) -> str:
        return (
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "ts_ns BIGINT,"
            "received_ts_ns BIGINT,"
            "bid_price DOUBLE,"
            "bid_size DOUBLE,"
            "ask_price DOUBLE,"
            "ask_size DOUBLE"
            ")"
        )

    def _list_tables(self) -> Iterable[str]:
        raise NotImplementedError

    def _drop_table(self, table: str) -> None:
        raise NotImplementedError
