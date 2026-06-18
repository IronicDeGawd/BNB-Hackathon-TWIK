"""The ~25 actively-monitored tokens — a liquid subset of ELIGIBLE.

Quality over quantity: thin tokens add noise and slippage. Each entry MUST be
(a) on the eligible list, (b) backed by a real BSC DEX pool with depth.

# TODO: confirm each has a deep BSC pool before live trading; trim/extend to ~25.
"""

from config.tokens import is_eligible

# Candidate watchlist from the spec, extended to ~25. Verify pool depth before live.
WATCHLIST: list[str] = [
    # original spec set
    "CAKE", "AVAX", "LINK", "UNI", "AAVE",
    "DOT", "ATOM", "INJ", "FET", "BONK",
    "FLOKI", "PENGU", "TWT", "SFP", "ASTER",
    # extension: liquid + social-active, all on ELIGIBLE (confirm BSC pool depth before live)
    "XRP", "DOGE", "SHIB", "TRX", "ADA",
    "TON", "PENDLE", "AXS", "APE", "LDO",
]


def validate() -> list[str]:
    """Return watchlist symbols that are NOT on the eligible list (should be empty)."""
    return [sym for sym in WATCHLIST if not is_eligible(sym)]
