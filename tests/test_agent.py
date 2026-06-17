"""Tests for the agent decision cycle (DRY_RUN, synthetic signals, no network)."""

import pytest

from config import settings
from agent import run_cycle
from risk.guardrails import RiskManager
from brain.memory import Memory
from signals.onchain import OnchainSignal
from signals.twitter import TwitterSignal
from signals.reddit import RedditSignal
from signals.cmc import CmcSignal

STRONG = settings.ONCHAIN_STRONG_FLOW_USD * 2
PF = 100.0


@pytest.fixture(autouse=True)
def dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")


def _on(flow):
    return OnchainSignal("CAKE", flow, flow, 4, "in" if flow > 0 else "out")


def test_accumulation_fires_a_dry_trade():
    rm = RiskManager()
    maps = (
        {"CAKE": _on(STRONG)},                       # strong inflow
        {"CAKE": TwitterSignal("CAKE", 50, 0.4)},    # quiet social
        {}, {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True)},
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
        {}, {"CAKE": CmcSignal("CAKE", 0.0, 0.0, False)},   # veto
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
        {}, {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True)},
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
        {"CAKE": _on(-STRONG)},                            # smart money leaving
        {"CAKE": TwitterSignal("CAKE", 900, 2.6)},         # retail euphoric
        {"CAKE": RedditSignal("CAKE", 0.7, 0.8)},          # reddit agrees
        {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True)},
    )
    actions = run_cycle(rm, ["CAKE"], *maps, PF, mem)
    exits = [a for a in actions if a.direction == "exit" and a.executed]
    assert len(exits) == 1 and exits[0].size_usd == 20.0
    assert mem.holding("CAKE") == 0.0                       # position closed
    mem.close()


def test_buy_is_recorded_in_memory():
    rm = RiskManager()
    mem = Memory(db_path=":memory:")
    maps = (
        {"CAKE": _on(STRONG)}, {"CAKE": TwitterSignal("CAKE", 50, 0.4)},
        {}, {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True)},
    )
    run_cycle(rm, ["CAKE"], *maps, PF, mem)
    assert mem.holding("CAKE") > 0                          # buy persisted
    mem.close()
