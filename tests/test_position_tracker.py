from trading_bot.core.position_tracker import Position, PositionTracker, PositionType


def test_consolidated_notional_and_net_position():
    tracker = PositionTracker()
    tracker.upsert(Position(symbol="BTCUSDT", position_type=PositionType.SPOT, quantity=2, mark_price=30000))
    tracker.upsert(
        Position(
            symbol="BTCUSDT",
            position_type=PositionType.PERPETUAL,
            quantity=-1,
            mark_price=30500,
            contract_size=1,
        )
    )

    assert tracker.consolidated_notional("BTCUSDT") == 2 * 30000 + (-1) * 30500
    assert tracker.net_position("BTCUSDT") == 1
    report = tracker.report()
    assert report["BTCUSDT"]["total"] == tracker.consolidated_notional("BTCUSDT")
