# Hackathon Rules — authoritative (from the official DoraHacks page)

> BNB Hack: AI Trading Agent Edition ⚡️ CoinMarketCap × Trust Wallet. $36,000 pool.
> This file supersedes any speculative findings in `hackathon-resources.md`.

## Our track
**Track 1 — Autonomous Trading Agents** ($24,000, 5 winners). Agent reads markets via
CMC, decides, and signs + processes its own txs via TWAK. Trades live on BSC during the
competition week; scored on real PnL.

Prizes: 1st $10k · 2nd $6k · 3rd $4k · 4th $2k · 5th $2k.

## Scoring (Track 1)
- **Live PnL** — ranked by total return over a held-out trading window.
- **Max drawdown cap = risk gate.** Blow past the threshold (example **30%**) → **DISQUALIFIED**
  regardless of headline return. (Our internal kill switch = 25%, below this.)
- **Min trade count:** ≥1 trade/day, ≥7 over the week.
- **Non-zero in-scope balance at competition start** required to be ranked.
- **Returns measured hourly.** Any hour starting with portfolio ≤ $1 = 0% for that hour.
  Keep capital deployed; don't drain to dust.
- Simulated transaction costs apply. "Most profit without blowing up."

## Registration (on-chain — Track 1)
- Competition contract on BSC: **`0x212c61b9b72c95d95bf29cf032f5e5635629aed5`**
  (https://bsctrace.com/address/0x212c61b9b72c95d95bf29cf032f5e5635629aed5)
- Register agent wallet via **`twak compete register`** (CLI) or MCP action
  **`competition_register`**. Both resolve the agent wallet + submit the tx.
- Deadline-enforced: entries after the trading window opens are rejected.
- ALSO submit the agent address + a strategy writeup on **DoraHacks**.

## Eligible tokens
Fixed list of **149 BEP-20 tokens** on CMC (source lists 149 line-items; SLX is duplicated
→ 148 unique). Full list lives in `config/tokens.py` (`ELIGIBLE`). **Trades outside the list
do not count.** Includes our watchlist candidates (CAKE, AVAX, LINK, UNI, AAVE, DOT, ATOM,
INJ, FET, BONK, FLOKI, PENGU, TWT, SFP, ASTER) — all confirmed present.

## Timeline (today = 2026-06-15)
- Build window: June 3 – **June 21** (≈6 days left).
- Live trading: **June 22 – June 28**.
- Judging: June 29 – July 5. Winners: week of July 6.
- **Register on-chain BEFORE June 22.**

## Provided stack — FREE for the duration (correction to earlier research)
- 🧠 **CMC AI Agent Hub** — data via MCP, x402, CLI, Skills. FREE for the hackathon.
- 🔐 **TWAK** — self-custody local signing, 30+ chains, MCP/REST/CLI/LangChain, native x402.
- 🛠️ **BNB AI Agent SDK** — Python, on-chain identity (ERC-8004) + job escrow (ERC-8183).
  NOT a trading framework; optional for us. See `bnb-agent-sdk.md`.
- 🌐 BNB Chain (BSC, chain id 56).
- Telegram: https://t.me/+MhiOLT0YUnlmNWFk

## Special prizes ($2,000 each, stack on top of a main placement)
1. **Best Use of TWAK (Track 1)** — discretionary panel. Scoring weights:
   TWAK integration depth 30 · self-custody integrity 25 (penalty ladder, not hard DQ) ·
   autonomous execution + guardrails 20 · native x402 usage 10 · originality 10 · demo 5.
   Tie-break: cleanest self-custody → deepest TWAK integration → most substantive x402.
2. **Best Use of Agent Hub** (both tracks).
3. **Best Use of BNB AI Agent SDK** (both tracks).

## Submission requirements
- Public repo + demo link/video or clear setup instructions.
- On-chain proof: agent address on BSC.
- **No token launches / fundraising / airdrop pumping during the event.**
- AI tooling encouraged ("vibe-code freely; we care that it works").

## Implications for our build
- **CMC is free** → use CMC Agent Hub (MCP/CLI) directly; the x402-for-CMC cost worry is moot.
- x402 still matters for the **TWAK special prize** (native x402 in the trade loop) — revisit
  the earlier "defer x402" call against this 10-pt criterion.
- Drawdown DQ confirmed at 30% → keep internal cap at 25%.
- Registration is a TWAK call to a known contract — wire `execution/twak.register()` to it.
