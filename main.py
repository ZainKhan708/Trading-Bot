"""Example entry point demonstrating the simulation framework."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from trading_bot.backtest import (
    BacktestEngine,
    BayesianParameterSweep,
    GridParameterSweep,
    WalkForwardTester,
)
from trading_bot.execution import SimulatedExecutionEngine
from trading_bot.events import MarketEvent
from trading_bot.live_sim import LiveSimulator
from trading_bot.market_data import ListMarketDataFeed
from trading_bot.portfolio import PortfolioState
from trading_bot.report import PerformanceReport
from trading_bot.risk import BasicRiskManager
from trading_bot.strategy import MeanReversionStrategy


def generate_synthetic_events(symbol: str, count: int = 500) -> List[MarketEvent]:
    events: List[MarketEvent] = []
    timestamp = datetime.now(tz=timezone.utc)
    price = 100.0
    for idx in range(count):
        # Introduce slow oscillations and noise.
        trend = math.sin(idx / 40.0) * 0.2
        shock = random.gauss(0, 0.5)
        price = max(1.0, price * (1 + trend * 0.01) + shock * 0.1)
        bid = price - 0.05
        ask = price + 0.05
        events.append(
            MarketEvent(
                symbol=symbol,
                timestamp=timestamp + timedelta(seconds=idx),
                bid=bid,
                ask=ask,
                bid_size=5_000,
                ask_size=5_000,
                last_price=price,
                last_size=1_000 + abs(shock) * 10,
            )
        )
    return events


def build_strategy(params: Dict[str, float]) -> MeanReversionStrategy:
    return MeanReversionStrategy(
        symbol="XYZ",
        lookback=int(params.get("lookback", 20)),
        entry_z=params.get("entry_z", 1.5),
        exit_z=params.get("exit_z", 0.5),
        size=float(params.get("size", 100.0)),
    )


def build_risk_manager(portfolio: PortfolioState) -> BasicRiskManager:
    return BasicRiskManager(portfolio=portfolio, max_position=5_000, max_notional=250_000)


def build_execution_engine() -> SimulatedExecutionEngine:
    return SimulatedExecutionEngine(random_seed=7)


def run_backtest(events: List[MarketEvent]) -> PerformanceReport:
    engine = BacktestEngine()
    portfolio = PortfolioState(1_000_000.0)
    strategy = build_strategy({})
    risk = build_risk_manager(portfolio)
    execution = build_execution_engine()
    return engine.run(events, strategy, risk, execution, portfolio)


def run_grid_search(events: List[MarketEvent]) -> Dict[str, float]:
    engine = BacktestEngine()
    grid = GridParameterSweep(
        {
            "lookback": [15, 20, 30],
            "entry_z": [1.2, 1.5, 2.0],
            "exit_z": [0.3, 0.5, 0.8],
            "size": [100.0, 200.0],
        }
    )

    def objective(params: Dict[str, float]) -> float:
        report = engine.run_with_factories(
            events,
            strategy_factory=build_strategy,
            params=params,
            risk_factory=build_risk_manager,
            execution_factory=build_execution_engine,
        )
        return report.total_return

    best_params, _ = grid.optimize(objective)
    return best_params


def run_bayesian_optimization(events: List[MarketEvent]) -> Dict[str, float]:
    engine = BacktestEngine()
    sweep = BayesianParameterSweep(
        bounds={"lookback": (10, 50), "entry_z": (1.0, 2.5), "exit_z": (0.2, 1.0), "size": (50.0, 250.0)},
        iterations=15,
        init_points=5,
        random_seed=11,
    )

    def objective(params: Dict[str, float]) -> float:
        report = engine.run_with_factories(
            events,
            strategy_factory=build_strategy,
            params=params,
            risk_factory=build_risk_manager,
            execution_factory=build_execution_engine,
        )
        return report.total_return

    best_params, _ = sweep.optimize(objective)
    return best_params


def run_walk_forward(events: List[MarketEvent]) -> List[PerformanceReport]:
    engine = BacktestEngine()
    tester = WalkForwardTester(events, engine)

    results = tester.run(
        strategy_factory=build_strategy,
        risk_factory=build_risk_manager,
        execution_factory=build_execution_engine,
        parameter_search_factory=lambda: GridParameterSweep(
            {"lookback": [15, 20, 25], "entry_z": [1.2, 1.6], "exit_z": [0.3, 0.6], "size": [100.0, 150.0]}
        ),
        train_size=len(events) // 3,
        test_size=len(events) // 6,
        step_size=len(events) // 6,
    )
    return [result.report for result in results]


def run_live_sim(events: List[MarketEvent]) -> PerformanceReport:
    feed = ListMarketDataFeed(events)
    portfolio = PortfolioState(1_000_000.0)
    simulator = LiveSimulator(
        feed=feed,
        strategy=build_strategy({}),
        risk_manager=build_risk_manager(portfolio),
        execution_engine=build_execution_engine(),
        portfolio=portfolio,
    )
    return simulator.run()


def main() -> None:
    random.seed(0)
    events = generate_synthetic_events("XYZ", 600)

    print("=== Backtest ===")
    backtest_report = run_backtest(events)
    print(backtest_report.to_markdown())

    print("\n=== Grid Search ===")
    best_grid_params = run_grid_search(events)
    print(best_grid_params)

    print("\n=== Bayesian Optimization ===")
    best_bayes_params = run_bayesian_optimization(events)
    print(best_bayes_params)

    print("\n=== Walk Forward ===")
    walk_forward_reports = run_walk_forward(events)
    for idx, report in enumerate(walk_forward_reports):
        print(f"Window {idx}: {report.to_dict()}")

    print("\n=== Live Simulation ===")
    live_report = run_live_sim(events[:200])
    print(live_report.to_dict())


if __name__ == "__main__":
    main()
