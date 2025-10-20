"""Performance reporting utilities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from statistics import mean, pstdev
from typing import Dict, List, Tuple

from .portfolio import PortfolioState


def _compute_returns(equity_curve: List[Tuple[datetime, float]]) -> List[float]:
    returns: List[float] = []
    for idx in range(1, len(equity_curve)):
        prev = equity_curve[idx - 1][1]
        curr = equity_curve[idx][1]
        if prev > 0:
            returns.append((curr - prev) / prev)
    return returns


def _max_drawdown(equity_curve: List[Tuple[datetime, float]]) -> float:
    peak = float("-inf")
    max_dd = 0.0
    for _, value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (peak - value) / peak
            max_dd = max(max_dd, drawdown)
    return max_dd


def _elapsed_days(equity_curve: List[Tuple[datetime, float]]) -> float:
    if len(equity_curve) < 2:
        return 1 / 252.0
    start, end = equity_curve[0][0], equity_curve[-1][0]
    elapsed_seconds = max((end - start).total_seconds(), 1.0)
    return elapsed_seconds / 86_400


@dataclass
class PerformanceReport:
    starting_equity: float
    ending_equity: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    stats: Dict[str, float]

    @classmethod
    def from_portfolio(cls, portfolio: PortfolioState) -> "PerformanceReport":
        starting_equity = portfolio.starting_cash
        ending_equity = portfolio.equity_curve[-1][1] if portfolio.equity_curve else portfolio.cash
        total_return = (ending_equity - starting_equity) / starting_equity if starting_equity > 0 else 0.0
        equity_curve = portfolio.equity_curve or [(datetime.utcnow(), portfolio.cash)]
        returns = _compute_returns(equity_curve)
        max_dd = _max_drawdown(equity_curve)
        elapsed_days = _elapsed_days(equity_curve)
        if returns:
            avg_return = mean(returns)
            volatility = pstdev(returns) or 1e-9
            sharpe = (avg_return / volatility) * sqrt(252)
        else:
            sharpe = 0.0
        winning_trades = sum(1 for trade in portfolio.trade_log if trade["realized_pnl"] > 0)
        trade_count = len(portfolio.trade_log)
        win_rate = winning_trades / trade_count if trade_count else 0.0
        stats = {
            "starting_cash": portfolio.starting_cash,
            "ending_equity": ending_equity,
            "realized_pnl": portfolio.realized_pnl,
            "max_drawdown": max_dd,
            "trade_count": trade_count,
        }
        return cls(
            starting_equity=starting_equity,
            ending_equity=ending_equity,
            total_return=total_return,
            annualized_return=(1 + total_return) ** (365.0 / max(elapsed_days, 1.0)) - 1,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            trade_count=trade_count,
            win_rate=win_rate,
            stats=stats,
        )

    def to_dict(self) -> Dict[str, float]:
        payload = {
            "starting_equity": self.starting_equity,
            "ending_equity": self.ending_equity,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "trade_count": self.trade_count,
            "win_rate": self.win_rate,
        }
        payload.update(self.stats)
        return payload

    def to_markdown(self) -> str:
        rows = ["| Metric | Value |", "| --- | --- |"]
        for key, value in self.to_dict().items():
            rows.append(f"| {key} | {value:.4f} |")
        return "\n".join(rows)


__all__ = ["PerformanceReport"]
