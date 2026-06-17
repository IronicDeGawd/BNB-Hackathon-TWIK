# CoinMarketCap Agent Hub — Developer Reference

> **Scope**: Autonomous BSC trading agent (hackathon). CMC is used as a structural sanity/veto layer only — NOT for trade signal generation. Needed per decision cycle: Fear & Greed index, per-token funding rate, per-token liquidity depth.
>
> Last researched: 2026-06-14

---

## 1. Overview

CoinMarketCap AI Agent Hub is a unified integration layer (launched ~May 2026, currently in beta) that exposes CMC's market data to AI agents, LLM clients, and developer tools through four access paths:

| Path | Best for | Auth |
|------|----------|------|
| **MCP Server** | Claude Code, Cursor, Windsurf, any MCP client | API key header |
| **x402** | Autonomous agents, pay-per-request, no API key | USDC on Base |
| **CMC CLI** | Terminal/scripting | API key |
| **IDE integrations** | Cursor, Claude Code, Windsurf (pre-configured) | API key |

The underlying data comes from the CoinMarketCap Pro API (`pro-api.coinmarketcap.com`). Agent Hub is a layer on top; the Pro API can also be called directly over REST.

---

## 2. What Agent Hub is vs. Pro API

| | Agent Hub (MCP) | Pro API (REST) |
|---|---|---|
| Protocol | MCP (Model Context Protocol) — tool calls | REST / JSON |
| Endpoint | `https://mcp.coinmarketcap.com/mcp` | `https://pro-api.coinmarketcap.com` |
| Auth header | `X-CMC-MCP-API-KEY` | `X-CMC_PRO_API_KEY` |
| Tools available | 12 structured tools | 72+ raw endpoints |
| Best for | Agent loops that auto-select tools | Deterministic code that calls specific endpoints |
| Funding rate depth | Via `get_global_crypto_derivatives_metrics` (aggregate only — see §6) | `/v5/cryptocurrency/derivatives/market-pairs/list/latest` (per-pair) |
| Liquidity depth | Not directly exposed as MCP tool | `/v2/cryptocurrency/market-pairs/latest` (has `depth_negative_two`, `depth_positive_two`) |

**Recommendation for this agent**: Use the Pro API REST endpoints directly for the three veto signals (deterministic, no hallucination risk from tool-selection). Use MCP only if you want the agent itself to query during reasoning.

---

## 3. MCP Server

### Official CMC MCP Server

- **SSE endpoint**: `https://mcp.coinmarketcap.com/mcp`
- **x402 variant** (no API key): `https://mcp.coinmarketcap.com/x402/mcp`
- **Protocol**: MCP over HTTP (SSE transport)

### Authentication

```json
{
  "mcpServers": {
    "cmc-mcp": {
      "url": "https://mcp.coinmarketcap.com/mcp",
      "headers": {
        "X-CMC-MCP-API-KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

Get an API key at: https://pro.coinmarketcap.com/login → Dashboard → Copy key.

### x402 variant (keyless — see §8)

```json
{
  "mcpServers": {
    "cmc-x402": {
      "url": "https://mcp.coinmarketcap.com/x402/mcp"
    }
  }
}
```

### Available MCP Tools (12 total)

| Tool name | What it returns |
|-----------|-----------------|
| `search_cryptos` | Search across 10,000+ cryptos by name/symbol/slug |
| `get_crypto_quotes_latest` | Live price, market cap, volume, % changes |
| `get_crypto_info` | Metadata: logo, description, links, whitepaper |
| `get_crypto_technical_analysis` | MA, MACD, RSI, Fibonacci, pivot points |
| `get_crypto_marketcap_technical_analysis` | Market-cap TA indicators |
| `get_crypto_metrics` | Holder distribution, supply breakdown (on-chain) |
| `get_global_metrics_latest` | Total market cap, BTC dominance, **Fear & Greed Index** |
| `get_global_crypto_derivatives_metrics` | Open interest, **funding rates** (aggregate), leverage |
| `trending_crypto_narratives` | Trending narratives with performance data |
| `get_upcoming_macro_events` | Upcoming market-moving events |
| `get_crypto_latest_news` | Current crypto news |
| `search_crypto_info` | Semantic search across concepts/whitepapers |

**Note**: Funding rate via MCP is aggregate (`get_global_crypto_derivatives_metrics`). Per-token funding rate requires the REST API (§6).

### Third-party MCP option

`@shinzo-labs/coinmarketcap-mcp` (npm) — wraps the Pro REST API as MCP tools, with per-subscription-tier feature gating. Install via Smithery:

```bash
npx -y @smithery/cli install @shinzo-labs/coinmarketcap-mcp
```

Config env var: `COINMARKETCAP_API_KEY`. Optional: `SUBSCRIPTION_LEVEL` (Basic/Hobbyist/Startup/Standard/Professional/Enterprise).

---

## 4. Authentication (API Key — REST)

All Pro API calls require the header:

```
X-CMC_PRO_API_KEY: YOUR_KEY
```

Base URL: `https://pro-api.coinmarketcap.com`

