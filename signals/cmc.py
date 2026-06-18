"""Structural sanity layer — CMC (CoinMarketCap) data, free for the hackathon.

Does NOT generate trade signals. It VETOES: block a trade when liquidity is too thin
(slippage risk) or funding is stretched hard against the intended direction.

Uses the Pro REST API directly (deterministic, no tool-selection guesswork):
  - Fear & Greed : GET /v3/fear-and-greed/latest
  - Liquidity    : GET /v2/cryptocurrency/quotes/latest?symbol=... (24h volume as the proxy)
  - Funding rate : per-pair derivatives endpoint (deferred — left None for now)
Auth header: X-CMC_PRO_API_KEY (env CMC_API_KEY).

Veto-only: with no key or on any API failure, structural_ok defaults TRUE (do not block).
The decision itself (_structural_ok) is a pure, unit-tested function.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

from config import settings

log = logging.getLogger("conviction.cmc")

BASE = "https://pro-api.coinmarketcap.com"
TIMEOUT = 15


@dataclass
class CmcSignal:
    symbol: str
    liquidity_usd: float | None
    funding_rate: float | None
    structural_ok: bool             # False => veto any trade on this token


# --------------------------------------------------------------------------- #
# Pure veto decision (unit-tested)                                            #
# --------------------------------------------------------------------------- #
def _structural_ok(liquidity_usd: float | None, funding_rate: float | None,
                   intended_direction: str) -> tuple[bool, str]:
    """Decide the veto. Missing data never vetoes (veto-only layer)."""
    if liquidity_usd is not None and liquidity_usd < settings.CMC_MIN_LIQUIDITY_USD:
        return False, (f"thin liquidity ${liquidity_usd:,.0f} < "
                       f"${settings.CMC_MIN_LIQUIDITY_USD:,.0f}")
    if funding_rate is not None and abs(funding_rate) >= settings.CMC_MAX_FUNDING_ABS:
        # high positive funding crowds longs; high negative crowds shorts
        if intended_direction == "long" and funding_rate >= settings.CMC_MAX_FUNDING_ABS:
            return False, f"funding {funding_rate:+.3f} stretched against a long"
        if intended_direction == "exit" and funding_rate <= -settings.CMC_MAX_FUNDING_ABS:
            return False, f"funding {funding_rate:+.3f} stretched against an exit"
    return True, "ok"


# --------------------------------------------------------------------------- #
# Network layer                                                               #
# --------------------------------------------------------------------------- #
def _api_key() -> str | None:
    return os.getenv("CMC_API_KEY") or None


def _get(path: str, params: dict | None = None) -> dict:
    key = _api_key()
    if not key:
        raise RuntimeError("no CMC_API_KEY configured")
    r = requests.get(BASE + path, params=params or {},
                     headers={"X-CMC_PRO_API_KEY": key, "Accept": "application/json"},
                     timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _use_mcp() -> bool:
    """Route through the CMC Agent Hub MCP when CMC_TRANSPORT=mcp (else classic REST)."""
    return os.getenv("CMC_TRANSPORT", "rest").strip().lower() == "mcp"


def _dig(d, *paths):
    """First non-None value found at any of the given key-paths in a nested dict."""
    for path in paths:
        cur = d
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                break
        if cur is not None:
            return cur
    return None


def fear_greed() -> int:
    """Global Fear & Greed index (0-100). Neutral 50 if unavailable.

    Uses the Agent Hub MCP when CMC_TRANSPORT=mcp; always falls back to REST on error.
    """
    if _use_mcp():
        try:
            from signals import cmc_mcp
            d = cmc_mcp.call_tool(cmc_mcp.TOOL_GLOBAL)
            val = _dig(d, ["fear_and_greed", "value"], ["data", "fear_and_greed", "value"],
                       ["fearAndGreed", "value"], ["value"])
            if val is not None:
                return int(val)
            log.warning("MCP fear&greed: value not found in response -> REST")
        except Exception as e:
            log.warning("MCP fear&greed failed (%s) -> REST", e)
    try:
        return int(_get("/v3/fear-and-greed/latest")["data"]["value"])
    except Exception as e:
        log.warning("fear & greed unavailable: %s", e)
        return 50


def _fetch_liquidity(symbols: list[str]) -> dict[str, float | None]:
    """24h USD volume per symbol (liquidity proxy), batched in one call.

    Uses the Agent Hub MCP when CMC_TRANSPORT=mcp; falls back to REST on error.
    """
    if _use_mcp():
        try:
            from signals import cmc_mcp
            d = cmc_mcp.call_tool(cmc_mcp.TOOL_QUOTES, {"symbol": ",".join(symbols), "convert": "USD"})
            data = _dig(d, ["data"]) or d
            out: dict[str, float | None] = {}
            for sym in symbols:
                entry = data.get(sym) if isinstance(data, dict) else None
                rec = entry[0] if isinstance(entry, list) and entry else entry
                out[sym] = float(_dig(rec or {}, ["quote", "USD", "volume_24h"], ["volume_24h"]) or 0) or None
            if any(v is not None for v in out.values()):
                return out
            log.warning("MCP quotes: no volume parsed -> REST")
        except Exception as e:
            log.warning("MCP liquidity failed (%s) -> REST", e)
    data = _get("/v2/cryptocurrency/quotes/latest",
                {"symbol": ",".join(symbols), "convert": "USD"}).get("data", {})
    out: dict[str, float | None] = {}
    for sym in symbols:
        entry = data.get(sym)
        rec = entry[0] if isinstance(entry, list) and entry else entry
        try:
            out[sym] = float(rec["quote"]["USD"]["volume_24h"])
        except (TypeError, KeyError, IndexError):
            out[sym] = None
    return out


def collect(watchlist: list[str],
            intended_direction: dict[str, str]) -> dict[str, CmcSignal]:
    """Per-token structural read + veto decision. Veto-only and fault-tolerant:
    no key or any failure -> structural_ok True for all (never blocks the loop)."""
    if not _api_key():
        log.warning("no CMC_API_KEY — structural layer passive (no vetoes)")
        return {s: CmcSignal(s, None, None, True) for s in watchlist}

    try:
        liquidity = _fetch_liquidity(watchlist)
    except Exception as e:
        log.warning("CMC liquidity fetch failed: %s — passive", e)
        return {s: CmcSignal(s, None, None, True) for s in watchlist}

    out: dict[str, CmcSignal] = {}
    for sym in watchlist:
        liq = liquidity.get(sym)
        funding = None                       # per-pair funding deferred (see module docstring)
        ok, reason = _structural_ok(liq, funding, intended_direction.get(sym, "long"))
        if not ok:
            log.info("CMC veto %s: %s", sym, reason)
        out[sym] = CmcSignal(sym, liq, funding, ok)
    return out
