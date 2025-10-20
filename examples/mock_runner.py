import datetime as dt
from decimal import Decimal

from trading_bot import AccountStateMirror, AnalyticsEngine, PnLCalculator, SQLiteAnalyticsStorage
from trading_bot.api.server import create_app
from trading_bot.data.rest_client import InMemoryRESTClient
from trading_bot.data.ws_client import InMemoryWebSocketClient
from trading_bot.models import (
    AccountSnapshot,
    Balance,
    Currency,
    Fill,
    FundingRate,
    FundingRateUpdate,
    MidPriceUpdate,
    Position,
    PositionUpdate,
)


def build_app():
    snapshot = AccountSnapshot(
        balances={
            Currency.USD: Balance(currency=Currency.USD, total=Decimal("100000"), available=Decimal("100000"))
        },
        positions={},
        funding_rates={},
    )
    rest_client = InMemoryRESTClient(snapshot=snapshot)

    updates = [
        MidPriceUpdate(symbol="BTC-PERP", mid_price=Decimal("30000"), timestamp=dt.datetime.utcnow()),
        PositionUpdate(position=Position(symbol="BTC-PERP", size=Decimal("1"), entry_price=Decimal("30000"), side="long")),
        Fill(
            symbol="BTC-PERP",
            fill_id="1",
            price=Decimal("30010"),
            size=Decimal("1"),
            side="buy",
            fee=Decimal("0.5"),
            timestamp=dt.datetime.utcnow(),
        ),
        MidPriceUpdate(symbol="BTC-PERP", mid_price=Decimal("30020"), timestamp=dt.datetime.utcnow()),
        FundingRateUpdate(
            funding_rate=FundingRate(
                symbol="BTC-PERP",
                rate=Decimal("0.0001"),
                next_funding_time=dt.datetime.utcnow() + dt.timedelta(hours=8),
            )
        ),
    ]
    ws_client = InMemoryWebSocketClient(updates=updates, delay=0.1)

    pnl_calculator = PnLCalculator()
    account_state = AccountStateMirror(rest_client, ws_client, pnl_calculator)
    storage = SQLiteAnalyticsStorage(path="analytics.db")
    analytics = AnalyticsEngine(account_state, storage)

    app = create_app(account_state, analytics, storage)
    return app


if __name__ == "__main__":
    app = build_app()
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
