"""Unit tests for the risk guardrails — the disqualifier defense. No network."""

from config import settings
from risk.guardrails import RiskManager

ELIGIBLE_SYM = "CAKE"      # on the allowlist
OFFLIST_SYM = "NOTATOKEN"


class Clock:
    """Controllable clock for cooldown / daily-rollover tests."""
    def __init__(self, t=1_700_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def _rm(clock=None):
    return RiskManager(now_fn=clock or Clock())


def test_drawdown_trips_kill_switch_at_threshold():
    rm = _rm()
    rm.update_drawdown(100.0)                       # peak = 100
    st = rm.update_drawdown(100.0 * (1 - settings.MAX_DRAWDOWN_PCT / 100))  # exactly at cap
    assert st.kill_switch_tripped
    assert rm.allows(ELIGIBLE_SYM, 1.0, portfolio_usd=1000)[0] is False


def test_drawdown_below_threshold_does_not_trip():
    rm = _rm()
    rm.update_drawdown(100.0)
    st = rm.update_drawdown(90.0)                   # 10% dd, below 25%
    assert not st.kill_switch_tripped


def test_kill_switch_latches():
    rm = _rm()
    rm.update_drawdown(100.0)
    rm.update_drawdown(50.0)                        # 50% dd -> trip
    rm.update_drawdown(100.0)                       # recover
    assert rm.kill_switch is True                   # stays tripped


def test_allowlist_blocks_offlist_token():
    rm = _rm()
    rm.update_drawdown(1000.0)
    assert rm.allows(OFFLIST_SYM, 10.0)[0] is False
    assert rm.allows(ELIGIBLE_SYM, 10.0)[0] is True


def test_zero_size_trade_rejected():
    rm = _rm()
    rm.update_drawdown(1000.0)
    ok, reason = rm.allows(ELIGIBLE_SYM, 0.0)
    assert ok is False and "zero" in reason
    assert rm.allows(ELIGIBLE_SYM, -5.0)[0] is False


def test_position_size_caps_at_max_pct():
    rm = _rm()
    cap = 1000 * settings.MAX_POSITION_PCT / 100
    assert rm.position_size(100, 1000) == round(cap, 2)
    assert rm.position_size(50, 1000) == round(cap * 0.5, 2)


def test_oversized_trade_blocked():
    rm = _rm()
    rm.update_drawdown(1000.0)
    over = 1000 * settings.MAX_POSITION_PCT / 100 + 1
    assert rm.allows(ELIGIBLE_SYM, over)[0] is False


def test_cooldown_blocks_then_clears():
    clk = Clock()
    rm = _rm(clk)
    rm.update_drawdown(1000.0)
    rm.record_trade(ELIGIBLE_SYM)
    assert rm.allows(ELIGIBLE_SYM, 10.0)[0] is False           # immediately after
    clk.advance(settings.COOLDOWN_MINUTES * 60 + 1)
    assert rm.allows(ELIGIBLE_SYM, 10.0)[0] is True            # cooldown elapsed


def test_dust_guard_blocks_trade():
    rm = _rm()
    rm.update_drawdown(settings.DUST_FLOOR_USD)
    assert rm.is_dust()
    assert rm.allows(ELIGIBLE_SYM, 0.1)[0] is False


def test_daily_floor_and_rollover():
    clk = Clock()                                              # base 1.7e9 == 22:13 UTC (past floor hour)
    rm = _rm(clk)
    assert rm.needs_daily_floor_trade() is True                # nothing yet today, day closing
    rm.record_trade(ELIGIBLE_SYM)
    assert rm.needs_daily_floor_trade() is False               # traded today
    clk.advance(24 * 3600 + 1)                                 # next day
    assert rm.needs_daily_floor_trade() is True                # counter reset, still late hour


def test_daily_floor_held_until_day_closes():
    # 08:00 UTC: zero trades, but it is early — do NOT force a sub-threshold trade yet.
    early = Clock(t=1_699_948_800.0)                           # 2023-11-14T08:00:00 UTC
    rm = _rm(early)
    assert rm.needs_daily_floor_trade() is False
    early.advance(settings.DAILY_FLOOR_HOUR_UTC * 3600 - 8 * 3600)  # advance to the floor hour
    assert rm.needs_daily_floor_trade() is True


def test_daily_trade_cap_blocks_overtrading():
    rm = _rm()
    rm.update_drawdown(1000.0)
    toks = ["CAKE", "AVAX", "LINK", "UNI", "AAVE", "DOT", "ATOM", "INJ"]  # distinct -> no cooldown
    allowed = 0
    for t in toks:
        if rm.allows(t, 10.0)[0]:
            rm.record_trade(t)
            allowed += 1
    assert allowed == settings.MAX_TRADES_PER_DAY                # stops at the cap
    assert "daily trade cap" in rm.allows("FET", 10.0)[1]       # fresh token still blocked
