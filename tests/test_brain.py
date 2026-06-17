"""Unit tests for divergence detection + setup-conditional conviction scoring.

The key regression: the PRIME accumulation setup (whales in, retail asleep) must
score ABOVE a weaker confirmation setup with the same flow — the flaw the experiment
exposed. No network.
"""

from config import settings
from brain.divergence import detect, Setup
from brain.conviction import score
from signals.onchain import OnchainSignal
from signals.twitter import TwitterSignal
from signals.reddit import RedditSignal
from signals.cmc import CmcSignal

STRONG = settings.ONCHAIN_STRONG_FLOW_USD * 2  # comfortably strong flow


def _on(flow):
    return OnchainSignal("CAKE", flow, flow, 4, "in" if flow > 0 else "out")


def _tw(vel):
    return TwitterSignal("CAKE", mentions=100, velocity=vel)


def _rd(activity):
    return RedditSignal("CAKE", sentiment=0.5, activity=activity)


def _cmc(ok):
    return CmcSignal("CAKE", liquidity_usd=1e6, funding_rate=0.0, structural_ok=ok)


def test_accumulation_when_flow_in_and_social_flat():
    d = detect("CAKE", _tw(1.0), _rd(0.0), _on(STRONG), _cmc(True))
    assert d.setup is Setup.ACCUMULATION


def test_confirmation_when_flow_in_and_social_hot():
    d = detect("CAKE", _tw(2.5), _rd(0.8), _on(STRONG), _cmc(True))
    assert d.setup is Setup.CONFIRMATION


def test_distribution_when_flow_out_and_social_hot():
    d = detect("CAKE", _tw(2.6), _rd(0.8), _on(-STRONG), _cmc(True))
    assert d.setup is Setup.DISTRIBUTION


def test_no_trade_when_single_axis():
    d = detect("CAKE", _tw(2.5), _rd(0.8), _on(10.0), _cmc(True))  # social hot, no flow
    assert d.setup is Setup.NO_TRADE


def test_accumulation_outscores_confirmation_same_flow():
    # THE regression guard: prime accumulation must beat weaker confirmation.
    acc = score(detect("CAKE", _tw(1.0), _rd(0.0), _on(STRONG), _cmc(True)))
    conf = score(detect("CAKE", _tw(2.5), _rd(0.8), _on(STRONG), _cmc(True)))
    assert acc.direction == "long" and conf.direction == "long"
    assert acc.score > conf.score, (acc.score, conf.score)


def test_accumulation_fires_above_threshold():
    acc = score(detect("CAKE", _tw(0.5), _rd(0.0), _on(STRONG), _cmc(True)))
    assert acc.score >= settings.CONVICTION_THRESHOLD


def test_cmc_veto_zeroes_score():
    c = score(detect("CAKE", _tw(0.5), _rd(0.0), _on(STRONG), _cmc(False)))
    assert c.direction == "none" and c.score == 0.0


def test_distribution_is_exit():
    c = score(detect("CAKE", _tw(2.6), _rd(0.8), _on(-STRONG), _cmc(True)))
    assert c.direction == "exit"
