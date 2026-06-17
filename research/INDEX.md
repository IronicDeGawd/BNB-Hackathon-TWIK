# Research Index — third-party tool docs

Scraped from official docs/GitHub. Each file: setup, auth, the APIs we need, real code,
rate limits/pricing, gotchas, source URLs.

| File | Tool | Confidence | Critical takeaway |
|---|---|---|---|
| `twak.md` | Trust Wallet Agent Kit | High (med on register) | **TS/Node CLI, no Python SDK** — agent must shell out to `twak`. Competition-register syntax unconfirmed; check DoraHacks/Telegram. |
| `cmc-agent-hub.md` | CoinMarketCap Agent Hub | High | MCP live at `mcp.coinmarketcap.com/mcp` (key header). Fear&Greed `GET /v3/fear-and-greed/latest`. x402 path on **Base**. Free tier = no commercial rights. |
| `x402.md` | x402 protocol | High (on chains) | **No BSC support** — USDT on BSC lacks EIP-3009. Pay on Base/Polygon/Arbitrum; trade on BSC separately. |
| `twitter-wrapper.md` | twitterapi.io | High | `GET /twitter/tweet/advanced_search`, `X-API-Key` header. One batched `($A OR $B ...)` query covers the watchlist. ~$0.29/day at our cadence. |
| `bscscan-api.md` | BscScan API (V2) | High | V2 only: `api.etherscan.io/v2/api?chainid=56`. **BSC needs PAID plan** (~$49/mo Lite). Holder list = Standard+. |
| `web3py-bsc.md` | web3.py on BSC | High | POA `ExtraDataToPOAMiddleware` layer 0. **Public dataseed RPC blocks getLogs** — use third-party RPC. Chunk ≤2000 blocks. |
| `reddit-agent-reach.md` | Agent Reach / Reddit | Med-High | Agent Reach (`rdt-cli`, cookie auth) is fragile/single-maintainer. **PRAW + official Reddit API is the reliable fallback** (60 req/min). |
| `hackathon-rules.md` | **Official rules (authoritative)** | High | Track 1 scoring, 30% drawdown DQ, registration contract `0x212c...aed5`, full stack FREE, special-prize weights. **Supersedes hackathon-resources.md.** |
| `hackathon-resources.md` | Early speculative resource scrape | Low (superseded) | Pre-rules guesses; CMC-cost worry was WRONG (stack is free). Kept for history. |
| `bnb-agent-sdk.md` | BNB AI Agent SDK | High | Python `bnbagent`. On-chain identity (ERC-8004) + job escrow (ERC-8183), NOT trading. Optional. Does not wrap TWAK/CMC. |

## Cross-cutting consequences for the build

1. **x402 chain split** — special-prize x402 payments happen on Base (CMC), NOT on the BSC
   trading chain. Plan two-chain wallet setup. Re-evaluate whether x402 is worth it vs cost.
2. **Two paid dependencies** to budget: BscScan V2 (~$49/mo) for smart-wallet discovery,
   CMC Hobbyist ($29/mo) if commercial-grade needed (hackathon free tier likely OK).
3. **RPC for the edge** — need a getLogs-capable RPC. `bsc-rpc.publicnode.com` works keyless
   for dev; get a NodeReal/QuickNode free key for production reliability.
4. **TWAK is a CLI** — execution layer is subprocess calls from Python, not an import.
5. **Reddit** — build against PRAW first; treat Agent Reach as optional upgrade.

See `../experiment/FINDINGS.md` for the live proof-of-concept results (and a scoring-model
flaw the experiment exposed).
