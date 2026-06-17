"""SECONDARY social signal — Reddit sentiment + activity (a second, independent axis).

Do NOT just average with Twitter. Fallback-quality: if it breaks mid-competition the agent
keeps running on Twitter + on-chain alone. Everything is wrapped — this never crashes the loop.

Path: official Reddit API via PRAW (reliable; the research flags Agent Reach as a fragile
single-maintainer tool, so PRAW is primary here). Subreddits: r/CryptoCurrency,
r/BNBChainOfficial, plus token chatter. Anonymous reads are 403-blocked, so credentials are
required (REDDIT_CLIENT_ID/SECRET); without them the layer is passive.

Output per token: RedditSignal(symbol, sentiment, activity).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from config import settings

log = logging.getLogger("conviction.reddit")

SUBREDDITS = ["CryptoCurrency", "BNBChainOfficial"]
FETCH_LIMIT = 200

_POS = {"moon", "bull", "bullish", "pump", "buy", "long", "gain", "gains", "up",
        "green", "rally", "breakout", "accumulate", "send", "ath"}
_NEG = {"dump", "bear", "bearish", "sell", "rug", "rugpull", "crash", "scam",
        "down", "red", "dead", "exit", "short", "fud"}
_WORD = re.compile(r"[a-z0-9]+")


@dataclass
class RedditSignal:
    symbol: str
    sentiment: float                # -1..1
    activity: float                 # 0..1 (normalized post volume)


# --------------------------------------------------------------------------- #
# Pure core (unit-tested)                                                     #
# --------------------------------------------------------------------------- #
def text_sentiment(text: str) -> float:
    """Lexicon sentiment in -1..1 (0 if no signal words)."""
    toks = _WORD.findall((text or "").lower())
    p = sum(t in _POS for t in toks)
    n = sum(t in _NEG for t in toks)
    return (p - n) / (p + n) if (p + n) else 0.0


def classify(texts: list[str], symbols: list[str]) -> dict[str, RedditSignal]:
    """Per symbol: mean sentiment of mentioning posts + normalized activity."""
    pats = {s: re.compile(rf"(?<![A-Za-z0-9])\$?{re.escape(s)}(?![A-Za-z0-9])", re.I)
            for s in symbols}
    norm = settings.REDDIT_ACTIVITY_NORM_POSTS
    out: dict[str, RedditSignal] = {}
    for s in symbols:
        hits = [t for t in texts if pats[s].search(t or "")]
        if hits:
            sentiment = sum(text_sentiment(t) for t in hits) / len(hits)
            activity = min(len(hits) / norm, 1.0)
        else:
            sentiment, activity = 0.0, 0.0
        out[s] = RedditSignal(s, round(sentiment, 3), round(activity, 3))
    return out


# --------------------------------------------------------------------------- #
# Network                                                                     #
# --------------------------------------------------------------------------- #
def _passive(watchlist) -> dict[str, RedditSignal]:
    return {s: RedditSignal(s, 0.0, 0.0) for s in watchlist}


def _fetch_texts() -> list[str]:
    import praw  # lazy optional dependency
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "conviction-agent/0.1"),
        username=os.getenv("REDDIT_ACCOUNT_USER") or None,
        password=os.getenv("REDDIT_ACCOUNT_PASS") or None,
        check_for_async=False,
    )
    texts: list[str] = []
    for sub in SUBREDDITS:
        for post in reddit.subreddit(sub).new(limit=FETCH_LIMIT):
            texts.append(f"{post.title} {getattr(post, 'selftext', '')}")
    return texts


def collect(watchlist: list[str]) -> dict[str, RedditSignal]:
    """Pull recent posts and score per token. Never raises — passive on any problem."""
    if not os.getenv("REDDIT_CLIENT_ID"):
        log.warning("no REDDIT_CLIENT_ID — reddit signal passive")
        return _passive(watchlist)
    try:
        return classify(_fetch_texts(), watchlist)
    except Exception as e:                       # ImportError / auth / network -> degrade
        log.warning("reddit fetch failed: %s — passive", e)
        return _passive(watchlist)
