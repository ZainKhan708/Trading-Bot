# Trading-Bot

A simple algorithmic trading bot template written in Python. This repository now ships with a
reusable indicator library, regime filters, and a configurable state machine for quickly
experimenting with systematic strategies. It is NOT financial advice — use at your own risk.

## Features

- Streaming technical indicators (EMA, ATR, RSI, VWAP, z-score, order-book imbalance, ADX)
- Regime filters combining ADX and breadth proxies to gate mean-reversion systems
- Config-driven strategy parameters loaded via a central `ConfigManager`
- State machine that consumes feature vectors, supports pyramiding, trailing stops, and emits entry/exit intents
- Example configuration files for YAML/JSON driven strategies

## Requirements

- Python 3.10+
- pip

## Installation

1. Clone the repository (if it already has content):
   ```bash
   git clone https://github.com/ZainKhan708/Trading-Bot.git
   cd Trading-Bot
   ```

2. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS / Linux
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Use the `ConfigManager` to load YAML or JSON configuration files. An example YAML configuration is
available at `config/strategy.example.yml`.

```python
from pathlib import Path

from trading_bot import ConfigManager, RegimeFilter, StrategySettings, TradingStateMachine

config = ConfigManager([Path("config")]).load("strategy.example.yml")
settings = StrategySettings(**config["strategy"])
regime = RegimeFilter(**config["regime"])
machine = TradingStateMachine(settings=settings, regime_filter=regime)
```

## Usage

Feed streaming feature vectors into `TradingStateMachine.on_features`. Each invocation returns a
list of intents describing the desired trading actions (entry/exit, direction, size, and trailing
stop suggestions). Wire those intents into your execution layer or broker API.

## Contributing

Contributions are welcome. Please open issues or pull requests and follow repository coding
standards. Add tests and update documentation when adding new features.

## License

Add a LICENSE file (for example, MIT) to make licensing explicit. If none is provided, the project
defaults to “All rights reserved”.

---

This README was prepared for ZainKhan708/Trading-Bot. Replace or expand any sections to match the
actual project structure and filenames.
