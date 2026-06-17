"""Smoke tests for config — these can run today (no API keys needed).

The scorer + risk-gate tests (the ones that MUST be solid) come in Phase C/D.
"""

from config import settings
from config.tokens import is_eligible
from config.watchlist import WATCHLIST, validate


def test_watchlist_subset_of_eligible():
    # Every watchlist symbol must be on the eligible list.
    assert validate() == [], "watchlist contains non-eligible symbols"


def test_watchlist_nonempty():
    assert len(WATCHLIST) > 0


def test_is_eligible_rejects_unknown():
    assert is_eligible("NOTAREALTOKEN") is False
    assert is_eligible("") is False


def test_internal_drawdown_below_disqualifier():
    # Internal kill switch must trip BEFORE the hackathon disqualifier.
    assert settings.MAX_DRAWDOWN_PCT < settings.DISQUALIFY_DRAWDOWN_PCT


def test_scorer_weights_sum_to_one():
    total = (
        settings.WEIGHT_ONCHAIN_FLOW
        + settings.WEIGHT_SOCIAL_VELOCITY
        + settings.WEIGHT_SOCIAL_AGREEMENT
        + settings.WEIGHT_CMC_STRUCTURAL
    )
    assert abs(total - 1.0) < 1e-9
