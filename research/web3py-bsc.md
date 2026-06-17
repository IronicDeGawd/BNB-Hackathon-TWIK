# web3.py — BNB Smart Chain Transfer Event Log Reference

Focused reference for reading BEP-20/ERC-20 Transfer event logs on BSC (chain ID 56).
No swap execution. Covers efficient log fetching, address filtering, and block-range chunking.

---

## Overview

BSC is a POA (Proof-of-Authority) chain. Its `extraData` block field exceeds the 32-byte
Ethereum spec, so **web3.py requires POA middleware** or it raises a validation error on every
block response. Get that right first — everything else is standard EVM log fetching.

Two approaches for fetching Transfer logs:

| Approach | When to use |
|---|---|
| `contract.events.Transfer.get_logs(argument_filters=...)` | You have the ABI; want decoded `args` dict |
| `w3.eth.get_logs({topics: [...]})` | Raw speed; no ABI needed; easier bulk scanning |

---

## Install + Version Notes

```bash
pip install web3
```

Current stable: **7.x** (7.16.0 as of mid-2025). Use v7 — v5 and v6 are EOL.

| Version | POA middleware | Notes |
|---|---|---|
| v5 | `from web3.middleware import geth_poa_middleware` | `w3.middleware_onion.inject(geth_poa_middleware, layer=0)` |
| v6 | `ExtraDataToPOAMiddleware` introduced | Renamed from `geth_poa_middleware`; same inject call |
| v7 | `from web3.middleware import ExtraDataToPOAMiddleware` | Class-based middleware; same inject call. **Current.** |

Also notable v7 changes:
- `get_logs` kwargs use **snake_case**: `from_block` / `to_block` (not `fromBlock`/`toBlock`)
- When passing a **dict** to `w3.eth.get_logs({...})`, keys remain **camelCase**: `fromBlock`, `toBlock`

---

## Connect to BSC

```python
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware  # v6+, was geth_poa_middleware in v5

# Third-party RPC required — public endpoints disable eth_getLogs on mainnet (see Gotchas)
BSC_RPC = "https://bsc-dataseed.bnbchain.org"  # or your QuickNode/Ankr/NodeReal URL

w3 = Web3(Web3.HTTPProvider(BSC_RPC, request_kwargs={"timeout": 30}))

# CRITICAL: inject POA middleware at layer 0 (innermost) so it processes responses first
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

assert w3.is_connected(), "Not connected"
assert w3.eth.chain_id == 56, f"Wrong chain: {w3.eth.chain_id}"
```

**Why layer=0?** The docs mark this as crucial: layer 0 guarantees the middleware is *first* to
process the response, so the oversized `extraData` is stripped before any other layer sees it.

---

## Minimal ERC-20 ABI (Transfer event only)

```python
ERC20_TRANSFER_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "from",  "type": "address"},
            {"indexed": True,  "name": "to",    "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }
]
```

> `from` and `to` are **indexed** → they become topics (efficient pre-filter).
> `value` is **not indexed** → it lives in `data` (filtered post-fetch by web3.py).

---

## Reading Transfer Logs via `contract.events.Transfer.get_logs()`

```python
TOKEN_ADDRESS = Web3.to_checksum_address("0x55d398326f99059ff775485246999027b3197955")  # BSC-USD

contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_TRANSFER_ABI)

# Fetch all transfers in block range
logs = contract.events.Transfer.get_logs(
    from_block=45_000_000,
    to_block=45_001_000,
)

for log in logs:
    print(log["args"]["from"], "->", log["args"]["to"], log["args"]["value"])
```

### Filter by sender address (`from`)

```python
WALLET = Web3.to_checksum_address("0xYourSmartWalletAddress")

logs = contract.events.Transfer.get_logs(
    from_block=45_000_000,
    to_block=45_001_000,
    argument_filters={"from": WALLET},   # "from" not "from_" — uses ABI name as dict key string
)
```

### Filter by recipient address (`to`)

```python
logs = contract.events.Transfer.get_logs(
    from_block=45_000_000,
    to_block=45_001_000,
    argument_filters={"to": WALLET},
)
```

### Filter by multiple wallets at once

```python
WALLETS = [
    Web3.to_checksum_address("0xWallet1"),
    Web3.to_checksum_address("0xWallet2"),
]

# Transfers OUT from any of the wallets
logs = contract.events.Transfer.get_logs(
    from_block=45_000_000,
    to_block=45_001_000,
    argument_filters={"from": WALLETS},  # list = match any
)
```

**Indexed vs non-indexed filtering:**
- `from` and `to` are indexed → web3.py converts them to `topics` → the RPC node filters them
  server-side before returning data. Efficient.
- `value` is not indexed → web3.py fetches all logs then filters locally. Slower for large ranges.

