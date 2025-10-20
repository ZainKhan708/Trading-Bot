# Trading-Bot

An end-to-end research environment for deterministic market data playback, strategy experimentation, and live shadow testing. The codebase focuses on reusing production-ready interfaces for strategies, risk management, and execution while providing a simulation-grade fill model and analytical tooling for evaluating performance.

> ⚠️ This repository is **not** financial advice. It is intended for educational use and rapid prototyping. Trade responsibly.

## Highlights

- **Deterministic playback engine** – stream JSONL or in-memory market events at configurable speed for reproducible research.
- **Queue-aware execution simulator** – model latency, queue position, and market impact while reusing production execution APIs for seamless swapping between live and simulated environments.
- **Strategy + risk modularity** – implement strategies using familiar interfaces; risk controls operate on the same portfolio state as the execution layer.
- **Walk-forward + sweeps** – run grid or Bayesian parameter searches, then evaluate out-of-sample performance via walk-forward windows.
- **Live-sim shadow mode** – mirror a realtime feed while routing orders through the simulator for safe production rehearsals.
- **Rich reporting** – generate detailed performance summaries including drawdown, Sharpe, and trade statistics in JSON or markdown form.

## Project layout

```
trading_bot/
├── backtest.py          # Backtest engine, parameter sweeps, walk-forward tester
├── execution.py         # Simulated execution with queue position + impact
├── events.py            # Market + order event dataclasses
├── interfaces.py        # Shared Strategy/Risk/Execution/Feed interfaces
├── live_sim.py          # Live-sim runner for shadow testing
├── market_data.py       # Helpers for list/JSONL data feeds
├── playback.py          # Deterministic playback engine
├── portfolio.py         # Portfolio, position, and PnL accounting
├── report.py            # Performance reporting utilities
├── risk.py              # Example risk manager implementation
├── session.py           # Trading session orchestration glue
└── strategy.py          # Example mean reversion strategy
main.py                  # Demonstration entry point tying the components together
```

## Getting started

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt  # Optional – the demo relies only on NumPy (bundled with many Python installs)
   ```

2. **Run the demo**

   ```bash
   python main.py
   ```

   The script generates synthetic market data, performs a baseline backtest, runs grid and Bayesian parameter searches, executes walk-forward testing, and finally mirrors a live-sim session. Each stage prints a concise performance summary.

## Integrating your strategy

1. Implement the `Strategy` interface from `trading_bot.interfaces`. The example `MeanReversionStrategy` shows a lightweight implementation that emits `OrderRequest` objects in response to market data.
2. (Optional) Extend `BasicRiskManager` or provide your own `RiskManager` to enforce portfolio-level guardrails.
3. Use `BacktestEngine.run` or `LiveSimulator` to evaluate your strategy on stored data or realtime feeds. The same strategy code can operate in both modes without modification.

## Data playback

- To replay stored events from disk, serialize them as JSON lines compatible with `MarketEvent.from_dict` (see `events.py`).
- Use `PlaybackEngine.from_jsonl("/path/to/events.jsonl")` to construct a stream; configure `PlaybackConfig` for speed control, start/end timestamps, and realtime pacing.

## Parameter optimization

- **Grid search**: instantiate `GridParameterSweep` with discrete values for each parameter. The `.optimize` method expects an objective callable returning a scalar score (e.g., total return).
- **Bayesian optimization**: configure `BayesianParameterSweep` with parameter bounds. It leverages a Gaussian-process surrogate to balance exploration vs. exploitation while keeping dependency weight low.
- **Walk-forward**: `WalkForwardTester.run` takes factories for strategy/risk/execution components along with a sweep factory. Each window optimizes on training data and evaluates out-of-sample performance, returning structured reports.

## Live shadow testing

- Implement `MarketDataFeed.stream` to mirror your realtime data source.
- Create a `LiveSimulator` with your feed, strategy, risk manager, and the simulated execution engine. Orders will be filled by the queue/impact model while market data is consumed in realtime, enabling "live-sim" verification alongside production systems.

## Extensibility ideas

- Add exchange adapters that translate production FIX/REST messages into `MarketEvent` objects for playback.
- Plug in alternate execution models (agent-based, Monte Carlo) by implementing `ExecutionEngine`.
- Export `PerformanceReport.to_dict()` payloads into your analytics stack or dashboards.

## Contributing

Contributions are welcome! Please open issues or pull requests with clear descriptions, add tests where appropriate, and ensure code follows the style demonstrated in this repository.

## License

Specify your preferred open-source license in a new `LICENSE` file before distributing beyond personal use.
