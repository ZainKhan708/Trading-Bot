from trading_bot.risk.position_sizer import DepthLevel, DepthSnapshot, PositionSizer


def test_position_sizer_limits_to_smallest_constraint():
    depth = DepthSnapshot(
        bids=[DepthLevel(price=9990, size=1), DepthLevel(price=9980, size=1)],
        asks=[DepthLevel(price=10010, size=1.5), DepthLevel(price=10020, size=2)],
    )
    sizer = PositionSizer(equity=10000, risk_percent=0.01, atr_stop_multiple=2, slippage_cap=0.001)

    result = sizer.size_order(entry_price=10000, atr=50, is_buy=True, depth=depth)

    # Risk sizing: risk_amount=100, stop_distance=100, so size=1
    assert result.risk_limit_size == 1
    # Slippage size from asks: only first level within 0.1% => size=1.5
    assert result.slippage_limit_size == 1.5
    assert result.size == 1
