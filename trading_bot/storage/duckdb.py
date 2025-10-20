"""DuckDB-backed event persistence."""

from __future__ import annotations

import importlib
from typing import Iterable, List, Mapping, Tuple

from .base import PartitionedEventStore

_spec = importlib.util.find_spec("duckdb")
DUCKDB = importlib.import_module("duckdb") if _spec is not None else None


class DuckDBEventStore(PartitionedEventStore):
    """Persist events into partitioned DuckDB tables."""

    def __init__(self, path: str) -> None:
        if DUCKDB is None:
            raise ModuleNotFoundError("duckdb is required to use DuckDBEventStore")
        connection = DUCKDB.connect(path)
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
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        )
        return [row[0] for row in cursor.fetchall()]

    def _drop_table(self, table: str) -> None:  # type: ignore[override]
        with self._lock:
            self.connection.execute(f"DROP TABLE IF EXISTS {table}")
            self.connection.commit()
