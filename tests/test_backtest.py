"""Tests for the backtest replay harness. No network."""

from config import settings
from backtest import Frame, replay
from signals.onchain import OnchainSignal
from signals.twitter import TwitterSignal
from signals.reddit import RedditSignal
from signals.cmc import CmcSignal

S = settings.ONCHAIN_STRONG_FLOW_USD * 2
CMC_OK = {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True)}


def _accum_frame(ts, price):
    return Frame(ts, {"CAKE": price}, {"CAKE": OnchainSignal("CAKE", S, S, 5, "in")},
                 {"CAKE": TwitterSignal("CAKE", 40, 0.4)}, {}, CMC_OK)


def _exit_frame(ts, price):
    return Frame(ts, {"CAKE": price}, {"CAKE": OnchainSignal("CAKE", -S, -S, 5, "out")},
                 {"CAKE": TwitterSignal("CAKE", 900, 2.7)},
                 {"CAKE": RedditSignal("CAKE", 0.6, 0.8)}, CMC_OK)


def test_profitable_round_trip():
    frames = [_accum_frame(0, 2.00), Frame(3600, {"CAKE": 2.60}), _exit_frame(7200, 2.60)]
    r = replay(frames, starting_usd=100.0)
    assert r.n_trades == 2          # one buy, one exit
    assert r.n_wins == 1
    assert r.total_return_pct > 0
    assert not r.disqualified


def test_no_signals_no_trades():
    frames = [Frame(0, {"CAKE": 2.0}), Frame(3600, {"CAKE": 2.1})]
    r = replay(frames, 100.0)
    assert r.n_trades == 0 and r.total_return_pct == 0.0


def test_drawdown_flags_disqualified():
    # Two 20% positions (40% deployed), then both collapse -> drawdown past the 30% gate.
    # A single position can't breach it — that's the position-sizing protection working.
    on = lambda: OnchainSignal("X", S, S, 5, "in")          # noqa: E731
    tw = lambda: TwitterSignal("X", 40, 0.4)                # noqa: E731
    cmc = lambda s: {s: CmcSignal(s, 1e6, 0.0, True)}       # noqa: E731
    accum = Frame(0, {"CAKE": 2.0, "AVAX": 2.0},
                  {"CAKE": on(), "AVAX": on()}, {"CAKE": tw(), "AVAX": tw()}, {},
                  {**cmc("CAKE"), **cmc("AVAX")})
    crash = Frame(3600, {"CAKE": 0.01, "AVAX": 0.01})
    r = replay([accum, crash], 100.0)
    assert r.max_drawdown_pct >= settings.DISQUALIFY_DRAWDOWN_PCT
    assert r.disqualified


def test_empty_frames_safe():
    r = replay([], 100.0)
    assert r.n_trades == 0 and r.final_usd == 100.0
