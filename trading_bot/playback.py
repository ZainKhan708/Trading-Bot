"""Playback engine for deterministic market event simulation."""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

from .events import MarketEvent


@dataclass
class PlaybackConfig:
    speed: float = 1.0
    deterministic: bool = True
    seed: int = 42
    start_time: datetime | None = None
    end_time: datetime | None = None
    realtime: bool = False


class PlaybackEngine:
    """Streams stored market events to downstream components."""

    def __init__(
        self,
        events: Sequence[MarketEvent],
        config: PlaybackConfig | None = None,
        sleep_fn: callable = time.sleep,
    ) -> None:
        self.events = sorted(events, key=lambda e: e.timestamp)
        self.config = config or PlaybackConfig()
        self.sleep_fn = sleep_fn
        self._should_stop = False
        self._rng = random.Random(self.config.seed)

    @classmethod
    def from_jsonl(cls, path: str | Path, config: PlaybackConfig | None = None) -> "PlaybackEngine":
        events: List[MarketEvent] = []
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                payload = json.loads(line)
                events.append(MarketEvent.from_dict(payload))
        return cls(events, config=config)

    def stream(self) -> Iterator[MarketEvent]:
        """Yield events with optional timing control."""

        last_timestamp: datetime | None = None
        for event in self._windowed_events():
            if self._should_stop:
                break
            if self.config.realtime and last_timestamp is not None:
                delay = (event.timestamp - last_timestamp).total_seconds()
                if self.config.speed > 0:
                    delay /= self.config.speed
                if delay > 0:
                    self.sleep_fn(delay)
            yield event
            last_timestamp = event.timestamp

    def stop(self) -> None:
        self._should_stop = True

    def reset(self) -> None:
        self._should_stop = False

    def _windowed_events(self) -> Iterable[MarketEvent]:
        for event in self.events:
            if self.config.start_time and event.timestamp < self.config.start_time:
                continue
            if self.config.end_time and event.timestamp > self.config.end_time:
                break
            yield event

    def play_into(self, handler: callable) -> None:
        """Push events into the provided handler callback."""

        self.reset()
        for event in self.stream():
            handler(event)


__all__ = ["PlaybackEngine", "PlaybackConfig"]
