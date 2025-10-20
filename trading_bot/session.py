"""Trading session orchestration used by backtests and live simulation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .events import FillEvent, MarketEvent
from .interfaces import ExecutionEngine, RiskManager, Strategy
from .portfolio import PortfolioState


@dataclass
class TradingSession:
    strategy: Strategy
    risk: RiskManager
    execution: ExecutionEngine
    portfolio: PortfolioState

    def start(self) -> None:
        self.execution.reset()
        self.risk.reset()
        self.strategy.on_start()

    def process_event(self, event: MarketEvent) -> Iterable[FillEvent]:
        fills = list(self.execution.on_market_data(event))
        for fill in fills:
            self._handle_fill(fill)
        self.portfolio.mark_to_market(event)
        for order in self.strategy.on_market_data(event):
            if self.risk.approve(order):
                for fill in self.execution.submit(order, event):
                    fills.append(fill)
                    self._handle_fill(fill)
        return fills

    def stop(self) -> None:
        self.strategy.on_stop()

    def _handle_fill(self, fill: FillEvent) -> None:
        self.portfolio.update_on_fill(fill)
        self.risk.on_fill(fill)
        self.strategy.on_fill(fill)


__all__ = ["TradingSession"]
