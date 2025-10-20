"""SQLite-backed event persistence."""

from __future__ import annotations

import sqlite3
from typing import Iterable, List, Mapping, Tuple

from .base import PartitionedEventStore


class SqliteEventStore(PartitionedEventStore):
    """Persist events into partitioned SQLite tables."""

    def __init__(self, path: str) -> None:
        connection = sqlite3.connect(path, check_same_thread=False)
        connection.execute("PRAGMA journal_mode=WAL")
        super().__init__(connection)

    def _bulk_insert(self, batches: Mapping[str, List[Tuple]], schema_fn) -> None:  # type: ignore[override]
        with self._lock:
            cursor = self.connection.cursor()
            try:
                for table, rows in batches.items():
                    cursor.execute(schema_fn(table))
                    cursor.executemany(
                        f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
                        rows,
                    )
                self.connection.commit()
            finally:
                cursor.close()

    def _ensure_table(self, table: str, schema_sql: str) -> None:  # type: ignore[override]
        with self._lock:
            self.connection.execute(schema_sql)

    def _list_tables(self) -> Iterable[str]:  # type: ignore[override]
        cursor = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return [row[0] for row in cursor.fetchall()]

    def _drop_table(self, table: str) -> None:  # type: ignore[override]
        with self._lock:
            self.connection.execute(f"DROP TABLE IF EXISTS {table}")
            self.connection.commit()