**Key name rule:** Use the argument name exactly as it appears in the ABI (`"from"`, `"to"`,
`"value"`). `"from"` as a *string dict key* is fine in Python — it's only a reserved word as a
bare identifier. Do **not** use `"from_"`.

---

## Raw `eth_getLogs` with Topics

Faster for bulk scanning — no ABI, no contract object, decoding is manual.

```python
# Transfer event signature topic
TRANSFER_TOPIC = w3.keccak(text="Transfer(address,address,uint256)").hex()
# = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

TOKEN_ADDRESS = Web3.to_checksum_address("0x55d398326f99059ff775485246999027b3197955")
WALLET        = Web3.to_checksum_address("0xYourSmartWalletAddress")

def address_to_topic(addr: str) -> str:
    """Pad a checksum address to 32-byte topic format."""
    return "0x" + "0" * 24 + addr[2:].lower()  # strip 0x, pad to 64 hex chars

# Raw getLogs: dict keys are camelCase
raw_filter = {
    "fromBlock": 45_000_000,
    "toBlock":   45_001_000,
    "address":   TOKEN_ADDRESS,
    # topics[0] = event signature
    # topics[1] = indexed `from` address (None = any)
    # topics[2] = indexed `to` address   (None = any)
    "topics": [
        TRANSFER_TOPIC,
        address_to_topic(WALLET),  # filter by sender
        None,                       # any recipient
    ],
}

raw_logs = w3.eth.get_logs(raw_filter)

for log in raw_logs:
    # Decode addresses from topics (topics[1]=from, topics[2]=to)
    sender    = Web3.to_checksum_address("0x" + log["topics"][1].hex()[-40:])
    recipient = Web3.to_checksum_address("0x" + log["topics"][2].hex()[-40:])
    # Decode value from data (non-indexed, ABI-encoded uint256)
    value_raw = int(log["data"].hex(), 16)
    print(f"{sender} -> {recipient}: {value_raw}")
```

**To filter by recipient instead:** swap `None` and the address topic:
```python
"topics": [TRANSFER_TOPIC, None, address_to_topic(WALLET)]
```

**To match either sender OR recipient** (OR logic): pass a list in a topic slot:
```python
"topics": [TRANSFER_TOPIC, [address_to_topic(W1), address_to_topic(W2)]]
```

---

## Block-Range Chunking

Public BSC RPCs limit `eth_getLogs` to roughly **2,000–5,000 blocks per request** (some error at
1,000). Always chunk. At ~3 seconds/block, 2,000 blocks ≈ last ~100 minutes of history.

```python
from typing import Generator

def chunked_get_logs(
    w3: Web3,
    filter_params: dict,
    chunk_size: int = 2_000,
) -> Generator[list, None, None]:
    """
    Yield log batches in chunk_size block increments.
    filter_params must have fromBlock and toBlock as ints.
    """
    start = filter_params["fromBlock"]
    end   = filter_params["toBlock"]

    while start <= end:
        batch_end = min(start + chunk_size - 1, end)
        params = {**filter_params, "fromBlock": start, "toBlock": batch_end}
        try:
            yield w3.eth.get_logs(params)
        except Exception as e:
            if "limit exceeded" in str(e).lower() or "-32005" in str(e):
                # Halve chunk size and retry
                chunk_size = chunk_size // 2
                if chunk_size < 100:
                    raise RuntimeError("Chunk too small, RPC is very restrictive") from e
                continue  # retry same start with smaller chunk
            raise
        start = batch_end + 1


# Usage
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TOKEN_ADDRESS  = Web3.to_checksum_address("0x55d398326f99059ff775485246999027b3197955")

base_filter = {
    "address": TOKEN_ADDRESS,
    "topics":  [TRANSFER_TOPIC],
    "fromBlock": 44_000_000,
    "toBlock":   45_000_000,
}

all_logs = []
for batch in chunked_get_logs(w3, base_filter, chunk_size=2_000):
    all_logs.extend(batch)

print(f"Total logs: {len(all_logs)}")
```

---

## Block ↔ Timestamp Conversion

```python
def block_to_timestamp(w3: Web3, block_number: int) -> int:
    """Return Unix timestamp (seconds) for a block number."""
    block = w3.eth.get_block(block_number)
    return block["timestamp"]

# Convert timestamp to block (approximate, binary search approach)
def timestamp_to_approx_block(w3: Web3, target_ts: int) -> int:
    """Binary search for the block closest to target_ts."""
    lo = 1
    hi = w3.eth.block_number
    while lo < hi:
        mid = (lo + hi) // 2
        ts = block_to_timestamp(w3, mid)
        if ts < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo

# Example: logs since 24 hours ago
import time
since_ts    = int(time.time()) - 86_400
start_block = timestamp_to_approx_block(w3, since_ts)
end_block   = w3.eth.block_number
```

