# BNB Hack: AI Trading Agent Edition — Research Notes

**Researched:** 2026-06-15  
**Confidence:** Medium — DoraHacks detail page was bot-walled (human-verification challenge); all findings
are from public press releases, CMC pages, and official announcements. The DoraHacks `/detail` page
likely contains participant-only resources not captured here.

---

## Overview & Links

| Item | Detail |
|------|--------|
| Hackathon name | BNB Hack: AI Trading Agent Edition |
| Organizers | BNB Chain + CoinMarketCap + Trust Wallet |
| Prize pool | $36,000 |
| Registration | https://dorahacks.io/hackathon/bnbhack-twt-cmc |
| Detail page | https://dorahacks.io/hackathon/bnbhack-twt-cmc/detail (requires login / CAPTCHA) |
| CMC hackathon page | https://coinmarketcap.com/api/hackathon/ |
| CMC Agent Hub | https://coinmarketcap.com/api/agent/ |
| x402 docs | https://pro.coinmarketcap.com/api/documentation/ai-agent-hub/x402 |
| Trust Wallet portal | https://portal.trustwallet.com/ |
| BNB Chain GitHub | https://github.com/bnb-chain |
| Builder Telegram | https://t.me/+MhiOLT0YUnlmNWFk |
| CMC contact | min.park@coinmarketcap.com |
| Press release (primary) | https://chainwire.org/2026/06/03/bnb-chain-coinmarketcap-and-trust-wallet-launch-36000-bnb-hack-ai-trading-agent-edition/ |

---

## Timeline

| Event | Date / UTC |
|-------|-----------|
| Registration open | June 3, 2026 |
| Submission lock | June 21, 2026 — 12:00 PM UTC |
| **Track 1 live trading window** | **June 22–28, 2026** |
| Winners announced | Week of July 6, 2026 |

---

## Tracks

### Track 1 — Autonomous Trading Agents ($24,000)
- 1st: $10,000 | 2nd: $6,000 | 3rd: $4,000 | 4th–5th: $2,000 each
- Build an end-to-end agent that signs and executes live trades on BSC during the June 22–28 window
- Must use at least one sponsor capability; using all three scores highest with judges
- Required stack: CMC Agent Hub (data/signal) + Trust Wallet Agent Kit (self-custody signing) + BNB AI Agent SDK

### Track 2 — Strategy Skills ($6,000)
- 1st: $3,000 | 2nd: $2,000 | 3rd: $1,000
- Create backtestable trading strategies published to the CMC Skills Marketplace

### Sponsor Special Prizes — $2,000 × 3
- Best use of CMC Agent Hub / Best use of Trust Wallet / Best use of BNB Chain

---

## Provided Resources & API Access

### CONFIRMED — Available to ALL participants

#### 1. CMC Agent Hub (CoinMarketCap)
- **What it is:** A structured, LLM-friendly data layer over CMC market data. Returns
  pre-computed signals (market regime, liquidity, ETF demand, cross-asset pressure, risk flags)
  instead of raw JSON.
- **Access paths (all participants):**
  - **MCP endpoint** — 12 professional data tools; requires a CMC API key
  - **x402 keyless pay-per-call** — $0.01 USDC per request on Base (Chain ID 8453); no API key
    or account required; payment acts as auth; failed requests are never charged
  - **CLI / IDE integrations** (Cursor, Claude, LangChain, etc.)
  - **Skills Marketplace** — 190+ reusable skills covering market overviews to on-chain token analysis
- **Source:** https://coinmarketcap.com/academy/article/coinmarketcap-ai-agent-hub-now-live

