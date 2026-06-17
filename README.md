# Conviction Agent

> A crypto-native autonomous trading agent for the **BNB Hack: AI Trading Agent Edition (Track 1)**.
> Trade the **divergence** between what retail says (Twitter + Reddit hype) and what smart money does
> (BSC on-chain wallet flow) — gated by CoinMarketCap structural data and hard risk rules.

## The pitch

Most social-sentiment bots are lagging indicators: by the time a coin is trending, the move is
priced in. Conviction Agent inverts this. It treats **social hype** and **on-chain smart-money flow**
as two independent signals and only acts when they *disagree in an exploitable way* — whales quietly
accumulating a coin retail hasn't noticed yet (early entry), or retail euphoric while smart wallets
distribute (early exit). CoinMarketCap data is the sanity-check layer (liquidity, funding, Fear &
Greed). Trust Wallet Agent Kit (TWAK) is the self-custody execution layer — the agent signs and
broadcasts its own trades on BSC, hands-off, inside hard risk guardrails. Capital at risk is small;
the edge is in the signal, not the size.

## Architecture

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

Cycle cadence: **every 15 minutes** (96 cycles/day).

## Repo layout

```
config/      tokens (149 eligible), watchlist (~25), settings (single source of truth)
signals/     twitter, reddit, onchain, cmc collectors
brain/       divergence detector, conviction scorer, sqlite memory
risk/        guardrails — the disqualifier defense
execution/   twak — the only signer
agent.py     main loop      backtest.py  offline replay      tests/  scorer + risk-gate tests
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill secrets — NEVER commit .env
pytest                      # config smoke tests run today (no keys needed)
```

## Status

Scaffold stage. Module logic is stubbed by build phase (A–E) per the build spec.

- [ ] **Phase A** — config foundations (settings done; **token addresses unresolved**)
- [ ] **Phase B** — signal collectors (twitter, reddit, onchain, cmc)
- [ ] **Phase C** — brain (divergence, conviction, memory)
- [ ] **Phase D** — risk guardrails + TWAK execution
- [ ] **Phase E** — main loop + backtest

> ⚠️ `config/tokens.py` addresses are intentionally `None`. They must be resolved to canonical,
> BscScan+CMC-verified BEP-20 contracts before any live trade. An unverified address risks swapping
> into a clone/scam contract.

## Submission checklist

- [ ] Public repo + clean README + architecture diagram
- [ ] On-chain proof: agent wallet address + sample tx hashes (BscScan links)
- [ ] Demo video — self-custody + autonomous-signing loop end to end
- [ ] Strategy writeup on DoraHacks (divergence thesis + results)
- [ ] Agent registered on-chain **before June 22** trading window
- [ ] `rationale_text` surfaced in demo so judges see WHY each trade fired

## Timeline

Build closes **June 21** · live trading **June 22–28** · judging **June 29 – July 5**.
