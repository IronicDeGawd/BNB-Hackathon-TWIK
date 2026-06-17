"""Core IP — detect exploitable disagreement between social hype and on-chain flow.

Setups:
  ACCUMULATION  (long, highest)  : on-chain flow strongly +, social velocity still low/flat
                                   (whales in before the crowd)
  CONFIRMATION  (long, lower)    : on-chain +, social rising, Reddit agreeing (more priced in)
  DISTRIBUTION  (exit/avoid)     : social euphoric (Twitter + Reddit hot) AND on-chain flow -
                                   (smart money selling into retail)
  NO_TRADE                       : ambiguous, or only one axis firing

Output: a structured DivergenceSignal per token (NOT a single number yet).
detect() reads already-collected signal objects — it does not call the collectors,
so the brain works with real on-chain flow plus synthetic/partial social inputs.
"""

from dataclasses import dataclass
from enum import Enum

from config import settings


class Setup(str, Enum):
    ACCUMULATION = "accumulation"
    CONFIRMATION = "confirmation"
    DISTRIBUTION = "distribution"
    NO_TRADE = "no_trade"


@dataclass
class DivergenceSignal:
    symbol: str
    setup: Setup
    onchain_flow_usd: float        # net smart-money flow used (USD if priced, else token units)
    social_velocity: float
    reddit_agrees: bool
    structural_ok: bool


def _flow_value(onchain) -> float:
    """Prefer USD flow; fall back to token-unit flow; 0 if no on-chain signal."""
    if onchain is None:
        return 0.0
    if getattr(onchain, "net_flow_usd", None) is not None:
        return onchain.net_flow_usd
    return getattr(onchain, "net_flow_tokens", 0.0)


def detect(symbol: str, twitter, reddit, onchain, cmc) -> DivergenceSignal:
    """Combine the four signal axes into a divergence classification for one token.

    Any axis may be None (a collector down / not built yet); the classification
    degrades safely. CMC is veto-only — missing CMC data does not block (structural_ok
    defaults True), it only vetoes when it reports a problem.
    """
    flow = _flow_value(onchain)
    velocity = getattr(twitter, "velocity", 0.0) if twitter is not None else 0.0
    reddit_agrees = (reddit is not None
                     and getattr(reddit, "activity", 0.0) >= settings.REDDIT_HOT_ACTIVITY)
    structural_ok = getattr(cmc, "structural_ok", True) if cmc is not None else True

    strong_in = flow >= settings.ONCHAIN_STRONG_FLOW_USD
    strong_out = flow <= -settings.ONCHAIN_STRONG_FLOW_USD
    social_hot = velocity >= settings.SOCIAL_VEL_HOT
    social_flat = velocity <= settings.SOCIAL_VEL_FLAT

    if strong_in and social_flat:
        setup = Setup.ACCUMULATION             # whales in before the crowd — best long
    elif strong_in and social_hot and reddit_agrees:
        setup = Setup.CONFIRMATION             # momentum, more priced in — weaker long
    elif strong_out and social_hot and reddit_agrees:
        setup = Setup.DISTRIBUTION             # smart money selling into euphoria — exit
    else:
        setup = Setup.NO_TRADE

    return DivergenceSignal(symbol, setup, flow, velocity, reddit_agrees, structural_ok)
