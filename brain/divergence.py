"""Core IP — detect exploitable disagreement between social hype and on-chain flow.

Setups (PRIMARY axis = CMC 1h price momentum; on-chain wallet flow is an optional bonus):
  ACCUMULATION  (long, highest)  : momentum strongly +, social velocity still low/flat
                                   (price moving before the crowd notices)
  CONFIRMATION  (long, lower)    : momentum +, social rising, Reddit agreeing (more priced in)
  DISTRIBUTION  (exit/avoid)     : social euphoric (Twitter + Reddit hot) AND momentum -
                                   (rolling over into retail euphoria)
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
    onchain_flow_usd: float        # OPTIONAL smart-money wallet flow (bonus; 0 unless a keyed RPC feeds it)
    social_velocity: float
    reddit_agrees: bool
    structural_ok: bool
    cmc_momentum_pct: float = 0.0  # PRIMARY axis — signed 1h % price move from CMC


def _flow_value(onchain) -> float:
    """Prefer USD flow; fall back to token-unit flow; 0 if no on-chain signal."""
    if onchain is None:
        return 0.0
    if getattr(onchain, "net_flow_usd", None) is not None:
        return onchain.net_flow_usd
    return getattr(onchain, "net_flow_tokens", 0.0)


def detect(symbol: str, twitter, reddit, onchain, cmc) -> DivergenceSignal:
    """Combine the signal axes into a divergence classification for one token.

    PRIMARY axis = CMC 1h price momentum (the "read markets via CMC" data source).
    On-chain wallet flow is an OPTIONAL bonus (0 unless a keyed RPC feeds it). Any axis
    may be None; classification degrades safely. CMC structural is veto-only (missing data
    does not block).
    """
    momentum = getattr(cmc, "momentum_pct", 0.0) if cmc is not None else 0.0  # PRIMARY %
    flow = _flow_value(onchain)                                               # optional bonus
    velocity = getattr(twitter, "velocity", 0.0) if twitter is not None else 0.0
    reddit_agrees = (reddit is not None
                     and getattr(reddit, "activity", 0.0) >= settings.REDDIT_HOT_ACTIVITY)
    structural_ok = getattr(cmc, "structural_ok", True) if cmc is not None else True

    strong_up = momentum >= settings.CMC_MOMENTUM_STRONG_PCT
    strong_down = momentum <= -settings.CMC_MOMENTUM_STRONG_PCT
    social_hot = velocity >= settings.SOCIAL_VEL_HOT
    social_flat = velocity <= settings.SOCIAL_VEL_FLAT

    if strong_up and social_flat:
        setup = Setup.ACCUMULATION             # price moving, crowd not there yet — best long
    elif strong_up and social_hot and reddit_agrees:
        setup = Setup.CONFIRMATION             # momentum, more priced in — weaker long
    elif strong_down and social_hot and reddit_agrees:
        setup = Setup.DISTRIBUTION             # falling into euphoria — exit
    else:
        setup = Setup.NO_TRADE

    return DivergenceSignal(symbol, setup, flow, velocity, reddit_agrees, structural_ok, momentum)
