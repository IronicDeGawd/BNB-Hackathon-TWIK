"""Turn a DivergenceSignal into a 0-100 conviction score.

DECISION IS DETERMINISTIC (rules-based) — predictable for a PnL competition. The LLM
is used ONLY to generate `rationale_text` (human-readable "why", for the demo).
Weights live in config/settings.py.

# ============================================================================
# SCORING IS SETUP-CONDITIONAL — do NOT use a flat weighted sum.
# ----------------------------------------------------------------------------
# The experiment/divergence_poc.py PoC proved a flat sum is BACKWARDS: it rewards
# social velocity, but our PRIME setup (early accumulation) has LOW social BY
# DEFINITION, so it scored below threshold while a weaker setup fired. The social
# term must be interpreted per setup, not added blindly. See experiment/FINDINGS.md.
#
# Per-setup treatment of the social-velocity axis:
#   accumulation  -> social QUIETNESS is a BONUS. Score driven mainly by on-chain
#                    flow magnitude; HIGH social REDUCES the score (less edge left).
#   confirmation  -> social velocity + Twitter/Reddit agreement contribute POSITIVELY
#                    (momentum), but capped below a clean accumulation entry.
#   distribution  -> high social + negative on-chain flow drive the EXIT score up.
#   no_trade      -> score ~0.
# On-chain flow magnitude (WEIGHT_ONCHAIN_FLOW) and the CMC structural OK term
# (WEIGHT_CMC_STRUCTURAL, veto handled separately) keep their meaning across setups.
# ============================================================================

Output: {symbol, direction: long|exit|none, score, confidence, rationale_text}.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from config import settings
from brain.divergence import DivergenceSignal, Setup

log = logging.getLogger("conviction.score")

# Confirmation is "more priced in" than a clean accumulation entry, so its ceiling is
# held below accumulation's. Accumulation has no Twitter/Reddit agreement axis, so it
# spends the whole social budget on the quiet bonus instead.
CONFIRMATION_CAP = 0.8
ACC_SOCIAL_BUDGET = settings.WEIGHT_SOCIAL_VELOCITY + settings.WEIGHT_SOCIAL_AGREEMENT


@dataclass
class Conviction:
    symbol: str
    direction: str               # "long" | "exit" | "none"
    score: float                 # 0-100
    confidence: float            # 0-1
    rationale_text: str


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _flow_magnitude(flow: float) -> float:
    """Normalize |flow| to 0..1. STRONG_FLOW maps to ~0.5; 2x to 1.0."""
    return _clamp01(abs(flow) / (settings.ONCHAIN_STRONG_FLOW_USD * 2))


def score(div: DivergenceSignal) -> Conviction:
    """Setup-conditional 0-100 score + direction. Deterministic core.

    NOT a flat weighted sum — see module docstring. Re-tune weights/thresholds via backtest.py.
    """
    # CMC veto is absolute, regardless of setup.
    if not div.structural_ok:
        return Conviction(div.symbol, "none", 0.0, 0.0,
                          f"{div.symbol}: vetoed by CMC structural layer (thin liquidity / funding)")

    f = _flow_magnitude(div.onchain_flow_usd)
    vel = div.social_velocity
    agree = 1.0 if div.reddit_agrees else 0.0
    struct = settings.WEIGHT_CMC_STRUCTURAL  # structural_ok already true here

    if div.setup is Setup.ACCUMULATION:
        # quiet social is the edge: bonus is near-full while retail is asleep, and only
        # fades as velocity climbs toward "hot". Spends the full social budget.
        quiet = _clamp01((settings.SOCIAL_VEL_HOT - vel) / settings.SOCIAL_VEL_HOT)
        raw = (settings.WEIGHT_ONCHAIN_FLOW * f
               + ACC_SOCIAL_BUDGET * quiet
               + struct)
        direction = "long"

    elif div.setup is Setup.CONFIRMATION:
        v = _clamp01(vel / (settings.SOCIAL_VEL_HOT * 2))
        raw = (settings.WEIGHT_ONCHAIN_FLOW * f
               + settings.WEIGHT_SOCIAL_VELOCITY * v
               + settings.WEIGHT_SOCIAL_AGREEMENT * agree
               + struct) * CONFIRMATION_CAP        # held below a clean accumulation
        direction = "long"

    elif div.setup is Setup.DISTRIBUTION:
        v = _clamp01(vel / (settings.SOCIAL_VEL_HOT * 2))
        raw = (settings.WEIGHT_ONCHAIN_FLOW * f
               + settings.WEIGHT_SOCIAL_VELOCITY * v
               + settings.WEIGHT_SOCIAL_AGREEMENT * agree
               + struct)
        direction = "exit"

    else:  # NO_TRADE
        return Conviction(div.symbol, "none", round(_flow_magnitude(div.onchain_flow_usd) * 20, 1),
                          0.0, f"{div.symbol}: no actionable divergence")

    sc = round(_clamp01(raw) * 100, 1)
    confidence = round(f, 2)
    rationale = make_rationale(div, sc, direction)
    return Conviction(div.symbol, direction, sc, confidence, rationale)


def _template_rationale(div: DivergenceSignal, sc: float, direction: str) -> str:
    flow, vel = div.onchain_flow_usd, div.social_velocity
    if div.setup is Setup.ACCUMULATION:
        return (f"{div.symbol}: smart money {flow:+,.0f} while social quiet (vel {vel:.1f}) "
                f"— early accumulation, {direction} @ {sc}")
    if div.setup is Setup.CONFIRMATION:
        return (f"{div.symbol}: smart money {flow:+,.0f} with social rising (vel {vel:.1f}, "
                f"reddit {'agrees' if div.reddit_agrees else 'quiet'}) — momentum, {direction} @ {sc}")
    if div.setup is Setup.DISTRIBUTION:
        return (f"{div.symbol}: smart money {flow:+,.0f} into social euphoria (vel {vel:.1f}) "
                f"— distribution, {direction} @ {sc}")
    return f"{div.symbol}: no actionable divergence"


def make_rationale(div: DivergenceSignal, sc: float, direction: str) -> str:
    """One human-readable sentence for the demo. Off the hot path; never blocks a trade.

    Deterministic template by default. If ANTHROPIC_API_KEY is set, optionally upgrade to
    an LLM-written line; ANY failure falls back to the template.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _template_rationale(div, sc, direction)
    try:
        import anthropic  # imported lazily — optional dependency on the rationale path
        client = anthropic.Anthropic()
        facts = (f"token={div.symbol} setup={div.setup.value} net_flow={div.onchain_flow_usd:+.0f} "
                 f"social_velocity={div.social_velocity:.2f} reddit_agrees={div.reddit_agrees} "
                 f"direction={direction} score={sc}")
        msg = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=80,
            messages=[{"role": "user", "content":
                       "Write ONE terse trader sentence explaining this signal. Facts: " + facts}],
        )
        return msg.content[0].text.strip()
    except Exception as e:                       # network/key/SDK issue -> template
        log.debug("LLM rationale failed (%s) — using template", e)
        return _template_rationale(div, sc, direction)