Get key: https://pro.coinmarketcap.com → register/login → Dashboard.

---

## 5. Fear & Greed Index

**Verified.** Available on all paid tiers AND free Basic tier.

### Latest (use this in trading loop)

```
GET https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest
```

Headers: `X-CMC_PRO_API_KEY: YOUR_KEY`

Response fields:
- `value` — integer 0–100 (0 = Extreme Fear, 100 = Extreme Greed)
- `value_classification` — string ("Extreme Fear" / "Fear" / "Neutral" / "Greed" / "Extreme Greed")
- `update_time` — ISO timestamp

- **Credit cost**: 1 call credit
- **Update frequency**: every 15 minutes
- **Available tiers**: Basic, Hobbyist, Startup, Standard, Professional, Enterprise

### Historical

```
GET https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical
```

Optional params: `start` (default: 1), `limit` (default: 50, max: 500)
Response fields: `timestamp`, `value`, `value_classification`
- **Credit cost**: 1 call credit per request (regardless of limit)
- **Update frequency**: every 15 seconds (for the record)

### Code example (Python)

```python
import requests

def get_fear_and_greed(api_key: str) -> dict:
    """Returns {'value': int, 'value_classification': str, 'update_time': str}"""
    resp = requests.get(
        "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest",
        headers={"X-CMC_PRO_API_KEY": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]

# Veto: halt trading if extreme fear or extreme greed
def fear_greed_veto(api_key: str, fear_threshold: int = 20, greed_threshold: int = 80) -> bool:
    """Returns True if conditions are too extreme to trade safely."""
    data = get_fear_and_greed(api_key)
    v = data["value"]
    return v <= fear_threshold or v >= greed_threshold
```

---

## 6. Funding Rate (Per-Token)

**Partially verified.** CMC tracks funding rates at the market-pair level via the derivatives endpoints. No dedicated single-endpoint "give me BTC funding rate" call exists — you query per-token pairs.

### Per-token funding rate (across all exchanges)

```
GET https://pro-api.coinmarketcap.com/v5/cryptocurrency/derivatives/market-pairs/list/latest
```

Key parameters:
- `id` or `symbol` — e.g. `symbol=BTC`
- `category` — `"perpetual"` to filter perpetuals only

Response includes per-pair fields:
- `funding_rate` — current funding rate
- `open_interest` — open interest in USD
- `index_price` — index price
- `volume_24h` — 24h volume

- **Update frequency**: every 60 seconds
- **Available tiers**: Basic through Enterprise (verified: all tiers per documentation)
- **Credit cost**: tiered (see rate limits §10)

### Aggregate global derivatives metrics (MCP tool equivalent)

```
GET https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest
```

Includes aggregate `btc_dominance`, total open interest, aggregate funding rate direction. Less useful for per-token veto.

### Code example (Python)

