"""LLM confirm layer — a veto-only second opinion before a live entry.

Gemini 2.5 Flash (Vertex AI / ADC) sees the current signal PLUS recent history
(trades, signal trend, portfolio state) and may BLOCK a deterministic entry. It can
NEVER create or force a trade — the rule-based brain + risk gate remain the floor.

Disabled unless both VERTEX_PROJECT and LLM_CONFIRM are set. Any error or absence
=> ALLOW (fail-open), so an LLM outage never halts trading (and never costs a
qualification day). Decisions are logged.
"""

from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("conviction.llm_confirm")

_MODEL = "gemini-2.5-pro"      # veto judgment — sharper than flash, volume is tiny (one call/entry)


def _enabled() -> bool:
    return bool(os.getenv("VERTEX_PROJECT")) and \
        os.getenv("LLM_CONFIRM", "").strip().lower() in ("1", "true", "yes")


def _query_gemini(prompt: str) -> dict:
    """Single structured call to Gemini on Vertex; returns the parsed {allow, reason}."""
    from google import genai
    from google.genai import types
    client = genai.Client(vertexai=True, project=os.getenv("VERTEX_PROJECT"),
                          location=os.getenv("VERTEX_REGION", "us-central1"))
    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={"allow": types.Schema(type=types.Type.BOOLEAN),
                    "reason": types.Schema(type=types.Type.STRING)},
        required=["allow", "reason"])
    resp = client.models.generate_content(
        model=_MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=schema,
            max_output_tokens=1024))   # 2.5-pro always reasons; leave room for thinking + JSON
    return json.loads(resp.text)


def confirm(div, conv, mem, drawdown_pct: float, trades_today: int) -> tuple[bool, str]:
    """Veto-only review of a candidate entry. Returns (allow, reason).

    Fail-open: returns (True, ...) when disabled or on ANY error.
    """
    if not _enabled():
        return True, "llm-confirm disabled"
    try:
        recent_trades = mem.recent_trades(div.symbol, 5) if mem is not None else []
        recent_mentions = mem.recent_signals(div.symbol, "twitter", "mentions", 5) if mem is not None else []
        ctx = {
            "candidate": {"symbol": div.symbol, "setup": div.setup.value,
                          "net_flow_usd": round(div.onchain_flow_usd, 0),
                          "social_velocity": round(div.social_velocity, 2),
                          "reddit_agrees": div.reddit_agrees,
                          "direction": conv.direction, "score": conv.score},
            "recent_trades": recent_trades,
            "recent_mention_counts": recent_mentions,
            "portfolio": {"drawdown_pct": round(drawdown_pct, 2), "trades_today": trades_today},
        }
        prompt = (
            "You review entries for an autonomous BSC trading agent. A rule-based system already "
            "WANTS to enter this long; it passed conviction and risk gates. Your ONLY job is to "
            "BLOCK clearly unsound entries given the recent history — e.g. re-buying a token just "
            "sold, re-entering right after a failed entry, or adding while already deep in drawdown. "
            "When in doubt, ALLOW: the rules already vetted it. Set allow=false only with a concrete "
            "reason tied to the context.\n\nContext:\n" + json.dumps(ctx, default=str)
        )
        d = _query_gemini(prompt)
        allow = bool(d.get("allow", True))
        reason = str(d.get("reason", ""))[:200]
        if not allow:
            log.info("LLM vetoed %s: %s", div.symbol, reason)
        return allow, reason
    except Exception as e:                       # fail-open — never let the LLM halt trading
        log.warning("llm-confirm unavailable (%s) — allowing", e)
        return True, f"llm-confirm error: {e}"
