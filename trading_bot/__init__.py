"""Trading bot simulation and backtesting toolkit."""

from .events import MarketEvent, OrderRequest, FillEvent
from .interfaces import Strategy, RiskManager, ExecutionEngine, MarketDataFeed
from .playback import PlaybackEngine
from .execution import SimulatedExecutionEngine
from .backtest import BacktestEngine, WalkForwardTester, GridParameterSweep, BayesianParameterSweep
from .report import PerformanceReport
from .live_sim import LiveSimulator

__all__ = [
    "MarketEvent",
    "OrderRequest",
    "FillEvent",
    "Strategy",
    "RiskManager",
    "ExecutionEngine",
    "MarketDataFeed",
    "PlaybackEngine",
    "SimulatedExecutionEngine",
    "BacktestEngine",
    "WalkForwardTester",
    "GridParameterSweep",
    "BayesianParameterSweep",
    "PerformanceReport",
    "LiveSimulator",
]
