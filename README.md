# Trading-Bot

A modular event-driven trading bot toolkit focused on high quality market-data ingestion, persistence, and distribution. The
core components include:

- Immutable event models for trades, level-2 updates, and quote snapshots.
- A KuCoin websocket feed handler that normalises timestamps using a monotonic clock guard.
- Partitioned SQLite and DuckDB storage backends with retention policies and batch inserts.
- A lightweight publish/subscribe bus with utilities for building live snapshots for downstream consumers.

## Package layout

```
trading_bot/
├── events.py              # Immutable event data structures
├── feeds/kucoin.py        # KuCoin feed parsing utilities
├── pubsub.py              # Lock-free event bus and snapshot builders
├── storage/
│   ├── base.py            # Partitioned persistence framework
│   ├── sqlite.py          # SQLite-backed event store
│   └── duckdb.py          # DuckDB-backed event store
└── utils/time.py          # Monotonic timestamp guard
```

## Usage

```python
from trading_bot import EventBus, KuCoinFeedHandler
from trading_bot.storage.sqlite import SqliteEventStore

feed = KuCoinFeedHandler()
store = SqliteEventStore("events.db")
bus = EventBus()

raw_message = {"subject": "trade.l3match", "data": {"symbol": "BTC-USDT", "price": "25000", "size": "0.1", "ts": 1697040000000000000}}
for event in feed.parse(raw_message):
    store.persist_trades([event]) if event.to_dict()["type"] == "trade" else None
    bus.publish(event)
```

## Development

The package targets Python 3.10+ and relies on the standard library plus optional `duckdb` if the DuckDB backend is required.
```
python -m compileall trading_bot
```
