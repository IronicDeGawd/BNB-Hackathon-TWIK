"""Tests for the reddit collector — pure sentiment/activity + no-creds passive. No network."""

from config import settings
from signals import reddit
from signals.reddit import text_sentiment, classify


def test_sentiment_positive_negative_neutral():
    assert text_sentiment("bullish moon pump") > 0
    assert text_sentiment("rug scam dump") < 0
    assert text_sentiment("the weather is fine") == 0.0


def test_classify_activity_and_sentiment():
    texts = ["$CAKE to the moon, bullish", "CAKE looking strong, buy", "unrelated post"]
    out = classify(texts, ["CAKE", "AVAX"])
    assert out["CAKE"].sentiment > 0
    assert out["CAKE"].activity == round(2 / settings.REDDIT_ACTIVITY_NORM_POSTS, 3)
    assert out["AVAX"].activity == 0.0 and out["AVAX"].sentiment == 0.0


def test_classify_activity_caps_at_one():
    many = ["$CAKE bull"] * (settings.REDDIT_ACTIVITY_NORM_POSTS * 3)
    out = classify(many, ["CAKE"])
    assert out["CAKE"].activity == 1.0


def test_word_boundary_no_false_positive():
    out = classify(["PANCAKESWAP update"], ["CAKE"])
    assert out["CAKE"].activity == 0.0


def test_collect_without_creds_is_passive(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    out = reddit.collect(["CAKE", "AVAX"])
    assert all(v.sentiment == 0.0 and v.activity == 0.0 for v in out.values())
