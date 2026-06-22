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
#   accumulation  -> social QUIETNESS is a BONUS. Score driven mainly by CMC momentum
#                    magnitude; HIGH social REDUCES the score (less edge left).
#   confirmation  -> social velocity + Twitter/Reddit agreement contribute POSITIVELY
#                    (momentum), but capped below a clean accumulation entry.
#   distribution  -> high social + negative CMC momentum drive the EXIT score up.
#   no_trade      -> score ~0.
# CMC momentum magnitude (WEIGHT_CMC_MOMENTUM, primary) + optional on-chain bonus
# (WEIGHT_ONCHAIN_BONUS) + the CMC structural OK term (WEIGHT_CMC_STRUCTURAL, veto
# handled separately) keep their meaning across setups.
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
    """Normalize |on-chain flow| to 0..1 (optional bonus axis). STRONG maps ~0.5; 2x to 1.0."""
    return _clamp01(abs(flow) / (settings.ONCHAIN_STRONG_FLOW_USD * 2))


def _momentum_magnitude(pct: float) -> float:
    """Normalize |CMC 1h momentum %| to 0..1 (primary axis). STRONG maps ~0.5; 2x to 1.0."""
    return _clamp01(abs(pct) / (settings.CMC_MOMENTUM_STRONG_PCT * 2))


def score(div: DivergenceSignal) -> Conviction:
    """Setup-conditional 0-100 score + direction. Deterministic core.

    NOT a flat weighted sum — see module docstring. Re-tune weights/thresholds via backtest.py.
    """
    # CMC veto is absolute, regardless of setup.
    if not div.structural_ok:
        return Conviction(div.symbol, "none", 0.0, 0.0,
                          f"{div.symbol}: vetoed by CMC structural layer (thin liquidity / funding)")

    m = _momentum_magnitude(div.cmc_momentum_pct)      # PRIMARY (CMC momentum)
    b = _flow_magnitude(div.onchain_flow_usd)          # optional on-chain bonus (0 unless RPC feeds it)
    primary = settings.WEIGHT_CMC_MOMENTUM * m + settings.WEIGHT_ONCHAIN_BONUS * b
    vel = div.social_velocity
    agree = 1.0 if div.reddit_agrees else 0.0
    struct = settings.WEIGHT_CMC_STRUCTURAL  # structural_ok already true here

    if div.setup is Setup.ACCUMULATION:
        # quiet social is the edge: bonus is near-full while retail is asleep, and only
        # fades as velocity climbs toward "hot". Spends the full social budget.
        quiet = _clamp01((settings.SOCIAL_VEL_HOT - vel) / settings.SOCIAL_VEL_HOT)
        raw = primary + ACC_SOCIAL_BUDGET * quiet + struct
        direction = "long"

    elif div.setup is Setup.CONFIRMATION:
        v = _clamp01(vel / (settings.SOCIAL_VEL_HOT * 2))
        raw = (primary
               + settings.WEIGHT_SOCIAL_VELOCITY * v
               + settings.WEIGHT_SOCIAL_AGREEMENT * agree
               + struct) * CONFIRMATION_CAP        # held below a clean accumulation
        direction = "long"

    elif div.setup is Setup.DISTRIBUTION:
        v = _clamp01(vel / (settings.SOCIAL_VEL_HOT * 2))
        raw = (primary
               + settings.WEIGHT_SOCIAL_VELOCITY * v
               + settings.WEIGHT_SOCIAL_AGREEMENT * agree
               + struct)
        direction = "exit"

    else:  # NO_TRADE
        return Conviction(div.symbol, "none", round(_momentum_magnitude(div.cmc_momentum_pct) * 20, 1),
                          0.0, f"{div.symbol}: no actionable divergence")

    sc = round(_clamp01(raw) * 100, 1)
    confidence = round(m, 2)
    rationale = make_rationale(div, sc, direction)
    return Conviction(div.symbol, direction, sc, confidence, rationale)


def _template_rationale(div: DivergenceSignal, sc: float, direction: str) -> str:
    mom, vel = div.cmc_momentum_pct, div.social_velocity
    if div.setup is Setup.ACCUMULATION:
        return (f"{div.symbol}: CMC momentum {mom:+.1f}% while social quiet (vel {vel:.1f}) "
                f"— early accumulation, {direction} @ {sc}")
    if div.setup is Setup.CONFIRMATION:
        return (f"{div.symbol}: CMC momentum {mom:+.1f}% with social rising (vel {vel:.1f}, "
                f"reddit {'agrees' if div.reddit_agrees else 'quiet'}) — momentum, {direction} @ {sc}")
    if div.setup is Setup.DISTRIBUTION:
        return (f"{div.symbol}: CMC momentum {mom:+.1f}% into social euphoria (vel {vel:.1f}) "
                f"— distribution, {direction} @ {sc}")
    return f"{div.symbol}: no actionable divergence"


_GEMINI_MODEL = "gemini-2.5-flash"  # pinned; native Vertex via ADC, no Model Garden enable


def make_rationale(div: DivergenceSignal, sc: float, direction: str) -> str:
    """One human-readable sentence for the demo. Off the hot path; never blocks a trade.

    Deterministic template by default. If VERTEX_PROJECT is set, upgrade to a Gemini
    Flash line via Vertex AI (ADC auth); ANY failure falls back to the template.
    """
    project = os.getenv("VERTEX_PROJECT")
    if not project:
        return _template_rationale(div, sc, direction)
    try:
        from google import genai                 # imported lazily on the rationale path
        from google.genai import types
        client = genai.Client(vertexai=True, project=project,
                              location=os.getenv("VERTEX_REGION", "us-central1"))
        facts = (f"token={div.symbol} setup={div.setup.value} cmc_momentum_pct={div.cmc_momentum_pct:+.2f} "
                 f"onchain_flow={div.onchain_flow_usd:+.0f} social_velocity={div.social_velocity:.2f} "
                 f"reddit_agrees={div.reddit_agrees} direction={direction} score={sc}")
        resp = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents="Write ONE terse trader sentence explaining this signal. Facts: " + facts,
            config=types.GenerateContentConfig(
                max_output_tokens=100,
                thinking_config=types.ThinkingConfig(thinking_budget=0),  # no thinking: cheap + fast
            ),
        )
        return resp.text.strip()
    except Exception as e:                       # auth/region/model issue -> template
        log.debug("Gemini rationale failed (%s) — using template", e)
        return _template_rationale(div, sc, direction)
