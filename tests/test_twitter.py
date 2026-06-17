"""Tests for the twitter collector — pure query/count/velocity + budget + no-key. No network."""

import pytest

from config import settings
from signals import twitter
from signals.twitter import build_query, count_mentions, _velocity
from brain.memory import Memory


def test_build_query_batches_cashtags():
    q = build_query(["CAKE", "AVAX"])
    assert "$CAKE OR $AVAX" in q and "-filter:retweets" in q


def test_count_mentions_cashtag_and_word():
    texts = ["loving $CAKE today", "CAKE is great", "$AVAX to the moon", "no tokens here"]
    counts = count_mentions(texts, ["CAKE", "AVAX"])
    assert counts == {"CAKE": 2, "AVAX": 1}


def test_count_mentions_avoids_substring_false_positive():
    # "PANCAKE" must not count as a CAKE mention (word boundary)
    assert count_mentions(["PANCAKESWAP news"], ["CAKE"]) == {"CAKE": 0}


def test_velocity_against_baseline():
    mem = Memory(db_path=":memory:")
    # seed a 24h baseline of 10 mentions
    mem.log_signal("CAKE", "twitter", "mentions", 10, ts=0)
    # baseline() uses now_fn; with default clock the seeded ts=0 is too old, so force recent
    mem2 = Memory(db_path=":memory:", now_fn=lambda: 1000.0)
    mem2.log_signal("CAKE", "twitter", "mentions", 10, ts=900.0)
    assert _velocity("CAKE", 20, mem2) == 2.0      # 20 / 10
    mem.close(); mem2.close()


def test_velocity_neutral_without_baseline():
    assert _velocity("CAKE", 5, None) == twitter.NEUTRAL_VELOCITY


def test_collect_without_key_is_neutral(monkeypatch):
    monkeypatch.delenv("TWITTER_API_KEY", raising=False)
    out = twitter.collect(["CAKE", "AVAX"])
    assert all(v.velocity == twitter.NEUTRAL_VELOCITY and v.mentions == 0 for v in out.values())


def test_budget_guard_stops_at_limit(monkeypatch):
    monkeypatch.setenv("TWITTER_API_KEY", "x")
    monkeypatch.setattr(settings, "TWITTER_DAILY_BUDGET", 0)   # already at budget
    twitter._call_day = ""                                     # force re-eval
    out = twitter.collect(["CAKE"])
    assert out["CAKE"].velocity == twitter.NEUTRAL_VELOCITY    # neutral, no fetch attempted