> BSC block time is ~3 seconds. Rough estimate: `blocks_back = seconds_back // 3`.

---

## Decimals Decoding

```python
# Minimal ABI to read decimals
ERC20_META_ABI = [
    {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol",   "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"},
]

token = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_META_ABI)
decimals = token.functions.decimals().call()
symbol   = token.functions.symbol().call()

# Decode raw value from a log
raw_value = int(log["data"].hex(), 16)        # from raw eth_getLogs
human_amount = raw_value / (10 ** decimals)   # e.g. 1_000_000 / 1e6 = 1.0 USDT

# If using contract.events.Transfer.get_logs(), args["value"] is already an int:
human_amount = log["args"]["value"] / (10 ** decimals)
```

---

## Buy vs Sell Classification

For a trading agent tracking a smart wallet:

```python
def classify_transfers(logs, wallet: str, token_address: str, decimals: int):
    """
    Returns (total_bought, total_sold) in human units.
    Buys  = wallet received tokens  (wallet is `to`)
    Sells = wallet sent tokens      (wallet is `from`)
    """
    wallet = wallet.lower()
    bought = 0.0
    sold   = 0.0

    for log in logs:
        # Works for both raw logs (topics) and decoded logs (args)
        if hasattr(log.get("args", {}), "__getitem__") or "args" in log:
            sender    = log["args"]["from"].lower()
            recipient = log["args"]["to"].lower()
            amount    = log["args"]["value"] / (10 ** decimals)
        else:
            # raw log
            sender    = ("0x" + log["topics"][1].hex()[-40:]).lower()
            recipient = ("0x" + log["topics"][2].hex()[-40:]).lower()
            amount    = int(log["data"].hex(), 16) / (10 ** decimals)

        if recipient == wallet:
            bought += amount
        elif sender == wallet:
            sold += amount

    return bought, sold
```

---

## Public BSC RPC URLs and Limits

| URL | Notes |
|---|---|
| `https://bsc-dataseed.bnbchain.org` | Official; `eth_getLogs` **disabled** on mainnet public nodes |
| `https://bsc-dataseed.nariox.org` | Community; same restriction |
| `https://bsc-dataseed.defibit.io` | Community; same restriction |
| `https://bsc-dataseed-public.bnbchain.org` | Official alternate; same restriction |
| `https://bsc.nodereal.io` | NodeReal free tier; `eth_getLogs` enabled, 10k block limit |

**Official BSC documentation explicitly states `eth_getLogs` is disabled on public mainnet
endpoints.** For a trading agent that needs log history, use a paid or free-tier third-party node:

