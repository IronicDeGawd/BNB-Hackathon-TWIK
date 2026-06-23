"""Tests for the agent decision cycle (DRY_RUN, synthetic signals, no network)."""

import pytest

from config import settings
from execution import twak
from agent import run_cycle
from risk.guardrails import RiskManager
from brain.memory import Memory
from signals.onchain import OnchainSignal
from signals.twitter import TwitterSignal
from signals.reddit import RedditSignal
from signals.cmc import CmcSignal

STRONG = settings.ONCHAIN_STRONG_FLOW_USD * 2
MOM = settings.CMC_MOMENTUM_STRONG_PCT * 2          # strong CMC momentum (primary axis)
PF = 100.0


@pytest.fixture(autouse=True)
def dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    twak._reset_dry_run()
    yield
    twak._reset_dry_run()


def _on(flow):
    return OnchainSignal("CAKE", flow, flow, 4, "in" if flow > 0 else "out")


def test_accumulation_fires_a_dry_trade():
    rm = RiskManager()
    maps = (
        {"CAKE": _on(STRONG)},                       # strong inflow
        {"CAKE": TwitterSignal("CAKE", 50, 0.4)},    # quiet social
        {}, {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True, MOM)},
    )
    actions = run_cycle(rm, ["CAKE"], *maps, PF)
    longs = [a for a in actions if a.direction == "long" and a.executed]
    assert len(longs) == 1
    assert longs[0].tx_hash.startswith("0xDRYRUN")
    assert 0 < longs[0].size_usd <= PF * settings.MAX_POSITION_PCT / 100


def test_cmc_veto_blocks_trade():
    rm = RiskManager()
    maps = (
        {"CAKE": _on(STRONG)},
        {"CAKE": TwitterSignal("CAKE", 50, 0.4)},
        {}, {"CAKE": CmcSignal("CAKE", 0.0, 0.0, False, MOM)},   # momentum up but structural veto
    )
    actions = run_cycle(rm, ["CAKE"], *maps, PF)
    assert all(not a.executed for a in actions)


def test_kill_switch_blocks_entries():
    rm = RiskManager()
    rm.update_drawdown(100.0)
    rm.update_drawdown(50.0)                          # trip kill switch
    maps = (
        {"CAKE": _on(STRONG)},
        {"CAKE": TwitterSignal("CAKE", 50, 0.4)},
        {}, {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True, MOM)},
    )
    actions = run_cycle(rm, ["CAKE"], *maps, PF)
    assert all(not (a.direction == "long" and a.executed) for a in actions)


def test_weak_flow_no_trade():
    rm = RiskManager()
    maps = ({"CAKE": _on(10.0)}, {}, {}, {})         # tiny flow, no social/cmc
    actions = run_cycle(rm, ["CAKE"], *maps, PF)
    assert all(not a.executed for a in actions)


def test_missing_signals_do_not_crash():
    # all maps empty (every collector "down") — loop must still run, just no trades.
    rm = RiskManager()
    actions = run_cycle(rm, ["CAKE", "AVAX"], {}, {}, {}, {}, PF)
    assert all(not a.executed for a in actions)


def test_distribution_exit_sells_held_position():
    rm = RiskManager()
    mem = Memory(db_path=":memory:")
    mem.log_trade("CAKE", "buy", 20.0, "0xprev", 90.0)     # we hold CAKE
    maps = (
        {"CAKE": _on(-STRONG)},                            # on-chain bonus (optional)
        {"CAKE": TwitterSignal("CAKE", 900, 2.6)},         # retail euphoric
        {"CAKE": RedditSignal("CAKE", 0.7, 0.8)},          # reddit agrees
        {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True, -MOM)},  # momentum DOWN -> distribution
    )
    actions = run_cycle(rm, ["CAKE"], *maps, PF, mem)
    exits = [a for a in actions if a.direction == "exit" and a.executed]
    assert len(exits) == 1 and exits[0].size_usd == 20.0
    assert mem.holding("CAKE") == 0.0                       # position closed
    assert rm.trades_total == 1                             # the sell is counted toward activity
    mem.close()


