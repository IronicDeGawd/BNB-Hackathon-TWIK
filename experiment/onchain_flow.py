"""EXPERIMENT 1 — prove the edge: read REAL BEP-20 Transfer logs on BSC and
compute per-wallet net flow, keyless, over a trailing block window.

This is a throwaway proof-of-concept, NOT the production module. It exists only to
confirm we can extract smart-money flow from live chain data.

Findings baked in (from research/web3py-bsc.md):
  - public bsc-dataseed disables/limits eth_getLogs -> use bsc-rpc.publicnode.com
  - BSC is POA -> inject ExtraDataToPOAMiddleware at layer 0
  - chunk getLogs to <=2000 blocks
"""

from __future__ import annotations

from dataclasses import dataclass

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

RPC_URL = "https://bsc-rpc.publicnode.com"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
CHUNK = 1000  # blocks per getLogs call (under the ~2000 public limit)

# CAKE — PancakeSwap token. symbol() is verified at runtime so we never trust a
# hardcoded address blindly (mirrors the tokens.py "verify canonical contract" rule).
CAKE = "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82"

ERC20_MIN_ABI = [
    {"constant": True, "inputs": [], "name": "symbol",
     "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals",
     "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]


@dataclass
class FlowResult:
    symbol: str
    decimals: int
    from_block: int
    to_block: int
    n_transfers: int
    net_by_wallet: dict[str, float]   # wallet -> (received - sent), token units

    def top_accumulators(self, n=5):
        return sorted(self.net_by_wallet.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def top_distributors(self, n=5):
        return sorted(self.net_by_wallet.items(), key=lambda kv: kv[1])[:n]


def connect() -> Web3:
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 20}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    assert w3.is_connected(), "RPC connect failed"
    return w3


def _topic_to_addr(topic) -> str:
    h = topic.hex() if hasattr(topic, "hex") else str(topic)
    return Web3.to_checksum_address("0x" + h[-40:])


def net_flow(w3: Web3, token_addr: str, window_blocks: int = 600) -> FlowResult:
    """Fetch Transfer logs over the trailing `window_blocks` and net them per wallet."""
    token = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=ERC20_MIN_ABI)
    symbol = token.functions.symbol().call()
    decimals = token.functions.decimals().call()
    scale = 10 ** decimals

    head = w3.eth.block_number
    start = head - window_blocks
    logs = []
    lo = start
    while lo <= head:
        hi = min(lo + CHUNK - 1, head)
        logs += w3.eth.get_logs({
            "fromBlock": lo, "toBlock": hi,
            "address": Web3.to_checksum_address(token_addr),
            "topics": [TRANSFER_TOPIC],
        })
        lo = hi + 1

    net: dict[str, float] = {}
    for lg in logs:
        topics = lg["topics"]
        if len(topics) < 3:
            continue  # non-standard Transfer, skip
        src = _topic_to_addr(topics[1])
        dst = _topic_to_addr(topics[2])
        raw = int(lg["data"].hex(), 16) if hasattr(lg["data"], "hex") else int(lg["data"], 16)
        val = raw / scale
        net[src] = net.get(src, 0.0) - val
        net[dst] = net.get(dst, 0.0) + val

    return FlowResult(symbol, decimals, start, head, len(logs), net)


if __name__ == "__main__":
    w3 = connect()
    print(f"connected | chain_id={w3.eth.chain_id} | head={w3.eth.block_number}")
    res = net_flow(w3, CAKE, window_blocks=600)
    print(f"\ntoken={res.symbol} decimals={res.decimals} "
          f"blocks={res.from_block}..{res.to_block} transfers={res.n_transfers} "
          f"unique_wallets={len(res.net_by_wallet)}")
    print("\nTop 5 ACCUMULATORS (net received, token units):")
    for addr, v in res.top_accumulators():
        print(f"  +{v:>16,.2f}  {addr}")
    print("\nTop 5 DISTRIBUTORS (net sent):")
    for addr, v in res.top_distributors():
        print(f"  {v:>17,.2f}  {addr}")
