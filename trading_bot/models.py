from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, Iterable


class Currency(str, Enum):
    USD = "USD"
    USDT = "USDT"
    BTC = "BTC"
    ETH = "ETH"


@dataclass
class Balance:
    currency: Currency
    total: Decimal
    available: Decimal


@dataclass
class Position:
    symbol: str
    size: Decimal
    entry_price: Decimal
    side: str  # e.g., "long" or "short"


@dataclass
class FundingRate:
    symbol: str
    rate: Decimal
    next_funding_time: dt.datetime


@dataclass
class AccountSnapshot:
    balances: Dict[Currency, Balance] = field(default_factory=dict)
    positions: Dict[str, Position] = field(default_factory=dict)
    funding_rates: Dict[str, FundingRate] = field(default_factory=dict)


@dataclass
class BalanceUpdate:
    balance: Balance


@dataclass
class PositionUpdate:
    position: Position


@dataclass
class FundingRateUpdate:
    funding_rate: FundingRate


@dataclass
class MidPriceUpdate:
    symbol: str
    mid_price: Decimal
    timestamp: dt.datetime


@dataclass
class Fill:
    symbol: str
    fill_id: str
    price: Decimal
    size: Decimal
    side: str
    fee: Decimal
    timestamp: dt.datetime


@dataclass
class FillPnL:
    fill: Fill
    realized_pnl: Decimal
    slippage: Decimal


@dataclass
class AccountEquityPoint:
    timestamp: dt.datetime
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal


@dataclass
class TurnoverPoint:
    timestamp: dt.datetime
    notional_traded: Decimal


@dataclass
class ExposurePoint:
    timestamp: dt.datetime
    symbol: str
    exposure: Decimal


@dataclass
class AccountMetrics:
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_fees: Decimal
    exposures: Dict[str, Decimal]
    turnover: Decimal
    last_update: dt.datetime


def merge_balances(balances: Iterable[Balance]) -> Dict[Currency, Balance]:
    return {balance.currency: balance for balance in balances}


def merge_positions(positions: Iterable[Position]) -> Dict[str, Position]:
    return {position.symbol: position for position in positions}


def merge_funding_rates(funding_rates: Iterable[FundingRate]) -> Dict[str, FundingRate]:
    return {funding.symbol: funding for funding in funding_rates}
