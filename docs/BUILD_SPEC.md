# Conviction Agent — Build Spec

> A crypto-native autonomous trading agent for the BNB Hack: AI Trading Agent Edition (Track 1).
> Core thesis: trade the **divergence** between what retail says (Twitter + Reddit social hype) and
> what smart money does (BSC on-chain wallet flow), gated by CMC structural data and hard risk rules.

---

## 0. One-paragraph pitch

Most social-sentiment trading bots are lagging indicators: by the time a coin is trending, the move
is priced in. Conviction Agent inverts this. It treats social hype and on-chain smart-money flow as
two independent signals and only acts when they disagree in an exploitable way — whales quietly
accumulating a coin retail hasn't noticed yet (early entry), or retail euphoric while smart wallets
distribute (early exit). CoinMarketCap data is the sanity-check layer (liquidity, funding, Fear &
Greed). Trust Wallet Agent Kit (TWAK) is the self-custody execution layer — the agent signs and
broadcasts its own trades on BSC, hands-off, inside hard risk guardrails. Capital at risk is
intentionally small; the edge is in the signal, not the size.

## 1. Why this can win
- Track 1 main prize scored on live PnL with a max-drawdown gate. Divergence strategy is selective
  (few, high-conviction trades) which naturally controls drawdown.
- Best Use of TWAK ($2k): TWAK is the sole execution layer (local signing + autonomous + x402).
- Best Use of Agent Hub ($2k): CMC wired via MCP, used every decision cycle.
- Originality: social-vs-onchain divergence angle + Reddit as a second social axis.

## 2. Hard constraints

| Constraint | Value |
|---|---|
| Eligible tokens | Fixed list of 149 BEP-20 tokens on CMC |
| Min trades to qualify | ≥1 trade/day, ≥7 over the trading week |
| Max drawdown gate | DISQUALIFY if breached (assume 30%) |
| Non-zero in-scope balance at start | required to be ranked |
| Sub-$1 portfolio hours | counted as 0% return |
| Twitter API budget | ≤1,000 calls/day |
| Capital at risk | <$100 |
| Execution layer | TWAK only (no other signer) |
| No token launches during event | hard rule |

**Registration:** register on-chain before June 22 via `twak compete register` OR the
`competition_register` MCP action. Also submit agent address + strategy writeup on DoraHacks. The
agent does the registration tx itself.

**Timeline:** build closes June 21; live trading June 22–28; judging June 29–July 5.

## 3. Architecture

```
   SIGNAL      Twitter/X + Reddit      BSC on-chain          CMC Agent Hub
   SOURCES     mention velocity        smart-wallet flow     F&G, funding, liquidity
                      └───────────────────┼───────────────────┘
                                          ▼
                            Divergence detector  (CMC = sanity filter)
                                          ▼
                            Conviction scorer    (0–100, direction + confidence)
                                          ▼
                            Risk gate            (drawdown, allowlist, sizing, kill switch)
                                          ▼
                            TWAK autonomous exec (local sign + x402 + BSC)
```

Cadence: every 15 minutes (96 cycles/day). Twitter budget ≈ 10 calls/cycle (batched).

## 5. Module specs — build order

### Phase A — Foundations
- `config/tokens.py`: 149 eligible symbols + verified canonical BEP-20 addresses. `ELIGIBLE` +
  `is_eligible()`.
- `config/watchlist.py`: ~25 liquid, social-active tokens (subset). Candidates: CAKE, AVAX, LINK,
  UNI, AAVE, DOT, ATOM, INJ, FET, BONK, FLOKI, PENGU, TWT, SFP, ASTER. Confirm BSC pool depth.
- `config/settings.py`: single source of truth — cadence, thresholds, risk params, weights.

### Phase B — Signal collectors
- `signals/twitter.py` (PRIMARY, paid wrapper): one batched query/cycle; velocity =
  mentions(hour)/baseline(24h). Hard daily-budget guard.
- `signals/reddit.py` (SECONDARY, free via Agent Reach): independent axis, NOT averaged with
  Twitter. Fault-tolerant — never crash the loop.
- `signals/onchain.py` (the edge, free BSC RPC): curated smart-wallet net flow over trailing window
  via web3.py Transfer logs. Slowest to get right; cache aggressively.
- `signals/cmc.py` (structural, MCP): F&G, funding, liquidity. VETO-only (never generates signals).
  Use x402 pay-per-request where supported.

### Phase C — Brain
- `brain/memory.py`: SQLite — signals, trades, portfolio tables. State across wakes.
- `brain/divergence.py` (core IP): accumulation (long, highest), confirmation (long, lower),
  distribution (exit/avoid), no-trade. Structured signal per token.
- `brain/conviction.py`: deterministic weighted blend → 0–100 + direction. LLM ONLY for
  `rationale_text` (human-readable why; templated fallback on failure).

### Phase D — Risk + execution
- `risk/guardrails.py` (BUILD BEFORE EXECUTION): drawdown kill switch (25%, below 30% gate),
  allowlist, position sizing (≤20%), cooldown (60m), daily-floor nudge, dust guard.
- `execution/twak.py` (ONLY signer): `register()` (idempotent), `get_balance()`,
  `execute_trade()` (local sign, BSC broadcast, respect slippage), `pay_x402()`. Log every tx hash.

### Phase E — Loop + backtest
- `backtest.py`: offline replay to tune threshold + weights before live.
- `agent.py`: main loop — collect (parallel, fault-tolerant) → divergence → conviction → risk gate
  → execute → enforce daily floor → update drawdown → log. Top-level try/except per cycle.

## 6. Reliability rules
1. No single point of failure in signals (on-chain is the only must-have; it's free + self-hosted).
2. The loop never crashes — top-level try/except per cycle.
3. Risk gate (drawdown) runs unconditionally every cycle.
4. Idempotent registration — check state first.
5. Watch the Twitter budget counter — hard stop at 1,000/day.
6. Test `agent-reach doctor` daily if relying on it for Reddit.

## 7. Submission checklist
- [ ] Public repo + clean README + architecture diagram
- [ ] On-chain proof: agent address + sample tx hashes (BscScan links)
- [ ] Demo video — self-custody + autonomous-signing loop end to end
- [ ] Strategy writeup on DoraHacks (divergence thesis + results)
- [ ] Agent registered on-chain before June 22
- [ ] `rationale_text` surfaced in demo
- [ ] No token launches / fundraising during event

## 8. Open decisions before Day 1
1. Smart-wallet seed list — own discovery (BscScan + PnL filter) vs public labeled set?
2. Twitter wrapper — twitterapi.io vs getxapi.
3. LLM in loop or pure rules? **Decided: rules-based core + LLM only for rationale_text.**
4. Spot-only or perps? **Recommendation: start spot-only.**
