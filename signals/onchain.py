"""The real edge — BSC smart-money net-flow tracker (free, public RPC).

For each watchlist token, compute net flow (received - sent) by a curated set of
"smart wallets" over a trailing time window, from Transfer event logs. Positive net
= accumulation (whales buying), negative = distribution.

Promoted from experiment/onchain_flow.py (proven live on CAKE). Findings baked in:
  - public bsc-dataseed limits/blocks eth_getLogs -> use a getLogs-capable RPC
    (bsc-rpc.publicnode.com works keyless; set BSC_RPC_URL for a private node).
  - BSC is POA -> inject ExtraDataToPOAMiddleware at layer 0.
  - chunk getLogs to stay under public block-range limits.
  - server-side topic filtering by wallet set (argument_filters) keeps logs tiny.

Output per token: OnchainSignal(symbol, net_flow_tokens, net_flow_usd, n_wallets_active, direction).
Fault-tolerant: a failure on one token degrades to a flat signal, never raises into the loop.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from config import settings
from config.tokens import address_of

log = logging.getLogger("conviction.onchain")

DEFAULT_RPC = "https://bsc-rpc.publicnode.com"
CHUNK_BLOCKS = 1000          # under the ~2000 public getLogs limit
FLAT_EPS = 1e-9             # |net| below this counts as "flat"
RPC_DELAY_S = float(os.getenv("ONCHAIN_RPC_DELAY", "0.3"))  # throttle to stay under public RPC burst limits

# Smart-wallet set. Auto-seeded by scripts/discover_smart_wallets.py (recent net-accumulator
# EOAs) into config/smart_wallets.py. Heuristic seed — refine with a labeled set before scaling capital.
try:
    from config.smart_wallets import SMART_WALLETS
except ImportError:
    SMART_WALLETS: list[str] = []

ERC20_TRANSFER_ABI = [
    {"anonymous": False, "name": "Transfer", "type": "event",
     "inputs": [
         {"indexed": True, "name": "from", "type": "address"},
         {"indexed": True, "name": "to", "type": "address"},
         {"indexed": False, "name": "value", "type": "uint256"},
     ]},
    {"constant": True, "inputs": [], "name": "symbol",
     "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals",
     "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]


@dataclass
class OnchainSignal:
    symbol: str
    net_flow_tokens: float
    net_flow_usd: float | None      # None until a price is supplied
    n_wallets_active: int
    direction: str                  # "in" | "out" | "flat"


# --------------------------------------------------------------------------- #
# Pure core (unit-tested) — no network                                        #
# --------------------------------------------------------------------------- #
def aggregate_net(events: list[tuple[str, str, int]], wallets: set[str],
                  scale: float) -> tuple[float, int]:
    """Net token flow for a set of wallets from (from, to, value_raw) events.

    A tracked wallet RECEIVING adds +value; SENDING subtracts value. Returns
    (net_flow_tokens, n_wallets_active). Addresses are compared lower-cased.
    Pure function — the testable heart of the edge.
    """
    w = {a.lower() for a in wallets}
    per_wallet: dict[str, float] = {}
    for src, dst, raw in events:
        val = raw / scale
        s, d = src.lower(), dst.lower()
        if s in w:
            per_wallet[s] = per_wallet.get(s, 0.0) - val
        if d in w:
            per_wallet[d] = per_wallet.get(d, 0.0) + val
    net = sum(per_wallet.values())
    active = sum(1 for v in per_wallet.values() if abs(v) > FLAT_EPS)
    return net, active


def _direction(net: float) -> str:
    if net > FLAT_EPS:
        return "in"
    if net < -FLAT_EPS:
        return "out"
    return "flat"


# --------------------------------------------------------------------------- #
# Network layer                                                               #
# --------------------------------------------------------------------------- #
def connect(rpc_url: str | None = None) -> Web3:
    url = rpc_url or os.getenv("BSC_RPC_URL") or DEFAULT_RPC
    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 30}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        raise ConnectionError(f"BSC RPC not reachable: {url}")
    if w3.eth.chain_id != 56:
        raise ValueError(f"wrong chain: {w3.eth.chain_id} (want 56)")
    return w3


def blocks_for_window(w3: Web3, seconds: int, sample: int = 200) -> int:
    """Estimate how many blocks span `seconds`, by sampling recent block times."""
    head = w3.eth.block_number
    t_head = w3.eth.get_block(head)["timestamp"]
    t_old = w3.eth.get_block(head - sample)["timestamp"]
    avg = max((t_head - t_old) / sample, 0.1)
    return int(seconds / avg)


def _fetch_events(contract, wallets: list[str], from_block: int,
                  to_block: int) -> list[tuple[str, str, int]]:
    """Server-side filtered Transfer logs touching `wallets`, as (from, to, value) tuples."""
    checksummed = [Web3.to_checksum_address(a) for a in wallets]
    out: list[tuple[str, str, int]] = []
    lo = from_block
    while lo <= to_block:
        hi = min(lo + CHUNK_BLOCKS - 1, to_block)
        for key in ("from", "to"):
            logs = contract.events.Transfer.get_logs(
                from_block=lo, to_block=hi, argument_filters={key: checksummed})
            for lg in logs:
                a = lg["args"]
                out.append((a["from"], a["to"], a["value"]))
            if RPC_DELAY_S:
                time.sleep(RPC_DELAY_S)            # throttle: avoid public RPC burst rate limits
        lo = hi + 1
    # the from-query and to-query can both return a self->tracked or tracked->tracked
    # transfer; dedupe by (block, logIndex) is overkill here since aggregate nets them,
    # but a transfer between two tracked wallets would be double-counted. Drop exact dups.
    return list(dict.fromkeys(out))


def net_flow_for_token(w3: Web3, symbol: str, address: str, wallets: list[str],
                       from_block: int, to_block: int,
                       price_usd: float | None = None) -> OnchainSignal:
    """Compute one token's smart-money net flow, verifying the contract first."""
    contract = w3.eth.contract(address=Web3.to_checksum_address(address), abi=ERC20_TRANSFER_ABI)

    # Security: never trust an address blindly — confirm it really is this symbol.
    onchain_symbol = contract.functions.symbol().call()
    if onchain_symbol.strip().upper() != symbol.strip().upper():
        raise ValueError(f"contract {address} is '{onchain_symbol}', expected '{symbol}'")

    decimals = contract.functions.decimals().call()
    events = _fetch_events(contract, wallets, from_block, to_block)
    net, active = aggregate_net(events, set(wallets), 10 ** decimals)
    usd = net * price_usd if price_usd is not None else None
    return OnchainSignal(symbol, net, usd, active, _direction(net))


