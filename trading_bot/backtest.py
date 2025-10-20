"""Backtesting utilities supporting parameter sweeps and walk-forward testing."""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from math import erf, exp, pi, sqrt
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

from .events import MarketEvent
from .interfaces import ExecutionEngine, RiskManager, Strategy
from .playback import PlaybackConfig, PlaybackEngine
from .portfolio import PortfolioState
from .report import PerformanceReport
from .session import TradingSession


StrategyFactory = Callable[[Dict[str, float]], Strategy]
RiskFactory = Callable[[PortfolioState], RiskManager]
ExecutionFactory = Callable[[], ExecutionEngine]


def _cholesky(matrix: List[List[float]]) -> List[List[float]]:
    n = len(matrix)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                value = matrix[i][i] - s
                if value <= 0:
                    value = 1e-12
                L[i][j] = sqrt(value)
            else:
                if L[j][j] == 0:
                    L[j][j] = 1e-12
                L[i][j] = (matrix[i][j] - s) / L[j][j]
    return L


def _forward_substitution(L: List[List[float]], b: List[float]) -> List[float]:
    n = len(L)
    y = [0.0] * n
    for i in range(n):
        s = sum(L[i][j] * y[j] for j in range(i))
        y[i] = (b[i] - s) / L[i][i]
    return y


def _backward_substitution(L: List[List[float]], y: List[float]) -> List[float]:
    n = len(L)
    x = [0.0] * n
    for i in reversed(range(n)):
        s = sum(L[j][i] * x[j] for j in range(i + 1, n))
        x[i] = (y[i] - s) / L[i][i]
    return x


class BacktestEngine:
    """Coordinates strategy, risk, and execution objects with market events."""

    def __init__(self, playback_config: PlaybackConfig | None = None, starting_cash: float = 1_000_000.0) -> None:
        self.playback_config = playback_config or PlaybackConfig(realtime=False, speed=0.0)
        self.starting_cash = starting_cash

    def run(
        self,
        events: Sequence[MarketEvent],
        strategy: Strategy,
        risk_manager: RiskManager,
        execution_engine: ExecutionEngine,
        portfolio: PortfolioState | None = None,
    ) -> PerformanceReport:
        session_portfolio = portfolio or PortfolioState(self.starting_cash)
        session = TradingSession(strategy=strategy, risk=risk_manager, execution=execution_engine, portfolio=session_portfolio)
        session.start()
        playback = PlaybackEngine(events, config=self.playback_config, sleep_fn=lambda _: None)
        for event in playback.stream():
            session.process_event(event)
        session.stop()
        return PerformanceReport.from_portfolio(session_portfolio)

    def run_with_factories(
        self,
        events: Sequence[MarketEvent],
        strategy_factory: StrategyFactory,
        params: Dict[str, float],
        risk_factory: RiskFactory,
        execution_factory: ExecutionFactory,
    ) -> PerformanceReport:
        portfolio = PortfolioState(self.starting_cash)
        strategy = strategy_factory(params)
        risk = risk_factory(portfolio)
        execution = execution_factory()
        return self.run(events, strategy, risk, execution, portfolio=portfolio)


class GridParameterSweep:
    """Evaluates every combination in a discrete parameter grid."""

    def __init__(self, param_grid: Dict[str, Sequence[float]]) -> None:
        self.param_grid = param_grid

    def _combinations(self) -> Iterable[Dict[str, float]]:
        keys = list(self.param_grid.keys())
        for values in itertools.product(*(self.param_grid[key] for key in keys)):
            yield dict(zip(keys, values))

    def optimize(self, objective: Callable[[Dict[str, float]], float]) -> Tuple[Dict[str, float], float]:
        best_params: Dict[str, float] | None = None
        best_score = float("-inf")
        for candidate in self._combinations():
            score = objective(candidate)
            if score > best_score:
                best_score = score
                best_params = candidate
        if best_params is None:
            raise ValueError("Parameter grid is empty")
        return best_params, best_score