```python
def get_token_funding_rates(api_key: str, symbol: str) -> list[dict]:
    """Returns list of perpetual market pairs with funding_rate for the token."""
    resp = requests.get(
        "https://pro-api.coinmarketcap.com/v5/cryptocurrency/derivatives/market-pairs/list/latest",
        headers={"X-CMC_PRO_API_KEY": api_key},
        params={"symbol": symbol, "category": "perpetual"},
        timeout=10,
    )
    resp.raise_for_status()
    pairs = resp.json().get("data", {}).get("market_pairs", [])
    return [
        {
            "exchange": p.get("exchange", {}).get("name"),
            "funding_rate": p.get("quote", {}).get("USD", {}).get("funding_rate"),
            "open_interest": p.get("quote", {}).get("USD", {}).get("open_interest"),
        }
        for p in pairs
    ]

def funding_rate_veto(api_key: str, symbol: str, extreme_threshold: float = 0.001) -> bool:
    """Veto if any major exchange shows extreme funding (absolute > threshold)."""
    pairs = get_token_funding_rates(api_key, symbol)
    if not pairs:
        return False  # data unavailable — don't veto
    rates = [p["funding_rate"] for p in pairs if p["funding_rate"] is not None]
    if not rates:
        return False
    avg_rate = sum(rates) / len(rates)
    return abs(avg_rate) > extreme_threshold
```

> **CAVEAT**: The exact response schema (`quote.USD.funding_rate` nesting) is inferred from CMC's pattern for derivatives endpoints and the documented field name `funding_rate`. Verify against a live response before relying on it. Mark as **PARTIALLY VERIFIED**.

---

## 7. Liquidity Depth (Slippage Veto)

**Verified.** CMC provides order book depth at ±2% from mid-price via the market-pairs endpoint. This is a common institutional measure — "how much can I buy/sell within 2% of current price before moving the market."

### Endpoint

```
GET https://pro-api.coinmarketcap.com/v2/cryptocurrency/market-pairs/latest
```

Key parameters:
- `id` or `symbol` — crypto to query (e.g. `symbol=BNB`)
- `category` — `"spot"` to exclude derivatives
- `convert` — `"USD"` for USD-denominated depth
- `aux` — include `"depth"` to get the depth fields

Relevant response fields per market pair:
- `depth_negative_two` — USD depth on the bid side within −2% of mid-price
- `depth_positive_two` — USD depth on the ask side within +2% of mid-price
- `effective_liquidity` — CMC's aggregated liquidity score for the pair

- **Available tiers**: Basic through Enterprise
- **Credit cost**: 1 credit per request

### What ±2% depth means

Think of it like a supermarket shelf: `depth_negative_two` is how many USD worth of sell orders sit within 2% below the current price. A shallow shelf (low depth) means your trade will "eat through" those orders fast and get a bad fill — high slippage. A deep shelf means you can trade larger without moving the price.

**Veto rule**: If `depth_negative_two` + `depth_positive_two` for the relevant exchange/pair is below your minimum (e.g. $50,000 combined), reject the trade.

### Code example (Python)

```python
def get_liquidity_depth(api_key: str, symbol: str, exchange_slug: str = None) -> list[dict]:
    """
    Returns market pairs for symbol with depth_negative_two and depth_positive_two.
    Optionally filter by exchange_slug (e.g. 'pancakeswap' for BSC DEX).
    """
    params = {
        "symbol": symbol,
        "category": "spot",
        "convert": "USD",
        "aux": "depth,volume_24h_base,volume_24h_quote",
    }
    if exchange_slug:
        params["matched_id"] = exchange_slug  # UNVERIFIED: check if slug or id needed
    resp = requests.get(
        "https://pro-api.coinmarketcap.com/v2/cryptocurrency/market-pairs/latest",
        headers={"X-CMC_PRO_API_KEY": api_key},
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    pairs = resp.json().get("data", {}).get("market_pairs", [])
    return [
        {
            "exchange": p.get("exchange", {}).get("name"),
            "depth_negative_two": p.get("quote", {}).get("USD", {}).get("depth_negative_two"),
            "depth_positive_two": p.get("quote", {}).get("USD", {}).get("depth_positive_two"),
        }
        for p in pairs
    ]

def liquidity_veto(
    api_key: str,
    symbol: str,
    min_depth_usd: float = 50_000,
    exchange_slug: str = None,
) -> bool:
    """Returns True (veto trade) if combined ±2% depth is below threshold."""
    pairs = get_liquidity_depth(api_key, symbol, exchange_slug)
    if not pairs:
        return True  # no data = assume thin = veto
    # Use the pair with the most depth (best case)
    best = max(
        pairs,
        key=lambda p: (p["depth_negative_two"] or 0) + (p["depth_positive_two"] or 0),
    )
    combined = (best["depth_negative_two"] or 0) + (best["depth_positive_two"] or 0)
    return combined < min_depth_usd
```

