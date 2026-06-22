"""Unit tests for divergence detection + setup-conditional conviction scoring.

Primary axis is CMC 1h momentum; the PRIME accumulation setup (price moving, retail
asleep) must score ABOVE a weaker confirmation with the same momentum. No network.
"""

from config import settings
from brain.divergence import detect, Setup
from brain.conviction import score
from signals.twitter import TwitterSignal
from signals.reddit import RedditSignal
from signals.cmc import CmcSignal

MOM = settings.CMC_MOMENTUM_STRONG_PCT * 2  # comfortably strong momentum


def _tw(vel):
    return TwitterSignal("CAKE", mentions=100, velocity=vel)


def _rd(activity):
    return RedditSignal("CAKE", sentiment=0.5, activity=activity)


def _cmc(ok, mom=0.0):
    return CmcSignal("CAKE", liquidity_usd=1e6, funding_rate=0.0, structural_ok=ok, momentum_pct=mom)


def test_accumulation_when_momentum_up_and_social_flat():
    d = detect("CAKE", _tw(1.0), _rd(0.0), None, _cmc(True, MOM))
    assert d.setup is Setup.ACCUMULATION


def test_confirmation_when_momentum_up_and_social_hot():
    d = detect("CAKE", _tw(2.5), _rd(0.8), None, _cmc(True, MOM))
    assert d.setup is Setup.CONFIRMATION


def test_distribution_when_momentum_down_and_social_hot():
    d = detect("CAKE", _tw(2.6), _rd(0.8), None, _cmc(True, -MOM))
    assert d.setup is Setup.DISTRIBUTION


def test_no_trade_when_single_axis():
    d = detect("CAKE", _tw(2.5), _rd(0.8), None, _cmc(True, 0.0))  # social hot, flat momentum
    assert d.setup is Setup.NO_TRADE


def test_accumulation_outscores_confirmation_same_momentum():
    # THE regression guard: prime accumulation must beat weaker confirmation.
    acc = score(detect("CAKE", _tw(1.0), _rd(0.0), None, _cmc(True, MOM)))
    conf = score(detect("CAKE", _tw(2.5), _rd(0.8), None, _cmc(True, MOM)))
    assert acc.direction == "long" and conf.direction == "long"
    assert acc.score > conf.score, (acc.score, conf.score)


def test_accumulation_fires_above_threshold():
    acc = score(detect("CAKE", _tw(0.5), _rd(0.0), None, _cmc(True, MOM)))
    assert acc.score >= settings.CONVICTION_THRESHOLD


def test_cmc_veto_zeroes_score():
    c = score(detect("CAKE", _tw(0.5), _rd(0.0), None, _cmc(False, MOM)))
    assert c.direction == "none" and c.score == 0.0


def test_distribution_is_exit():
    c = score(detect("CAKE", _tw(2.6), _rd(0.8), None, _cmc(True, -MOM)))
    assert c.direction == "exit"
