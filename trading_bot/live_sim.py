"""Live simulation runner that reuses production interfaces."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .interfaces import ExecutionEngine, MarketDataFeed, RiskManager, Strategy
from .portfolio import PortfolioState
from .report import PerformanceReport
from .session import TradingSession


@dataclass
class LiveSimulator:
    feed: MarketDataFeed
    strategy: Strategy
    risk_manager: RiskManager
    execution_engine: ExecutionEngine
    portfolio: PortfolioState

    def __post_init__(self) -> None:
        self.session = TradingSession(
            strategy=self.strategy,
            risk=self.risk_manager,
            execution=self.execution_engine,
            portfolio=self.portfolio,
        )

    def run(self, max_events: Optional[int] = None) -> PerformanceReport:
        self.session.start()
        processed = 0
        for event in self.feed.stream():
            self.session.process_event(event)
            processed += 1
            if max_events is not None and processed >= max_events:
                break
        self.session.stop()
        return PerformanceReport.from_portfolio(self.portfolio)

    def step(self, event) -> None:
        """Process a single market event, useful for manual integration tests."""

        self.session.process_event(event)


__all__ = ["LiveSimulator"]