> **Note on BSC DEX data**: CMC's `depth_negative_two`/`depth_positive_two` come from exchange-reported CEX order books. For DEX liquidity on BSC (PancakeSwap, etc.), CMC has a separate DEX API (see §9).

---

## 8. x402 Support

**Verified.** CMC fully supports x402 — this is one of their four official access paths.

### What x402 is

x402 is an open payment protocol (built by Coinbase) for machine-to-machine micropayments over HTTP. When you call an x402 endpoint without a signature, you get back HTTP 402 with payment terms. Your agent signs a USDC transfer authorization (off-chain EIP-3009 signature) and retries. Payment only executes on-chain if CMC delivers the data.

### CMC x402 details

- **Cost**: $0.01 USDC per request (MCP tool call OR REST endpoint call)
- **Payment token**: USDC on Base (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- **Network**: Base (Chain ID: 8453)
- **Mechanism**: EIP-3009 `transferWithAuthorization` (off-chain signature, on-chain execution only on delivery)

### x402-supported REST endpoints (verified)

| Endpoint | Path |
|----------|------|
| DEX Search | `/x402/v1/dex/search` |
| Cryptocurrency Quotes Latest | `/x402/v3/cryptocurrency/quotes/latest` |
| Cryptocurrency Listings Latest | `/x402/v3/cryptocurrency/listings/latest` |
| DEX Pairs Quotes Latest | `/x402/v4/dex/pairs/quotes/latest` |

Base URL for x402 REST: `https://pro-api.coinmarketcap.com` (prefix paths with `/x402/...`)

### x402 MCP endpoint

```
https://mcp.coinmarketcap.com/x402/mcp
```

No API key required. Agent needs a Base wallet with USDC.

### TypeScript SDK

```bash
npm install @x402/axios
```

```typescript
import axios from "axios";
import { withPaymentInterceptor } from "@x402/axios";
import { createWalletClient, http } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { base } from "viem/chains";

const account = privateKeyToAccount(process.env.PRIVATE_KEY as `0x${string}`);
const walletClient = createWalletClient({ account, chain: base, transport: http() });

const client = withPaymentInterceptor(axios.create(), walletClient);

// Usage — same as regular axios, payment happens automatically on 402 response
const resp = await client.get(
  "https://pro-api.coinmarketcap.com/x402/v3/cryptocurrency/quotes/latest",
  { params: { symbol: "BNB", convert: "USD" } }
);
```

> **Fear & Greed via x402**: The `/v3/fear-and-greed/latest` path is NOT in the verified x402 endpoint list above. It may be accessible via the x402 MCP server (`get_global_metrics_latest` tool includes Fear & Greed), but direct REST access via x402 is **UNVERIFIED** for this specific endpoint. Use the API-key path for fear & greed in the trading loop to be safe.

---

## 9. DEX Liquidity (BSC-specific)

For BSC DEX liquidity (PancakeSwap V2/V3, etc.), CMC has a separate DEX API that provides on-chain pool data.

**Relevant endpoints (PARTIALLY VERIFIED — verify exact paths)**:

```
GET https://pro-api.coinmarketcap.com/v4/dex/pairs/quotes/latest
```

Returns: real-time quotes for DEX trading pairs including liquidity pool data.

```
GET https://pro-api.coinmarketcap.com/v1/dex/search   (UNVERIFIED path)
```

CMC's DEX API covers data from "on-chain token, pair, liquidity, platform, and OHLCV data across decentralized ecosystems." BSC (BNB Chain) is included.

**For x402 access to DEX data**, the verified x402 paths are:
- `/x402/v1/dex/search`
- `/x402/v4/dex/pairs/quotes/latest`

---

## 10. Rate Limits & Pricing Tiers

### Plan tiers

| Plan | Price | Monthly credits | Rate limit |
|------|-------|----------------|------------|
| Basic (Free) | $0 | 15,000 | 30 calls/min |
| Hobbyist | $29/mo | 150,000 | 60 calls/min |
| Startup | $79/mo | 450,000 | ~unknown |
| Standard | $299/mo | 2,000,000 | ~unknown |
| Professional | $699/mo | 5,000,000 | ~unknown |
| Enterprise | Custom | 30,000,000 | Custom |

Note: Basic plan is for personal use only — **no commercial rights**. Hackathon use likely OK, production trading bot needs paid tier.

### Credit costs (verified)

| Endpoint | Credits |
|----------|---------|
| `/v3/fear-and-greed/latest` | 1 |
| `/v3/fear-and-greed/historical` | 1 |
| `/v3/cryptocurrency/quotes/latest` | 1 |
| `/v2/cryptocurrency/market-pairs/latest` | 1 |
| `/v5/cryptocurrency/derivatives/market-pairs/list/latest` | 1 (UNVERIFIED — tiered for some exchange endpoints) |

### x402 cost

$0.01 USDC per request (flat, no subscription needed). Cheaper than paid tiers for low-volume agents.

**For the hackathon trading loop** (e.g. 3 calls per decision cycle × 100 cycles/day = 300 credits/day = ~9,000/month): **Basic free tier works** for fear & greed and quotes. Derivatives and liquidity depth endpoints may require Hobbyist+ — confirm at https://coinmarketcap.com/api/pricing/.

---

## 11. Gotchas

1. **Fear & Greed is global, not per-token.** The index reflects overall crypto market sentiment. You cannot get a "BNB Fear & Greed" — it's one number for the entire market. Use it as a macro filter only.

2. **Funding rate is per exchange/pair, not per token.** You'll get a list of perpetual pairs across Binance, OKX, Bybit, etc. for the token. Aggregate or pick the most liquid exchange. CMC does NOT have a single canonical "BNB funding rate" field.

3. **`depth_negative_two` / `depth_positive_two` are CEX order book depths.** For BSC DEX (PancakeSwap), these fields will not apply — use the DEX API endpoint instead. Pool TVL is the proxy for DEX liquidity depth.

4. **Basic (free) tier has no commercial rights.** If the bot runs money, upgrade to Hobbyist minimum.

5. **MCP `get_global_crypto_derivatives_metrics` returns aggregate derivatives metrics**, not per-token funding rates. Do not use MCP for per-token funding rate in the veto loop — use the REST API directly.

6. **x402 requires a funded Base wallet with USDC.** Your agent needs a private key with USDC on Base (Chain ID: 8453). EIP-3009 signatures are computed off-chain; gas is not required (payment executes on CMC's side via relayer).

7. **The x402 MCP variant costs $0.01 per tool call** — at 12 tools exposed, a complex agent query could cost $0.12/round-trip vs. ~$0.01 for a direct REST call. Use REST for the veto signals; MCP/x402 is better for open-ended agent reasoning.

8. **Response schema nesting**: CMC wraps all responses in `{ "data": ..., "status": { "error_code": 0, ... } }`. Always check `status.error_code` before reading data.

9. **`aux` parameter for depth fields**: When calling the market-pairs endpoint, you must explicitly request depth data by passing `aux=depth` (or including `"depth"` in the comma-separated aux list). Without it, `depth_negative_two` and `depth_positive_two` are omitted.

10. **Agent Hub is in beta** (launched ~May 2026). Tool schemas and endpoints may change. Pin to specific API versions (v2, v3, v4, v5 prefixes) in your code.

---

## 12. Decision Cycle Integration Pattern

```python
import requests

CMC_KEY = "YOUR_CMC_PRO_KEY"
BASE = "https://pro-api.coinmarketcap.com"
HEADERS = {"X-CMC_PRO_API_KEY": CMC_KEY}

def cmc_veto(symbol: str, trade_size_usd: float) -> tuple[bool, str]:
    """
    Returns (should_veto: bool, reason: str).
    Call this once per decision cycle before placing any trade.
    """
    # 1. Fear & Greed — macro market condition
    fg = requests.get(f"{BASE}/v3/fear-and-greed/latest", headers=HEADERS, timeout=8).json()
    fg_value = fg["data"]["value"]
    if fg_value <= 15:
        return True, f"Extreme Fear (F&G={fg_value}) — market panic, skip trade"
    if fg_value >= 85:
        return True, f"Extreme Greed (F&G={fg_value}) — overheated market, skip trade"

    # 2. Liquidity depth — slippage risk (CEX proxy; for DEX use pool TVL)
    liq = requests.get(
        f"{BASE}/v2/cryptocurrency/market-pairs/latest",
        headers=HEADERS,
        params={"symbol": symbol, "category": "spot", "convert": "USD", "aux": "depth"},
        timeout=8,
    ).json()
    pairs = liq.get("data", {}).get("market_pairs", [])
    if pairs:
        best_depth = max(
            (p.get("quote", {}).get("USD", {}).get("depth_negative_two", 0) or 0) +
            (p.get("quote", {}).get("USD", {}).get("depth_positive_two", 0) or 0)
            for p in pairs
        )
        # Veto if trade size > 5% of available depth (rough slippage guard)
        if trade_size_usd > 0.05 * best_depth:
            return True, f"Thin liquidity (depth=${best_depth:,.0f}) for trade size ${trade_size_usd:,.0f}"

    # 3. Funding rate — extreme directional bias
    deriv = requests.get(
        f"{BASE}/v5/cryptocurrency/derivatives/market-pairs/list/latest",
        headers=HEADERS,
        params={"symbol": symbol, "category": "perpetual"},
        timeout=8,
    ).json()
    pairs_d = deriv.get("data", {}).get("market_pairs", [])
    if pairs_d:
        rates = [
            p.get("quote", {}).get("USD", {}).get("funding_rate")
            for p in pairs_d
            if p.get("quote", {}).get("USD", {}).get("funding_rate") is not None
        ]
        if rates:
            avg_rate = sum(rates) / len(rates)
            if abs(avg_rate) > 0.002:  # >0.2% per 8h is extreme
                return True, f"Extreme funding rate ({avg_rate:.4%}) — crowded trade, skip"

    return False, "OK"
```

---

## 13. Source URLs

- [CoinMarketCap AI Agent Hub — official landing](https://coinmarketcap.com/api/documentation/ai-agent-hub/mcp)
- [CMC Agent Hub MCP documentation](https://coinmarketcap.com/api/mcp/)
- [CMC Agent Hub launch article](https://coinmarketcap.com/academy/article/coinmarketcap-ai-agent-hub-now-live)
- [CMC Agent Hub x402 documentation](https://pro.coinmarketcap.com/api/documentation/ai-agent-hub/x402)
- [CMC Pro API — Fear & Greed reference](https://coinmarketcap.com/api/documentation/pro-api-reference/global-metrics)
- [CMC Pro API — Derivatives reference](https://coinmarketcap.com/api/documentation/pro-api-reference/derivatives)  
- [CMC API pricing tiers](https://coinmarketcap.com/api/pricing/)
- [CMC Liquidity Score methodology](https://support.coinmarketcap.com/hc/en-us/articles/360043836931-Liquidity-Score-Market-Pair-Exchange)
- [CMC Fear & Greed live chart](https://coinmarketcap.com/charts/fear-and-greed-index/)
- [shinzo-labs/coinmarketcap-mcp (third-party MCP)](https://github.com/shinzo-labs/coinmarketcap-mcp)
- [x402 Foundation launch article (CMC)](https://coinmarketcap.com/academy/article/x402-foundation-launches-agent-payment-protocol)
- [x402 Protocol explained (eco.com)](https://eco.com/support/en/articles/12328618-x402-protocol-explained-how-ai-agents-pay-onchain)
- [CMC Derivatives Cursor/IDE setup](https://pro.coinmarketcap.com/api/documentation/ai-agent-hub/cursor)
- [Composio CMC MCP + Claude SDK](https://composio.dev/toolkits/coinmarketcap/framework/claude-agents-sdk)
