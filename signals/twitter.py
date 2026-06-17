"""PRIMARY social signal — Twitter/X mention velocity via a cheap wrapper.

Per cycle: ONE batched query for the whole watchlist (an `($A OR $B ...)` cashtag query),
count tweets mentioning each token, and compute velocity = mentions(now) / 24h baseline
(read from memory). A hard daily-budget guard degrades gracefully.

Wrapper: twitterapi.io — GET /twitter/tweet/advanced_search, header `X-API-Key`,
params `query` + `queryType=Latest` (see research/twitter-wrapper.md).

Output per token: TwitterSignal(symbol, mentions, velocity, sentiment).
Fault-tolerant: no key, budget exhausted, or any failure -> neutral signals (velocity 1.0).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from config import settings

log = logging.getLogger("conviction.twitter")

ENDPOINT = "https://api.twitterapi.io/twitter/tweet/advanced_search"
TIMEOUT = 20
NEUTRAL_VELOCITY = 1.0

_calls_today = 0
_call_day = ""


@dataclass
class TwitterSignal:
    symbol: str
    mentions: int
    velocity: float                 # mentions(now) / 24h baseline; 1.0 = neutral/unknown
    sentiment: float | None = None


# --------------------------------------------------------------------------- #
# Pure core (unit-tested)                                                     #
# --------------------------------------------------------------------------- #
def build_query(symbols: list[str]) -> str:
    """One batched cashtag OR query covering the whole watchlist."""
    cashtags = " OR ".join(f"${s}" for s in symbols)
    return f"({cashtags}) -filter:retweets lang:en"


def count_mentions(texts: list[str], symbols: list[str]) -> dict[str, int]:
    """Tweets mentioning each symbol (by $cashtag or standalone word). Case-insensitive."""
    counts = {s: 0 for s in symbols}
    patterns = {s: re.compile(rf"(?<![A-Za-z0-9])\$?{re.escape(s)}(?![A-Za-z0-9])", re.I)
                for s in symbols}
    for text in texts:
        for s in symbols:
            if patterns[s].search(text or ""):
                counts[s] += 1
    return counts


def _velocity(symbol: str, mentions: int, mem) -> float:
    if mem is None:
        return NEUTRAL_VELOCITY
    base = mem.baseline(symbol, "twitter", "mentions", settings.SOCIAL_BASELINE_HOURS)
    return mentions / base if base > 0 else NEUTRAL_VELOCITY


# --------------------------------------------------------------------------- #
# Budget + network                                                           #
# --------------------------------------------------------------------------- #
def calls_used_today() -> int:
    return _calls_today


def _bump_budget() -> bool:
    """Increment the daily call counter (resetting on UTC date change). False if over budget."""
    global _calls_today, _call_day
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if day != _call_day:
        _call_day, _calls_today = day, 0
    if _calls_today >= settings.TWITTER_DAILY_BUDGET:
        return False
    _calls_today += 1
    return True


def _neutral(watchlist) -> dict[str, TwitterSignal]:
    return {s: TwitterSignal(s, 0, NEUTRAL_VELOCITY) for s in watchlist}


def _fetch(query: str) -> list[str]:
    r = requests.get(ENDPOINT, params={"query": query, "queryType": "Latest"},
                     headers={"X-API-Key": os.getenv("TWITTER_API_KEY", "")}, timeout=TIMEOUT)
    r.raise_for_status()
    return [t.get("text", "") for t in r.json().get("tweets", [])]


def collect(watchlist: list[str], mem=None) -> dict[str, TwitterSignal]:
    """Batched mention pull + velocity for the watchlist. Never raises into the loop."""
    if not os.getenv("TWITTER_API_KEY"):
        log.warning("no TWITTER_API_KEY — twitter signal neutral")
        return _neutral(watchlist)
    if not _bump_budget():
        log.warning("twitter daily budget (%d) reached — neutral this cycle",
                    settings.TWITTER_DAILY_BUDGET)
        return _neutral(watchlist)
    try:
        texts = _fetch(build_query(watchlist))
    except Exception as e:
        log.warning("twitter fetch failed: %s — neutral", e)
        return _neutral(watchlist)

    counts = count_mentions(texts, watchlist)
    out: dict[str, TwitterSignal] = {}
    for s in watchlist:
        m = counts[s]
        if mem is not None:
            mem.log_signal(s, "twitter", "mentions", m)   # feed future baselines
        out[s] = TwitterSignal(s, m, _velocity(s, m, mem))
    return out
