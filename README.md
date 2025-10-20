# Trading-Bot Account Analytics

This project provides a modular toolkit for mirroring an exchange account, computing portfolio analytics, and exposing the
results via a FastAPI service. It demonstrates how to combine REST snapshots with WebSocket deltas to keep balances, positions,
and funding rates in sync while generating rich risk and performance metrics for strategy and risk management teams.

## Key Features

- **State mirroring** – `AccountStateMirror` hydrates account data from a REST snapshot and continuously processes incremental
  WebSocket updates for balances, positions, funding rates, mid-prices, and fills.
- **PnL analytics** – `PnLCalculator` captures per-fill realized PnL, fees, and slippage while marking open positions to the
  latest mid-price for unrealized PnL.
- **Historical analytics** – `AnalyticsEngine` produces equity curve, exposure, and turnover time series and persists them using
  an `AnalyticsStorage` backend (SQLite by default).
- **REST API** – A FastAPI application (see `trading_bot/api/server.py`) exposes live metrics plus historical summaries for
  downstream consumers.
- **Examples** – `examples/mock_runner.py` wires the components together with in-memory data sources for local experimentation.

## Getting Started

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Example API

```bash
python examples/mock_runner.py
```

The mock runner spins up an in-memory REST snapshot and WebSocket stream, launches the analytics pipeline, and serves the API on
`http://localhost:8000`. Explore the automatically generated documentation at `http://localhost:8000/docs`.

## Project Structure

```
trading_bot/
├── account_state.py      # Account mirroring orchestration
├── analytics.py          # Equity, exposure, turnover analytics engine
├── api/
│   └── server.py         # FastAPI application factory
├── data/
│   ├── rest_client.py    # REST snapshot interfaces + in-memory implementation
│   └── ws_client.py      # WebSocket streaming interfaces + in-memory implementation
├── models.py             # Dataclasses for account entities and metrics
├── pnl.py                # Realized / unrealized PnL logic
└── storage.py            # Persistence abstractions and SQLite backend
```

## Extending

- Implement concrete REST/WebSocket clients for your exchange by subclassing the provided interfaces.
- Swap out `SQLiteAnalyticsStorage` with a warehouse or data lake connector that suits your analytics stack.
- Add additional metrics (e.g., Sharpe ratios, drawdowns) inside `AnalyticsEngine` and expose new endpoints in the API.

## License

MIT