def collect(watchlist: list[str], address_map: dict[str, str] | None = None,
            wallets: list[str] | None = None, prices: dict[str, float] | None = None,
            window_hours: int | None = None) -> dict[str, OnchainSignal]:
    """Net smart-money flow per watchlist token over the trailing window.

    address_map: symbol -> contract (defaults to config.tokens.address_of).
    wallets:     tracked smart wallets (defaults to SMART_WALLETS).
    prices:      symbol -> USD price for net_flow_usd (optional).
    Fault-tolerant: per-token failures degrade to a flat signal; never raises.
    """
    wallets = wallets if wallets is not None else SMART_WALLETS
    prices = prices or {}
    hours = window_hours if window_hours is not None else settings.ONCHAIN_FLOW_WINDOW_HOURS
    out: dict[str, OnchainSignal] = {}

    if not wallets:
        log.warning("SMART_WALLETS empty — on-chain signal is flat for all tokens")
        return {s: OnchainSignal(s, 0.0, None, 0, "flat") for s in watchlist}

    try:
        w3 = connect()
        head = w3.eth.block_number
        start = head - blocks_for_window(w3, hours * 3600)
    except Exception as e:                       # RPC unreachable -> degrade, don't crash loop
        log.error("on-chain connect failed: %s", e)
        return {s: OnchainSignal(s, 0.0, None, 0, "flat") for s in watchlist}

    for sym in watchlist:
        addr = (address_map or {}).get(sym) or address_of(sym)
        if not addr:
            log.info("no address for %s — skipping on-chain read", sym)
            out[sym] = OnchainSignal(sym, 0.0, None, 0, "flat")
            continue
        try:
            out[sym] = net_flow_for_token(w3, sym, addr, wallets, start, head, prices.get(sym))
        except Exception as e:
            log.warning("on-chain read failed for %s: %s", sym, e)
            out[sym] = OnchainSignal(sym, 0.0, None, 0, "flat")
        if RPC_DELAY_S:
            time.sleep(RPC_DELAY_S)               # space token reads to respect public RPC limits
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # demo: verified CAKE address + a sample active wallet, through the production path
    CAKE = "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82"
    w3 = connect()
    head = w3.eth.block_number
    start = head - 600
    # pull all recent transfers to discover a real active wallet to demo the filter
    c = w3.eth.contract(address=Web3.to_checksum_address(CAKE), abi=ERC20_TRANSFER_ABI)
    recent = c.events.Transfer.get_logs(from_block=head - 50, to_block=head)
    sample_wallets = list({lg["args"]["to"] for lg in recent})[:5] or [CAKE]
    print(f"demo wallets ({len(sample_wallets)}): {sample_wallets}")
    sig = net_flow_for_token(w3, "CAKE", CAKE, sample_wallets, start, head, price_usd=2.5)
    print(sig)
