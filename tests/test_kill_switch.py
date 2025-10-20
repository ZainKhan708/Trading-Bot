from datetime import datetime, timedelta

from trading_bot.core.position_tracker import Position, PositionTracker, PositionType
from trading_bot.monitoring.kill_switch import KillSwitch


BASE_TIME = datetime(2024, 1, 1, 0, 0, 0)


def make_kill_switch():
    return KillSwitch(
        heartbeat_interval=timedelta(seconds=30),
        heartbeat_grace=timedelta(seconds=10),
        clock_skew_limit=timedelta(seconds=5),
        error_window=timedelta(minutes=1),
        error_threshold=3,
        position_tolerance=0.1,
    )


def test_heartbeat_timeout_triggers_kill_switch():
    ks = make_kill_switch()
    ks.report_heartbeat(BASE_TIME)
    ks.check_heartbeat(now=BASE_TIME + timedelta(minutes=1))
    assert ks.halted
    assert ks.halt_reason == "heartbeat_timeout"


def test_clock_skew_trigger():
    ks = make_kill_switch()
    ks.check_clock_skew(exchange_time=BASE_TIME, local_time=BASE_TIME + timedelta(seconds=10))
    assert ks.halted
    assert ks.halt_reason == "clock_skew"


def test_api_error_threshold():
    ks = make_kill_switch()
    for i in range(3):
        ks.record_api_error(429, timestamp=BASE_TIME + timedelta(seconds=i))
    assert ks.halted
    assert ks.halt_reason == "api_errors"


def test_position_desync_triggers():
    ks = make_kill_switch()
    tracker = PositionTracker()
    tracker.upsert(Position(symbol="ETHUSDT", position_type=PositionType.SPOT, quantity=1, mark_price=2000))
    ks.check_position_sync(tracker, {"ETHUSDT": 0})
    assert ks.halted
    assert ks.halt_reason.startswith("position_desync")
