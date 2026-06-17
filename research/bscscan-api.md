# BscScan API Reference

> Scope: BSC trading agent — smart-wallet discovery (top holders, early buyers, PnL filtering)
> and token Transfer event ingestion.
>
> **IMPORTANT (2025 migration):** The legacy `api.bscscan.com` endpoint and all
> `docs.bscscan.com` pages now redirect to Etherscan API V2. BscScan API keys have been
> migrated to the unified Etherscan V2 system. Use the V2 base URL for all new code.

---

## Overview

BscScan is the block explorer for BNB Smart Chain (BSC, chain ID 56). It exposes an
Etherscan-family REST API covering account balances, transaction lists, token transfers,
event logs, and contract data. The API follows the same request/response shape as
Etherscan, which means most Etherscan code works on BSC by swapping the base URL and
adding `chainid=56`.

All responses share this envelope:
```json
{
  "status": "1",      // "1" = success, "0" = error
  "message": "OK",   // "OK" or error description
  "result": <data>   // string, array, or object depending on endpoint
}
```

---

## Auth & Keys

1. Register a **free** account at https://etherscan.io/register (unified with BscScan since migration).
2. Go to **My API Keys** (https://etherscan.io/myapikey) and click **+ Add**.
3. One API key works across all 60+ supported chains in V2.
4. Pass the key as query param `apikey=YOUR_KEY` on every request.

Without a key you get `"Missing/Invalid API Key, rate limit of 1/5sec applied"` — the call
still works but at a severely throttled rate. Always include the key.

---

## Base URLs

| Variant | URL | Notes |
|---------|-----|-------|
| **V2 unified (preferred)** | `https://api.etherscan.io/v2/api` | Add `chainid=56` to every request. Single key for all chains. |
| Legacy BscScan | `https://api.bscscan.com/api` | Deprecated as of Aug 15 2025. Still works [UNVERIFIED how long] but do not use for new code. |

**V2 example skeleton:**
```
https://api.etherscan.io/v2/api?chainid=56&module=account&action=tokentx&apikey=KEY&...
```

**V1 legacy skeleton (avoid):**
```
https://api.bscscan.com/api?module=account&action=tokentx&apikey=KEY&...
```

---

## Rate Limits & Tiers

Source: https://docs.etherscan.io/resources/rate-limits

| Tier | Calls/sec | Calls/day | API PRO features | BSC (chain 56) access |
|------|-----------|-----------|------------------|-----------------------|
| **Free** | 3 | 100,000 | No | **NO — paid required** |
| **Lite** | 5 | 100,000 | No | Yes |
| **Standard** | 10 | 200,000 | Yes | Yes |
| **Advanced** | 20 | 500,000 | Yes | Yes |
| **Professional** | 30 | 1,000,000 | Yes | Yes |
| **Pro Plus** | 30 | 1,500,000 | Yes | Yes |
| Dedicated/Custom | contact | contact | Yes | Yes |

> **Critical for this project:** BSC (chain ID 56) is **NOT available on the Free tier**.
> It requires at minimum the **Lite plan** (which was introduced at ~25% of the old Standard
> price). Base, OP Mainnet, and Avalanche C-Chain are similarly paid-only.

**Rate limit error response:**
```json
{"status":"0","message":"NOTOK","result":"Max rate limit reached"}
```

**Practical throttle:** Add `time.sleep(0.2)` between calls on Lite (5/sec). For burst
queries use a semaphore or token bucket.

**Free tier record cap change (effective July 1, 2026):**
Free tier users will receive max 1,000 records per request (down from 10,000). Paid tiers
retain the 10,000 record maximum.

---

## Endpoints

All examples use the V2 base URL with `chainid=56`.

---

### account.tokentx

Returns BEP-20 (ERC-20) token transfer events for an address. This is the primary
endpoint for tracing token flows into/out of a wallet.

**URL pattern:**
```
https://api.etherscan.io/v2/api
  ?chainid=56
  &module=account
  &action=tokentx
  &apikey=KEY
  [&address=WALLET]
  [&contractaddress=TOKEN_CONTRACT]
  [&startblock=0]
  [&endblock=999999999]
  [&page=1]
  [&offset=100]
  [&sort=asc]
```

**Parameters:**

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `address` | Yes* | — | Wallet address to query |
| `contractaddress` | No | — | BEP-20 token contract. If omitted → returns transfers of ALL tokens for the wallet. If set → filters to that token only. |
| `startblock` | No | 0 | Inclusive start block |
| `endblock` | No | 999999999 | Inclusive end block |
| `page` | No | 1 | Page number (1-indexed) |
| `offset` | No | 100 | Records per page. Max 10,000 (paid); max 1,000 (free, from Jul 1 2026). |
| `sort` | No | `asc` | `asc` = oldest first, `desc` = newest first |
| `apikey` | Yes | — | API key |
| `chainid` | Yes (V2) | 1 | Set to `56` for BSC |

*Either `address` or `contractaddress` must be provided.

**Filtering notes:**
- Omit `contractaddress` → all BEP-20 token transfers for the wallet (any token).
- Set `contractaddress` → only transfers of that specific token.
- Combine both to filter wallet + token.

**Response fields per record:**
```
blockNumber, timeStamp, hash, nonce, blockHash,
from, contractAddress, to, value,
tokenName, tokenSymbol, tokenDecimal,
transactionIndex, gas, gasPrice, gasUsed,
cumulativeGasUsed, input, methodId, functionName, confirmations
```

**Example — all USDT transfers for a wallet:**
```
https://api.etherscan.io/v2/api?chainid=56&module=account&action=tokentx
  &address=0xABCDEF...
  &contractaddress=0x55d398326f99059fF775485246999027B3197955
  &startblock=0&endblock=99999999&page=1&offset=100&sort=desc
  &apikey=KEY
```

**Example — find early buyers of a token (all holders who ever received it):**
```
# No address filter — returns all transfers of the token globally:
https://api.etherscan.io/v2/api?chainid=56&module=account&action=tokentx
  &contractaddress=TOKEN_CONTRACT
  &startblock=DEPLOY_BLOCK&endblock=DEPLOY_BLOCK+50000
  &page=1&offset=10000&sort=asc
  &apikey=KEY
```

**Tier:** Free (but BSC requires Lite+). Paid tiers for higher offset limits.

---

### account.txlist

Returns normal (native BNB) transactions for an address. Useful for identifying swap
transactions, contract interactions, and funding flows.

**URL pattern:**
```
https://api.etherscan.io/v2/api
  ?chainid=56
  &module=account
  &action=txlist
  &address=WALLET
  &startblock=0
  &endblock=999999999
  &page=1
  &offset=100
  &sort=asc
  &apikey=KEY
```

**Parameters:** Same as `tokentx` — `address`, `startblock`, `endblock`, `page`,
`offset`, `sort`, `apikey`, `chainid`. No `contractaddress` param.

**Response fields per record:**
```
blockNumber, timeStamp, hash, nonce, blockHash,
transactionIndex, from, to, value, gas, gasPrice, isError,
txreceipt_status, input, contractAddress, cumulativeGasUsed,
gasUsed, confirmations, methodId, functionName
```

**Note:** `isError` is `"1"` for failed txs. Filter these out when computing realized PnL.

**Tier:** Same as tokentx — requires Lite+ for BSC.

---

### account.balance

Returns the native BNB balance for a single address.

**URL pattern:**
```
https://api.etherscan.io/v2/api
  ?chainid=56
  &module=account
  &action=balance
  &address=WALLET
  &tag=latest
  &apikey=KEY
```

**Parameters:**

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `address` | Yes | — | Wallet address |
| `tag` | No | `latest` | `latest` or block number in hex for historical (last 128 blocks only) |
| `chainid` | Yes (V2) | 1 | `56` for BSC |
| `apikey` | Yes | — | API key |

**Response:**
```json
{
  "status": "1",
  "message": "OK",
  "result": "172774397764084972158218"
}
```
Result is in wei (18 decimals). Divide by `1e18` to get BNB.

**Batch variant:** `action=balancemulti` accepts `address=ADDR1,ADDR2,...ADDR20` (up to 20
addresses) and returns an array.

**Tier:** Requires Lite+ for BSC.

---

### contract.getabi

Returns the ABI JSON for a verified contract. Needed to decode function calls and events.

**URL pattern:**
```
https://api.etherscan.io/v2/api
  ?chainid=56
  &module=contract
  &action=getabi
  &address=CONTRACT_ADDRESS
  &apikey=KEY
```

**Parameters:**

| Param | Required | Description |
|-------|----------|-------------|
| `address` | Yes | The contract address (must be verified on BscScan) |
| `chainid` | Yes (V2) | `56` for BSC |
| `apikey` | Yes | API key |

**Response:**
```json
{
  "status": "1",
  "message": "OK",
  "result": "[{\"constant\":true,\"inputs\":[...],\"name\":\"...\",\"outputs\":[...],\"type\":\"function\"}]"
}
```
`result` is a JSON string (not an object) — `json.loads(result["result"])` to parse.

If the contract is not verified: `{"status":"0","message":"NOTOK","result":"Contract source code not verified"}`

**Tier:** Free (ABI endpoints are explicitly exempt from chain coverage restrictions per Etherscan policy). Works on BSC even on the free tier [VERIFY before relying on this].

---

### logs.getLogs

Returns raw event logs filtered by contract address and/or topic hashes. The most flexible
way to ingest Transfer events without relying on the `tokentx` address index.

**URL pattern:**
```
https://api.etherscan.io/v2/api
  ?chainid=56
  &module=logs
  &action=getLogs
  &address=TOKEN_CONTRACT
  &fromBlock=START
  &toBlock=END
  &topic0=0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
  &page=1
  &offset=1000
  &apikey=KEY
```

**Parameters:**

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `address` | No* | — | Contract address to filter by (the token contract for Transfer events) |
| `fromBlock` | No | — | Starting block (integer or `latest`) |
  | `toBlock` | No | — | Ending block (integer or `latest`) |
| `topic0` | No* | — | Keccak256 hash of event signature |
| `topic1` | No | — | First indexed param (padded to 32 bytes) |
| `topic2` | No | — | Second indexed param |
| `topic3` | No | — | Third indexed param |
| `topic0_1_opr` | No | — | Logical op between topic0 & topic1: `and` or `or` |
| `topic1_2_opr` | No | — | Logical op between topic1 & topic2: `and` or `or` |
| `topic2_3_opr` | No | — | Logical op between topic2 & topic3: `and` or `or` |
| `topic0_2_opr` | No | — | Logical op between topic0 & topic2: `and` or `or` |
| `topic0_3_opr` | No | — | Logical op between topic0 & topic3: `and` or `or` |
| `topic1_3_opr` | No | — | Logical op between topic1 & topic3: `and` or `or` |
| `page` | No | 1 | Page number |
| `offset` | No | 100 | Records per page (max 10,000 paid; max 1,000 free from Jul 1 2026) |
| `chainid` | Yes (V2) | 1 | `56` for BSC |
| `apikey` | Yes | — | API key |

*At least one of `address` or `topic0` should be provided; without any filter the query is too broad.

**Transfer event constants:**
```
topic0 = 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
# = keccak256("Transfer(address,address,uint256)")

# topic1 = from address (padded): 0x000...000<address_without_0x>
# topic2 = to address (padded):   0x000...000<address_without_0x>
```

**Example — all Transfer events for a token contract in a block range:**
```
https://api.etherscan.io/v2/api?chainid=56&module=logs&action=getLogs
  &address=0x55d398326f99059fF775485246999027B3197955
  &topic0=0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
  &fromBlock=30000000&toBlock=30010000
  &page=1&offset=1000
  &apikey=KEY
```

**Example — Transfer events TO a specific wallet (find incoming transfers):**
```
https://api.etherscan.io/v2/api?chainid=56&module=logs&action=getLogs
  &address=TOKEN_CONTRACT
  &topic0=0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
  &topic2=0x000000000000000000000000<WALLET_ADDRESS_WITHOUT_0x>
  &topic0_2_opr=and
  &fromBlock=30000000&toBlock=30010000
  &page=1&offset=1000
  &apikey=KEY
```

**Limitations:**
- Max records per request: 10,000 (paid); 1,000 (free, from Jul 1 2026).
- Max block range per request: not officially documented — empirically ~2,000 blocks is safe
  before hitting result limits on busy tokens. [UNVERIFIED — test per token]
- If a block range has more events than the offset cap, paginate with `page` param.
- Responses are not guaranteed to be in block order across pages; sort client-side.

**Tier:** Requires Lite+ for BSC.

---

### Token Holders (Pro — Standard plan+)

Returns the list of addresses holding a BEP-20 token, sorted by balance descending.
This is the primary endpoint for **smart-wallet discovery** (top holders).

**Availability:** Standard plan and above only. Not available on Free or Lite.

**URL pattern:**
```
https://api.etherscan.io/v2/api
  ?chainid=56
  &module=token
  &action=tokenholderlist
  &contractaddress=TOKEN_CONTRACT
  &page=1
  &offset=100
  &apikey=KEY
```

**Parameters:**

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `contractaddress` | Yes | — | BEP-20 token contract address |
| `page` | No | 1 | Page number |
| `offset` | No | 100 | Records per page (max 10,000 paid) |
| `chainid` | Yes (V2) | 1 | `56` for BSC |
| `apikey` | Yes | — | API key |

**Response fields per record:**
```
TokenHolderAddress   - wallet address
TokenHolderQuantity  - raw token balance (divide by 10^decimals)
```

**Note on "early buyers" use case:** `tokenholderlist` only shows **current** holders — it
does not show historical or past holders who have since sold. To find early buyers:
1. Use `tokentx` filtered by `contractaddress` + narrow `startblock`/`endblock` near deploy.
2. Or use `getLogs` with Transfer topic on the token contract at early blocks.
3. Then filter the `from` addresses that are the DEX pair (buys) from a specific wallet.

**Tier:** Standard plan minimum (API PRO feature).

---

## Code Examples (Python)

### Setup

```python
import requests
import time

BASE_URL = "https://api.etherscan.io/v2/api"
API_KEY = "YOUR_KEY_HERE"
BSC_CHAIN_ID = 56

def bsc_api(params: dict, delay: float = 0.21) -> dict:
    """Single call with rate-limit guard (Lite = 5/sec -> 0.21s between calls)."""
    params.update({"apikey": API_KEY, "chainid": BSC_CHAIN_ID})
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data["status"] == "0":
        raise ValueError(f"API error: {data['message']} — {data['result']}")
    time.sleep(delay)
    return data["result"]
```

### Get BEP-20 token transfers for a wallet

```python
def get_token_transfers(wallet: str, token_contract: str = None,
                        start_block: int = 0, end_block: int = 99999999,
                        page: int = 1, offset: int = 1000) -> list:
    params = {
        "module": "account",
        "action": "tokentx",
        "address": wallet,
        "startblock": start_block,
        "endblock": end_block,
        "page": page,
        "offset": offset,
        "sort": "asc",
    }
    if token_contract:
        params["contractaddress"] = token_contract
    return bsc_api(params)
```

### Get event logs (Transfer events for a token)

```python
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

def get_transfer_logs(token_contract: str, from_block: int, to_block: int,
                      to_address: str = None, page: int = 1, offset: int = 1000) -> list:
    params = {
        "module": "logs",
        "action": "getLogs",
        "address": token_contract,
        "topic0": TRANSFER_TOPIC,
        "fromBlock": from_block,
        "toBlock": to_block,
        "page": page,
        "offset": offset,
    }
    if to_address:
        # Filter to specific recipient (topic2 = indexed `to` param)
        padded = "0x" + to_address[2:].zfill(64).lower()
        params["topic2"] = padded
        params["topic0_2_opr"] = "and"
    return bsc_api(params)
```

### Get token holders (Standard plan+)

```python
def get_token_holders(token_contract: str, page: int = 1, offset: int = 1000) -> list:
    params = {
        "module": "token",
        "action": "tokenholderlist",
        "contractaddress": token_contract,
        "page": page,
        "offset": offset,
    }
    return bsc_api(params)
```

### Paginate all results

```python
def paginate(fetch_fn, **kwargs) -> list:
    """Collect all pages until fewer results than offset are returned."""
    all_results = []
    page = 1
    offset = kwargs.get("offset", 1000)
    while True:
        batch = fetch_fn(page=page, **kwargs)
        all_results.extend(batch)
        if len(batch) < offset:
            break
        page += 1
    return all_results
```

---

## Gotchas

1. **BSC is NOT on the free tier.** The free plan only supports ~90% of chains; BSC is
   excluded. You need at minimum the Lite plan. Do not assume a free key will work for BSC.

2. **docs.bscscan.com is dead.** All those URLs 301-redirect to `docs.etherscan.io/etherscan-v2`.
   The legacy `api.bscscan.com` endpoint may still work but is deprecated (Aug 15 2025).
   Use `api.etherscan.io/v2/api?chainid=56` for all new code.

3. **`tokenholderlist` is Standard plan+.** If you're on Free or Lite, the call will return
   a "403" or plan error. For early-buyer discovery on a budget, use `tokentx` filtered by
   `contractaddress` near the deploy block instead.

4. **`tokentx` without `contractaddress` returns ALL token transfers.** If you query a busy
   wallet without a token filter you may get tens of thousands of records across all tokens.
   Always pass `contractaddress` when you know the token.

5. **`offset` max is 10,000 (paid) / 1,000 (free, from Jul 1 2026).** For high-activity
   tokens you must paginate. A busy DEX pair can emit thousands of Transfer events per block.

6. **Block range for `getLogs` is not officially limited**, but in practice large ranges on
   busy contracts hit the result cap (10k records) immediately. Use narrow ranges (500–2,000
   blocks) and paginate. Always check `len(result) == offset` to detect a full page.

7. **`result` in `getabi` is a string**, not a parsed JSON object. You must call
   `json.loads(data["result"])` to get the ABI array.

8. **Topic address padding.** When filtering logs by address in topic1/topic2/topic3, the
   address must be left-padded to 32 bytes:
   `"0x" + address[2:].zfill(64).lower()`

9. **Timestamps are Unix epoch strings**, not integers. Cast with `int(tx["timeStamp"])`.

10. **`tokenDecimal` in `tokentx` is a string**, not an int. Cast:
    `amount = int(tx["value"]) / 10**int(tx["tokenDecimal"])`

11. **V1 deprecation deadline was Aug 15 2025.** `api.bscscan.com` calls may silently fail
    or stop working at any point. Migrate to V2 now.

---

## Sources

- [Etherscan V2 Migration Guide](https://docs.etherscan.io/v2-migration)
- [Etherscan API Supported Chains](https://docs.etherscan.io/supported-chains)
- [Etherscan Rate Limits](https://docs.etherscan.io/resources/rate-limits)
- [account.tokentx endpoint](https://docs.etherscan.io/api-reference/endpoint/tokentx.md)
- [logs.getLogs endpoint (address+topics)](https://docs.etherscan.io/api-reference/endpoint/getlogs-address-topics.md)
- [logs.getLogs topics-only](https://docs.etherscan.io/api-reference/endpoint/getlogs-topics.md)
- [token.tokenholderlist endpoint](https://docs.etherscan.io/api-reference/endpoint/tokenholderlist.md)
- [contract.getabi endpoint](https://docs.etherscan.io/api-reference/endpoint/getabi.md)
- [BscScan rate limit errors](https://info.bscscan.com/api-return-errors/)
- [Etherscan free tier coverage changes](https://info.etherscan.com/whats-changing-in-the-free-api-tier-coverage-and-why/)
- [BNB Chain BSCScan deprecation announcement](https://www.kucoin.com/news/flash/bnb-chain-deprecates-bscscan-api-replaced-by-etherscan-api-v2)
- [Etherscan API V2 multichain info](https://info.etherscan.com/etherscan-api-v2-multichain/)