def test_daily_floor_prefers_quality_then_falls_back():
    from agent import _maybe_daily_floor
    from brain.conviction import Conviction
    from risk.guardrails import RiskState
    late = lambda: 1_700_000_000.0                          # 22:13 UTC — floor window active
    state = RiskState(100.0, 100.0, 0.0, False)

    def fresh():
        rm = RiskManager(now_fn=late); rm.update_drawdown(100.0); return rm

    # sub-MIN long and NO fallback pool -> no forced trade
    actions = []
    _maybe_daily_floor(fresh(), state, actions, [Conviction("CAKE", "long", 20.0, 0.2, "weak")], [], 100.0, None)
    assert actions == []

    # sub-MIN long but a positive-momentum fallback exists -> qualifying trade fires
    actions = []
    pool = [(0.6, Conviction("CAKE", "long", 12.0, 0.1, "momentum"))]
    _maybe_daily_floor(fresh(), state, actions, [], pool, 100.0, None)
    assert any(a.executed for a in actions)

    # a quality sub-threshold long is preferred (primary path)
    actions = []
    _maybe_daily_floor(fresh(), state, actions, [Conviction("CAKE", "long", 50.0, 0.5, "ok")], [], 100.0, None)
    assert any(a.executed for a in actions)


def test_llm_veto_blocks_entry(monkeypatch):
    from brain import llm_confirm
    monkeypatch.setenv("VERTEX_PROJECT", "proj")
    monkeypatch.setenv("LLM_CONFIRM", "true")
    monkeypatch.setattr("brain.conviction.make_rationale", lambda *a: "stub")   # keep offline
    monkeypatch.setattr(llm_confirm, "_query_gemini",
                        lambda p: {"allow": False, "reason": "re-buying just-sold token"})
    rm = RiskManager()
    maps = (
        {"CAKE": _on(STRONG)}, {"CAKE": TwitterSignal("CAKE", 50, 0.4)},
        {}, {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True, MOM)},
    )
    actions = run_cycle(rm, ["CAKE"], *maps, PF)
    assert all(not a.executed for a in actions)             # deterministic long, vetoed by LLM
    assert any("LLM veto" in a.reason for a in actions)


def test_stop_loss_exits_losing_position(monkeypatch):
    from agent import _check_stops
    from execution import twak as twk
    mem = Memory(db_path=":memory:")
    mem.log_trade("CAKE", "buy", 10.0, "0xa", 70.0)            # cost $10
    monkeypatch.setattr(twk, "get_token_value", lambda s: 8.0)  # now $8 = -20% > 8% stop
    actions = []
    _check_stops(RiskManager(), actions, mem)
    assert any(a.direction == "exit" and a.executed and "stop-loss" in a.reason for a in actions)
    assert mem.holding("CAKE") == 0.0                          # position closed
    mem.close()


def test_stop_loss_holds_within_threshold(monkeypatch):
    from agent import _check_stops
    from execution import twak as twk
    mem = Memory(db_path=":memory:")
    mem.log_trade("CAKE", "buy", 10.0, "0xa", 70.0)
    monkeypatch.setattr(twk, "get_token_value", lambda s: 9.7)  # -3% < 8% stop -> hold
    actions = []
    _check_stops(RiskManager(), actions, mem)
    assert actions == []
    mem.close()


def test_buy_is_recorded_in_memory():
    rm = RiskManager()
    mem = Memory(db_path=":memory:")
    maps = (
        {"CAKE": _on(STRONG)}, {"CAKE": TwitterSignal("CAKE", 50, 0.4)},
        {}, {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True, MOM)},
    )
    run_cycle(rm, ["CAKE"], *maps, PF, mem)
    assert mem.holding("CAKE") > 0                          # buy persisted
    mem.close()