class BayesianParameterSweep:
    """Lightweight Bayesian optimization using a Gaussian process surrogate."""

    def __init__(
        self,
        bounds: Dict[str, Tuple[float, float]],
        iterations: int = 30,
        init_points: int = 5,
        candidate_pool: int = 128,
        length_scale: float = 1.0,
        noise: float = 1e-6,
        random_seed: int | None = None,
    ) -> None:
        self.bounds = bounds
        self.iterations = iterations
        self.init_points = init_points
        self.candidate_pool = candidate_pool
        self.length_scale = length_scale
        self.noise = noise
        self.random = random.Random(random_seed)
        self.param_names = list(bounds.keys())

    def optimize(self, objective: Callable[[Dict[str, float]], float]) -> Tuple[Dict[str, float], float]:
        samples: List[List[float]] = []
        scores: List[float] = []

        initial_evals = min(self.init_points, self.iterations)
        for _ in range(initial_evals):
            params = self._sample_params()
            score = objective(params)
            samples.append(self._to_array(params))
            scores.append(score)

        if not scores:
            raise ValueError("BayesianParameterSweep requires at least one iteration")

        best_idx = max(range(len(scores)), key=lambda idx: scores[idx])
        best_params = self._to_params(samples[best_idx])
        best_score = scores[best_idx]

        while len(samples) < self.iterations:
            candidate_point = self._propose_candidate(samples, scores)
            params = self._to_params(candidate_point)
            score = objective(params)
            samples.append(candidate_point)
            scores.append(score)
            if score > best_score:
                best_score = score
                best_params = params
        return best_params, best_score

    def _kernel(self, x1: List[float], x2: List[float]) -> float:
        diff = [a - b for a, b in zip(x1, x2)]
        distance_sq = sum(d * d for d in diff)
        return float(exp(-0.5 * distance_sq / (self.length_scale ** 2)))

    def _kernel_matrix(self, X: List[List[float]]) -> List[List[float]]:
        n = len(X)
        K = [[0.0 for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                K[i][j] = self._kernel(X[i], X[j])
        for i in range(n):
            K[i][i] += self.noise
        return K

    def _kernel_vector(self, X: List[List[float]], x_star: List[float]) -> List[float]:
        return [self._kernel(x, x_star) for x in X]

    def _propose_candidate(self, samples: List[List[float]], scores: List[float]) -> List[float]:
        if len(samples) == 0:
            return self._to_array(self._sample_params())
        K = self._kernel_matrix(samples)
        L = _cholesky(K)
        alpha = _backward_substitution(L, _forward_substitution(L, scores))
        candidates = [self._to_array(self._sample_params()) for _ in range(self.candidate_pool)]
        best_candidate = candidates[0]
        best_ei = float("-inf")
        for candidate in candidates:
            k_star = self._kernel_vector(samples, candidate)
            mu = sum(k * a for k, a in zip(k_star, alpha))
            v = _forward_substitution(L, k_star)
            k_star_star = self._kernel(candidate, candidate) + self.noise
            variance = max(float(k_star_star - sum(val * val for val in v)), 0.0)
            sigma = max(sqrt(variance), 1e-6)
            ei = self._expected_improvement(mu, sigma, max(scores))
            if ei > best_ei:
                best_ei = ei
                best_candidate = candidate
        return best_candidate

    def _expected_improvement(self, mu: float, sigma: float, best: float) -> float:
        if sigma <= 0:
            return 0.0
        z = (mu - best) / sigma
        cdf = 0.5 * (1 + erf(z / sqrt(2)))
        pdf = (1 / sqrt(2 * pi)) * exp(-0.5 * z ** 2)
        return (mu - best) * cdf + sigma * pdf

    def _sample_params(self) -> Dict[str, float]:
        return {
            name: self.random.uniform(low, high) for name, (low, high) in self.bounds.items()
        }

    def _to_array(self, params: Dict[str, float]) -> List[float]:
        return [float(params[name]) for name in self.param_names]

    def _to_params(self, array: List[float]) -> Dict[str, float]:
        return {name: float(array[idx]) for idx, name in enumerate(self.param_names)}


@dataclass
class WalkForwardResult:
    params: Dict[str, float]
    report: PerformanceReport
    window_index: int


class WalkForwardTester:
    """Perform walk-forward optimization over sequential data windows."""

    def __init__(self, events: Sequence[MarketEvent], engine: BacktestEngine) -> None:
        self.events = sorted(events, key=lambda e: e.timestamp)
        self.engine = engine

    def run(
        self,
        strategy_factory: StrategyFactory,
        risk_factory: RiskFactory,
        execution_factory: ExecutionFactory,
        parameter_search_factory: Callable[[], object],
        train_size: int,
        test_size: int,
        step_size: int,
    ) -> List[WalkForwardResult]:
        results: List[WalkForwardResult] = []
        total_events = len(self.events)
        window_index = 0
        for start in range(0, total_events - train_size - test_size + 1, step_size):
            train_slice = self.events[start : start + train_size]
            test_slice = self.events[start + train_size : start + train_size + test_size]
            searcher = parameter_search_factory()

            def objective(params: Dict[str, float]) -> float:
                report = self.engine.run_with_factories(
                    train_slice,
                    strategy_factory=strategy_factory,
                    params=params,
                    risk_factory=risk_factory,
                    execution_factory=execution_factory,
                )
                return report.total_return

            best_params, _ = searcher.optimize(objective)
            test_report = self.engine.run_with_factories(
                test_slice,
                strategy_factory=strategy_factory,
                params=best_params,
                risk_factory=risk_factory,
                execution_factory=execution_factory,
            )
            results.append(WalkForwardResult(params=best_params, report=test_report, window_index=window_index))
            window_index += 1
        return results


__all__ = [
    "BacktestEngine",
    "GridParameterSweep",
    "BayesianParameterSweep",
    "WalkForwardTester",
    "WalkForwardResult",
]
