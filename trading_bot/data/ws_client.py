from __future__ import annotations

import abc
import asyncio
from typing import AsyncIterator, Iterable, Protocol


class AbstractWebSocketClient(abc.ABC):
    """Interface for streaming incremental account updates."""

    @abc.abstractmethod
    async def subscribe(self) -> AsyncIterator[object]:
        """Yield updates for balances, positions, fills, and mid-prices."""


class WebSocketClientProtocol(Protocol):
    async def subscribe(self) -> AsyncIterator[object]:
        ...


class InMemoryWebSocketClient(AbstractWebSocketClient):
    """In-memory producer to simulate streaming updates."""

    def __init__(self, updates: Iterable[object], delay: float = 0.0):
        self._updates = list(updates)
        self._delay = delay

    async def subscribe(self) -> AsyncIterator[object]:
        for update in self._updates:
            if self._delay:
                await asyncio.sleep(self._delay)
            yield update
