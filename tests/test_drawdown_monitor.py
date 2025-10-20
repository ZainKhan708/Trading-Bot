from datetime import datetime, timedelta

from trading_bot.risk.drawdown_monitor import DrawdownMonitor


def test_drawdown_monitor_cool_off_and_override():
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    monitor = DrawdownMonitor(
        daily_limit=0.05,
        weekly_limit=0.1,
        daily_cool_off=timedelta(hours=6),
        weekly_cool_off=timedelta(days=1),
    )

    monitor.record_equity(100_000, now=base_time)
    assert monitor.trading_allowed(now=base_time)

    # 10% drawdown triggers both daily and weekly limits
    monitor.record_equity(90_000, now=base_time + timedelta(minutes=1))
    assert not monitor.trading_allowed(now=base_time + timedelta(minutes=1))

    # Manual override allows trading temporarily
    monitor.manual_override(base_time + timedelta(hours=1))
    assert monitor.trading_allowed(now=base_time + timedelta(minutes=30))

    # Once override expires and cool-off elapsed -> trading allowed again
    later = base_time + timedelta(days=2)
    assert monitor.trading_allowed(now=later)
    status = monitor.status(now=later)
    assert status["override_active"] is False
