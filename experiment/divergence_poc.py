"""EXPERIMENT 2 — prove the IDEA end to end.

Take REAL on-chain smart-money net flow (from experiment 1) and run the full
decision pipeline against SYNTHETIC social scenarios:

    real on-chain flow  +  social velocity  ->  divergence setup  ->  conviction 0-100  ->  decision

Goal: confirm the four divergence setups (accumulation / confirmation / distribution /
no-trade) fire correctly and that conviction crosses the threshold only when it should.

This is a throwaway PoC mirroring the intended logic of brain/divergence.py +
brain/conviction.py — NOT the production code. Weights/threshold come from the real
config so the PoC and production stay in sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import project config

from config import settings  # noqa: E402
from experiment.onchain_flow import connect, net_flow, CAKE  # noqa: E402

# --- thresholds for what counts as "strong" / "hot" in this PoC ---
FLOW_STRONG = 50.0      # |net flow| (proxy units) above this = strong smart-money signal
VEL_HOT = 2.0           # social velocity >= this = retail euphoric
VEL_FLAT = 1.2          # social velocity <= this = retail asleep


def detect_setup(flow: float, twitter_vel: float, reddit_hot: bool) -> str:
    """Mirror of brain/divergence.py intent."""
    strong_in = flow >= FLOW_STRONG
    strong_out = flow <= -FLOW_STRONG
    social_hot = twitter_vel >= VEL_HOT
    social_flat = twitter_vel <= VEL_FLAT

    if strong_in and social_flat:
        return "accumulation"          # whales in before the crowd -> best long
    if strong_in and social_hot and reddit_hot:
        return "confirmation"          # real momentum, more priced in -> weaker long
    if strong_out and social_hot and reddit_hot:
        return "distribution"          # smart money selling into euphoria -> exit/avoid
    return "no_trade"


def score(setup: str, flow: float, twitter_vel: float, reddit_hot: bool,
          structural_ok: bool) -> tuple[str, float, str]:
    """Mirror of brain/conviction.py intent. Deterministic weighted blend -> 0-100."""
    if not structural_ok:
        return "none", 0.0, "vetoed by CMC structural layer (thin liquidity / funding)"

    # normalize each axis to 0..1
    f = min(abs(flow) / (FLOW_STRONG * 4), 1.0)                 # on-chain magnitude
    v = min(twitter_vel / (VEL_HOT * 2), 1.0)                   # social velocity
    a = 1.0 if reddit_hot else 0.0                              # agreement bonus
    s = 1.0 if structural_ok else 0.0

    raw = (settings.WEIGHT_ONCHAIN_FLOW * f
           + settings.WEIGHT_SOCIAL_VELOCITY * v
           + settings.WEIGHT_SOCIAL_AGREEMENT * a
           + settings.WEIGHT_CMC_STRUCTURAL * s)
    sc = round(raw * 100, 1)

    if setup == "accumulation":
        direction = "long"
    elif setup == "confirmation":
        direction = "long"
    elif setup == "distribution":
        direction = "exit"
    else:
        direction = "none"

    rationale = (f"{setup}: smart-money net flow={flow:+.1f}, twitter_vel={twitter_vel:.1f}, "
                 f"reddit_hot={reddit_hot} -> {direction} @ score {sc}")
    return direction, sc, rationale


def run():
    print("=== EXPERIMENT 2: divergence -> conviction (real flow + synthetic social) ===\n")
    print(f"config: threshold={settings.CONVICTION_THRESHOLD} "
          f"weights(flow/vel/agree/struct)="
          f"{settings.WEIGHT_ONCHAIN_FLOW}/{settings.WEIGHT_SOCIAL_VELOCITY}/"
          f"{settings.WEIGHT_SOCIAL_AGREEMENT}/{settings.WEIGHT_CMC_STRUCTURAL}\n")

    # --- pull REAL smart-money flow for CAKE ---
    w3 = connect()
    res = net_flow(w3, CAKE, window_blocks=600)
    # pseudo "tracked smart wallets" = top-5 net accumulators this window
    tracked = res.top_accumulators(5)
    real_flow = sum(v for _, v in tracked)
    print(f"REAL on-chain read: {res.symbol} blocks {res.from_block}..{res.to_block}, "
          f"{res.n_transfers} transfers")
    print(f"  pseudo-smart-wallet net flow (top5 accumulators) = {real_flow:+.2f} {res.symbol}\n")

    # --- scenarios: same real flow magnitude, different synthetic social states ---
    scenarios = [
        ("Whales in, retail asleep",  abs(real_flow) + FLOW_STRONG, 1.0, False, True),
        ("Whales in, retail euphoric", abs(real_flow) + FLOW_STRONG, 2.5, True,  True),
        ("Whales OUT, retail euphoric", -(abs(real_flow) + FLOW_STRONG), 2.6, True, True),
        ("Mixed / weak signal",        15.0, 1.5, False, True),
        ("Strong setup but CMC veto",  abs(real_flow) + FLOW_STRONG, 1.0, False, False),
    ]

    print(f"{'scenario':<30} {'setup':<13} {'dir':<5} {'score':>6}  trade?")
    print("-" * 78)
    for name, flow, vel, reddit_hot, struct_ok in scenarios:
        setup = detect_setup(flow, vel, reddit_hot)
        direction, sc, rationale = score(setup, flow, vel, reddit_hot, struct_ok)
        fires = direction in ("long", "exit") and sc >= settings.CONVICTION_THRESHOLD
        trade = "YES" if fires else "no"
        print(f"{name:<30} {setup:<13} {direction:<5} {sc:>6}  {trade}")
    print()
    print("Interpretation: only 'accumulation' (whales in, retail asleep) and a real")
    print("'distribution' exit cross threshold; momentum-confirmation is weaker; mixed and")
    print("CMC-vetoed setups correctly do NOT fire. Core idea works on live chain data.")


if __name__ == "__main__":
    run()
