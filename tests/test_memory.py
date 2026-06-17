"""Tests for the sqlite memory — baselines + holdings. In-memory DB, no filesystem."""

import pytest

from brain.memory import Memory


class Clock:
    def __init__(self, t=1_700_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def mem():
    m = Memory(db_path=":memory:", now_fn=Clock())
    yield m
    m.close()


def test_baseline_averages_recent(mem):
    now = 1_700_000_000.0
    # three mention readings within the last hour
    for v, dt in [(10, 600), (20, 1200), (30, 1800)]:
        mem.log_signal("CAKE", "twitter", "mentions", v, ts=now - dt)
    assert mem.baseline("CAKE", "twitter", "mentions", hours=1, now=now) == 20.0


def test_baseline_excludes_old(mem):
    now = 1_700_000_000.0
    mem.log_signal("CAKE", "twitter", "mentions", 100, ts=now - 10 * 3600)  # 10h old
    mem.log_signal("CAKE", "twitter", "mentions", 50, ts=now - 600)          # recent
    assert mem.baseline("CAKE", "twitter", "mentions", hours=1, now=now) == 50.0


def test_baseline_empty_is_zero(mem):
    assert mem.baseline("NONE", "twitter", "mentions", hours=24) == 0.0


def test_holding_nets_buys_and_sells(mem):
    mem.log_trade("CAKE", "buy", 20.0, "0xa", 80.0)
    mem.log_trade("CAKE", "buy", 10.0, "0xb", 70.0)
    mem.log_trade("CAKE", "sell", 5.0, "0xc", 0.0)
    assert mem.holding("CAKE") == 25.0


def test_holding_floored_at_zero(mem):
    mem.log_trade("CAKE", "sell", 5.0, "0xc", 0.0)   # oversell / no position
    assert mem.holding("CAKE") == 0.0


def test_holdings_lists_open_positions(mem):
    mem.log_trade("CAKE", "buy", 20.0, "0xa", 80.0)
    mem.log_trade("AVAX", "buy", 15.0, "0xb", 70.0)
    mem.log_trade("AVAX", "sell", 15.0, "0xc", 0.0)  # closed
    assert mem.holdings() == {"CAKE": 20.0}


def test_bad_side_rejected(mem):
    with pytest.raises(ValueError):
        mem.log_trade("CAKE", "hodl", 1.0, "0x", 0.0)
