"""Market data feed helpers for playback and live simulation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Sequence

from .events import MarketEvent
from .interfaces import MarketDataFeed


class ListMarketDataFeed(MarketDataFeed):
    def __init__(self, events: Sequence[MarketEvent]) -> None:
        self.events = sorted(events, key=lambda e: e.timestamp)

    def stream(self) -> Iterator[MarketEvent]:
        for event in self.events:
            yield event


class JsonlMarketDataFeed(MarketDataFeed):
    """Read events lazily from a JSONL file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def stream(self) -> Iterator[MarketEvent]:
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = json.loads(line)
                yield MarketEvent.from_dict(payload)


__all__ = ["ListMarketDataFeed", "JsonlMarketDataFeed"]