- [Ankr](https://www.ankr.com/rpc/bsc/) — free tier, 1500 req/day
- [NodeReal](https://nodereal.io/) — free tier, 10k block/request limit
- [QuickNode](https://www.quicknode.com/) — 10k block/request limit on `eth_getLogs`
- [GetBlock](https://getblock.io/) — free tier available
- Testnet (chain ID 97): `https://bsc-testnet-dataseed.bnbchain.org` — `eth_getLogs` works

Rate limit on official endpoints: **10,000 requests / 5 minutes**.

---

## Gotchas

### 1. POA middleware is mandatory
Without it, every `w3.eth.get_block()` call raises:
```
ExtraDataLengthError: The field extraData is 278 bytes, but should be 32.
It is quite likely that you are connected to a POA chain.
```
Fix: inject at layer=0 (see Connect section above).

### 2. `eth_getLogs` disabled on official public mainnet nodes
Use a third-party RPC. The BNB Chain docs confirm this. If you see `Method not found` or a
`-32601` error, that's why.

### 3. Checksum addresses
web3.py raises `InvalidAddress` if you pass a lowercase address to `contract()` or `address=`
in a filter. Always use `Web3.to_checksum_address(addr)`.

### 4. Block range errors
BSC public/free-tier nodes return error `-32005` (`limit exceeded`) or just time out when the
block range is too wide. Start with `chunk_size=2_000` and halve on error.

### 5. `argument_filters` key is `"from"`, not `"from_"`
```python
# CORRECT — "from" as a string dict key is valid Python
argument_filters={"from": WALLET}

# WRONG — underscore suffix is not the ABI name
argument_filters={"from_": WALLET}
```
Use the exact ABI parameter name as a string. The restriction only applies when using `from`
as a bare Python *identifier*, not as a dict key.

### 6. dict vs kwargs snake_case split
```python
# dict to w3.eth.get_logs → camelCase keys
w3.eth.get_logs({"fromBlock": 100, "toBlock": 200})

# contract.events API kwargs → snake_case
contract.events.Transfer.get_logs(from_block=100, to_block=200)
```

### 7. Transfer topic hash
```python
# Verify it yourself:
assert w3.keccak(text="Transfer(address,address,uint256)").hex() == \
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
```

### 8. Address padding in raw topics
Topics are 32 bytes. An address is 20 bytes. When filtering by address in raw topics, pad with
24 leading zero hex chars:
```python
padded = "0x" + "0" * 24 + address[2:].lower()
# 0x000000000000000000000000abcdef1234...
```

### 9. v5 → v6/v7 migration
If upgrading old code:
```python
# v5 (remove this):
from web3.middleware import geth_poa_middleware
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# v6/v7 (use this):
from web3.middleware import ExtraDataToPOAMiddleware
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
```

---

## Full Working Example (buy/sell scanner)

```python
"""
Scan BEP-20 Transfer events for a list of wallets over the last N blocks.
Classifies each transfer as a buy (wallet received) or sell (wallet sent).
"""
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

BSC_RPC    = "https://YOUR_THIRD_PARTY_BSC_RPC"
TOKEN_ADDR = "0x55d398326f99059ff775485246999027b3197955"  # BSC-USD (USDT on BSC)
WALLETS    = ["0xSmartWallet1", "0xSmartWallet2"]
BLOCKS_BACK = 2_000
CHUNK_SIZE  = 500   # conservative for free-tier nodes

w3 = Web3(Web3.HTTPProvider(BSC_RPC, request_kwargs={"timeout": 30}))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

token_address = Web3.to_checksum_address(TOKEN_ADDR)
wallets       = [Web3.to_checksum_address(w) for w in WALLETS]

ERC20_ABI = [
    {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}],  "stateMutability": "view", "type": "function"},
    {"anonymous": False, "inputs": [
        {"indexed": True,  "name": "from",  "type": "address"},
        {"indexed": True,  "name": "to",    "type": "address"},
        {"indexed": False, "name": "value", "type": "uint256"},
    ], "name": "Transfer", "type": "event"},
]

contract  = w3.eth.contract(address=token_address, abi=ERC20_ABI)
decimals  = contract.functions.decimals().call()

end_block   = w3.eth.block_number
start_block = end_block - BLOCKS_BACK

TRANSFER_TOPIC = w3.keccak(text="Transfer(address,address,uint256)").hex()


def address_to_topic(addr: str) -> str:
    return "0x" + "0" * 24 + addr[2:].lower()


totals = {w.lower(): {"bought": 0.0, "sold": 0.0} for w in wallets}

for wallet in wallets:
    # Fetch logs where wallet is sender
    for start in range(start_block, end_block + 1, CHUNK_SIZE):
        chunk_end = min(start + CHUNK_SIZE - 1, end_block)
        logs = w3.eth.get_logs({
            "fromBlock": start,
            "toBlock":   chunk_end,
            "address":   token_address,
            "topics":    [TRANSFER_TOPIC, address_to_topic(wallet), None],
        })
        for log in logs:
            raw = int(log["data"].hex(), 16)
            totals[wallet.lower()]["sold"] += raw / (10 ** decimals)

    # Fetch logs where wallet is recipient
    for start in range(start_block, end_block + 1, CHUNK_SIZE):
        chunk_end = min(start + CHUNK_SIZE - 1, end_block)
        logs = w3.eth.get_logs({
            "fromBlock": start,
            "toBlock":   chunk_end,
            "address":   token_address,
            "topics":    [TRANSFER_TOPIC, None, address_to_topic(wallet)],
        })
        for log in logs:
            raw = int(log["data"].hex(), 16)
            totals[wallet.lower()]["bought"] += raw / (10 ** decimals)

for wallet, data in totals.items():
    net = data["bought"] - data["sold"]
    print(f"{wallet}: bought={data['bought']:.4f}, sold={data['sold']:.4f}, net={net:.4f}")
```

---

## Source URLs

- [web3.py Events and Logs (stable)](https://web3py.readthedocs.io/en/stable/filters.html)
- [web3.py Middleware (stable)](https://web3py.readthedocs.io/en/stable/middleware.html)
- [web3.py Contracts (stable)](https://web3py.readthedocs.io/en/stable/web3.contract.html)
- [web3.py Migration Guide (v5→v7)](https://web3py.readthedocs.io/en/stable/migration.html)
- [BSC JSON-RPC Endpoints (official)](https://docs.bnbchain.org/bnb-smart-chain/developers/json_rpc/json-rpc-endpoint/)
- [eth_getLogs BSC block range issue](https://github.com/bnb-chain/bsc/issues/113)
- [How to encode topics for eth_getLogs (Chainstack)](https://docs.chainstack.com/recipes/how-to-properly-encode-topics-for-eth_getlogs-1)
- [ERC-20 Transfer logs gist (web3.py)](https://gist.github.com/soos3d/9ff9dc2054b7069a0c868833dcb483cd)
- [Alchemy: Deep dive into eth_getLogs](https://www.alchemy.com/docs/deep-dive-into-eth_getlogs)
