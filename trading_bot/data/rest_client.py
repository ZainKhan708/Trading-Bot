from __future__ import annotations

import abc
from typing import Protocol

from trading_bot.models import AccountSnapshot


class AbstractRESTClient(abc.ABC):
    """Abstract interface for retrieving REST snapshots."""

    @abc.abstractmethod
    async def fetch_account_snapshot(self) -> AccountSnapshot:
        """Return a complete account snapshot."""


class RESTClientProtocol(Protocol):
    async def fetch_account_snapshot(self) -> AccountSnapshot:
        ...


class InMemoryRESTClient(AbstractRESTClient):
    """Simple REST client returning a pre-configured snapshot."""

    def __init__(self, snapshot: AccountSnapshot):
        self._snapshot = snapshot

    async def fetch_account_snapshot(self) -> AccountSnapshot:
        return self._snapshot