#### 2. Trust Wallet Agent Kit (TWAK)
- **What it is:** Self-custody signing across 30+ chains with native x402 support
- **Access:** Available via Trust Wallet Developer Portal (https://portal.trustwallet.com/)
- **Status:** CONFIRMED included — it is one of the three core required tools
- **Hackathon-specific free access/credits:** NOT CONFIRMED in any public source; check DoraHacks
  detail page or Telegram channel

#### 3. BNB AI Agent SDK
- **What it is:** SDK for BSC, PancakeSwap, and BSC perps integration
- **Access:** https://github.com/bnb-chain (search for AI Agent SDK repo)
- **Status:** CONFIRMED included as third core tool

### CONFIRMED — For finalists/winners only (NOT all participants)

| Resource | Who gets it |
|----------|-------------|
| CoinMarketCap Pro API subscription credits | Top finalists |
| Claude API compute credits | Winners |
| CMC Labs mentorship access | Finalists |
| Trust Wallet Reference Agent listing | Eligible finalists |
| BNB Chain Kickstart Package consideration | Top projects |

---

### NOT CONFIRMED / UNKNOWN — Your specific questions

| API / Service | Hackathon coverage? | Notes |
|--------------|--------------------|----|
| **BscScan / Etherscan API** (V2 paid, Chain 56) | **UNKNOWN — not mentioned anywhere** | No press release, CMC page, or announcement mentions BscScan or Etherscan. No sponsor deal confirmed. You likely need to pay (~$49/mo for Standard plan) or use a free workaround. Free tier (`api.bscscan.com`) supports `eth_getLogs` but with rate limits (5 calls/sec). |
| **CMC Pro API** (for all participants) | **NO** — winners only | x402 at $0.01/req is the participant path; CMC Pro credits go to finalists only |
| **NodeReal** | **NOT MENTIONED** | NodeReal appears in BNB ecosystem context (bnb-chain-agentkit GitHub) but is not named as a hackathon sponsor |
| **QuickNode** | **NOT MENTIONED** | Not a named sponsor |
| **Ankr** | **NOT MENTIONED** | Not a named sponsor |
| **BSC RPC endpoint** | **Partial** — BNB Chain's own free public RPC is implicitly available via BNB AI Agent SDK, but no premium sponsored endpoint confirmed |
| **Claude / Anthropic API credits** | **For winners only** — "Claude API compute" is listed as a winner benefit, not a participant benefit |
| **LLM inference credits (general)** | **UNKNOWN** | Not addressed in public materials |

---

### CMC x402 — Practical cost estimate for Track 1

The x402 path is the realistic data-access route for all participants:
- $0.01 USDC per CMC Agent Hub call
- No key needed — wallet signs Base-chain USDC transfer
- An agent making 100 calls/day × 7 days = ~$7 total cost
- This is the intended low-friction path for hackathon builders

---

## The Eligible 149-Token List

### Status: NOT PUBLICLY FOUND — likely gated behind DoraHacks registration or Telegram

**What is confirmed:**
- There is a fixed list of **149 BEP-20 tokens listed on CoinMarketCap** that agents are allowed
  to trade in Track 1
- The guardrails mention "token allowlists" — the 149 list is the allowlist
- Source: Multiple press releases confirm the 149-token count

**What was NOT found in any public source:**
- The actual token symbols or contract addresses
- A CSV, JSON, or API endpoint exposing the list
- A public link to the list

**Where to find it:**
1. **DoraHacks detail page** — https://dorahacks.io/hackathon/bnbhack-twt-cmc/detail
   This page requires passing a CAPTCHA/human-verification challenge and may require login.
   The rules/resources section almost certainly contains or links to the token list.

2. **Builder Telegram channel** — https://t.me/+MhiOLT0YUnlmNWFk
   Pinned messages or organizer posts likely contain the list or a link.

3. **CMC Agent Hub hackathon page** — https://coinmarketcap.com/api/hackathon/
   May have a downloadable assets section not captured by WebFetch (JavaScript-rendered).

4. **Contact** — min.park@coinmarketcap.com or the Telegram channel
   Ask for the token list CSV/JSON directly.

**Likely composition (UNVERIFIED — inference only):**
The 149 tokens are likely all BEP-20 tokens that: (a) are listed on CoinMarketCap, (b) trade on
PancakeSwap with sufficient liquidity, and (c) have BSC contract addresses verified on BscScan.
This narrows it to major BEP-20 assets (BNB, CAKE, BUSD, USDT, ETH bridged, etc.) plus mid-cap
BSC-native tokens. Do NOT use this inference for trading logic — get the official list.

---

## BscScan API — Free Workaround Assessment

Since BscScan V2 API (Chain 56) requires a paid plan and the hackathon does not appear to cover it:

**Free alternatives:**
1. **BscScan free tier** (`https://api.bscscan.com/api`) — supports `getLogs`, `getBlockNumber`,
   token transfer events. Rate limit: 5 calls/sec, no `eth_getLogs` on free tier for bulk.
2. **Public BSC RPC** (`https://bsc-dataseed.binance.org/`) — supports `eth_getLogs` natively via
   JSON-RPC; free but rate-limited and unreliable under load
3. **Ankr free tier** (`https://rpc.ankr.com/bsc`) — public RPC with `eth_getLogs` support,
   no key required for low usage
4. **NodeReal Community** (`https://nodereal.io/`) — free community tier with BSC RPC access
5. **QuickNode free trial** — 7-day trial with full BSC RPC including `eth_getLogs`

For a 7-day trading window with moderate call volumes, Ankr or NodeReal free tiers are likely
sufficient without paying for BscScan V2.

---

## Registration Requirements

- Solo builders or teams, age 18+
- Must use at least one sponsor capability (CMC Agent Hub, Trust Wallet Agent Kit, or BNB AI Agent SDK)
- Using all three scores highest with judges
- Submission on DoraHacks platform by June 21, 2026 — 12:00 PM UTC

---

## Sources

1. https://dorahacks.io/hackathon/bnbhack-twt-cmc (primary registration — CAPTCHA blocked)
2. https://coinmarketcap.com/api/hackathon/
3. https://chainwire.org/2026/06/03/bnb-chain-coinmarketcap-and-trust-wallet-launch-36000-bnb-hack-ai-trading-agent-edition/
4. https://chainwire.org/2026/06/03/bnb-chain-launches-36000-hackathon-to-advance-on-chain-ai-trading-agents/
5. https://coinmarketcap.com/academy/article/coinmarketcap-ai-agent-hub-now-live
6. https://pro.coinmarketcap.com/api/documentation/ai-agent-hub/x402
7. https://cryptobriefing.com/bnb-chain-coinmarketcap-and-trust-wallet-launch-36000-bnb-hack-ai-trading-agent-edition/
8. https://benzinga.com/pressreleases/26/06/52976446/bnb-chain-launches-36-000-hackathon-to-advance-on-chain-ai-trading-agents
9. https://cryptoslate.com/press-releases/bnb-chain-launches-36000-hackathon-to-advance-on-chain-ai-trading-agents/
10. https://bravenewcoin.com/press-release/bnb-chain-coinmarketcap-and-trust-wallet-launch-36000-bnb-hack-ai-trading-agent-edition
