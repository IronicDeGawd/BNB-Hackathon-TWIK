"""The eligible BEP-20 tokens (hackathon allowlist) + their BSC contract addresses.

SOURCE OF TRUTH for what the agent is allowed to touch. The risk gate calls
`is_eligible()` before EVERY trade — an off-list trade does not count toward scoring.

The list is the official 149-token universe from the BNB Hack: AI Trading Agent
Edition rules (see research/hackathon-rules.md). Trades outside it do not count.

# ============================================================================
# Addresses are still None — they are NOT on the critical path:
#   - The allowlist / qualification check works on SYMBOL alone (is_eligible).
#   - TWAK resolves swaps for execution; we don't need a local address table to trade.
#   - We only need real addresses for the ~25 WATCHLIST tokens we monitor on-chain
#     (signals/onchain.py reads Transfer logs by contract address).
# Resolve watchlist addresses against CMC (free during the hackathon) + verify each
# on-chain via symbol() (see experiment/onchain_flow.py) before live monitoring.
#
# Data notes from the official list:
#   - Source listed 149 line-items but SLX appears twice -> 148 unique symbols here.
#   - Case-variant collisions exist (USDf vs USDF). is_eligible() is case-insensitive,
#     so both return True (fine for the allowlist); address resolution must keep exact case.
#   - Some symbols are non-ASCII / meme tokens (币安人生, NIGHT, CHEEMS, ...) — kept for
#     completeness; they are unlikely watchlist candidates (thin / illiquid).
# ============================================================================
"""

# Official eligible universe — symbol -> BEP-20 address (None = unresolved).
# Order preserved from the rules page.
_ELIGIBLE_SYMBOLS: tuple[str, ...] = (
    "ETH", "USDT", "USDC", "XRP", "TRX", "DOGE", "ZEC", "ADA", "LINK", "BCH",
    "DAI", "TON", "USD1", "USDe", "M", "LTC", "AVAX", "SHIB", "XAUt", "WLFI",
    "H", "DOT", "UNI", "ASTER", "DEXE", "USDD", "ETC", "AAVE", "ATOM", "U",
    "STABLE", "FIL", "INJ", "币安人生", "NIGHT", "FET", "TUSD", "BONK", "PENGU", "CAKE",
    "SIREN", "LUNC", "ZRO", "KITE", "FDUSD", "BEAT", "PIEVERSE", "BTT", "NFT", "EDGE",
    "FLOKI", "LDO", "B", "FF", "PENDLE", "NEX", "STG", "AXS", "TWT", "HOME",
    "RAY", "COMP", "GWEI", "XCN", "GENIUS", "XPL", "BAT", "SKYAI", "APE", "IP",
    "SFP", "TAG", "NXPC", "AB", "SAHARA", "1INCH", "CHEEMS", "BANANAS31", "RIVER", "MYX",
    "RAVE", "SNX", "FORM", "LAB", "HTX", "USDf", "CTM", "BDX", "SLX", "UB",
    "DUCKY", "FRAX", "BILL", "WFI", "KOGE", "ALE", "FRXUSD", "USDF", "GOMINING", "VCNT",
    "GUA", "DUSD", "SMILEK", "0G", "BEAM", "MY", "SOON", "REAL", "Q", "AIOZ",
    "ZIG", "YFI", "TAC", "lisUSD", "CYS", "ZAMA", "TRIA", "HUMA", "PLUME", "ZIL",
    "XPR", "ZETA", "BabyDoge", "NILA", "ROSE", "VELO", "UAI", "BRETT", "OPEN", "BSB",
    "TOSHI", "BAS", "ACH", "AXL", "LUR", "ELF", "KAVA", "APR", "IRYS", "EURI",
    "XUSD", "BARD", "DUSK", "SUSHI", "PEAQ", "COAI", "BDCA", "XAUM",
)

# symbol -> checksummed BEP-20 address (None = unresolved, resolve for watchlist tokens)
from config.token_addresses import ADDRESSES as _ADDR  # noqa: E402
ELIGIBLE: dict[str, str | None] = {sym: _ADDR.get(sym) for sym in _ELIGIBLE_SYMBOLS}


def is_eligible(symbol_or_address: str) -> bool:
    """True if the symbol (or contract address) is on the eligible list.

    Case-insensitive on symbols (note: USDf/USDF both resolve True — fine for the
    allowlist). Address comparison is case-insensitive too.
    """
    if not symbol_or_address:
        return False
    key = symbol_or_address.strip()
    if key.upper() in _UPPER_INDEX:
        return True
    target = key.lower()
    return any(addr and addr.lower() == target for addr in ELIGIBLE.values())


# upper-cased symbol index for fast case-insensitive membership
_UPPER_INDEX = {sym.upper() for sym in _ELIGIBLE_SYMBOLS}


def address_of(symbol: str) -> str | None:
    """Return the BEP-20 address for an EXACT-cased symbol, or None if unresolved."""
    return ELIGIBLE.get(symbol.strip())


def unresolved() -> list[str]:
    """Symbols still missing an address. Only the watchlist subset must be empty before
    live on-chain monitoring; the full list does not need addresses to trade."""
    return [sym for sym, addr in ELIGIBLE.items() if addr is None]
