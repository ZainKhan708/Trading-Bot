"""Abstract interfaces shared by live and simulated components."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from .events import FillEvent, MarketEvent, OrderRequest


class Strategy(ABC):
    """Base interface for trading strategies."""

    @abstractmethod
    def on_start(self) -> None:
        """Invoked before the first market event is processed."""

    @abstractmethod
    def on_market_data(self, event: MarketEvent) -> List[OrderRequest]:
        """Called for each incoming market event."""

    @abstractmethod
    def on_fill(self, fill: FillEvent) -> None:
        """Called when the execution layer generates a fill."""

    @abstractmethod
    def on_stop(self) -> None:
        """Invoked after all events have been processed."""


class RiskManager(ABC):
    """Controls whether orders are permitted to reach the execution layer."""

    @abstractmethod
    def reset(self) -> None:
        """Reset any internal state prior to a new session."""

    @abstractmethod
    def approve(self, order: OrderRequest) -> bool:
        """Return True if the order is permitted."""

    @abstractmethod
    def on_fill(self, fill: FillEvent) -> None:
        """Update risk state based on fills."""


class ExecutionEngine(ABC):
    """Handles the conversion of orders into fills."""

    @abstractmethod
    def reset(self) -> None:
        """Reset state before a new session starts."""

    @abstractmethod
    def submit(self, order: OrderRequest, event: MarketEvent) -> Iterable[FillEvent]:
        """Called when a new order is approved by the risk manager."""

    @abstractmethod
    def on_market_data(self, event: MarketEvent) -> Iterable[FillEvent]:
        """Advance internal state in response to new market data."""


class MarketDataFeed(ABC):
    """Provides a stream of market events for live simulation."""

    @abstractmethod
    def stream(self) -> Iterable[MarketEvent]:
        """Yield market events in chronological order."""
