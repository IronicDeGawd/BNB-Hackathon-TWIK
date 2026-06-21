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
config/      tokens (148 eligible), watchlist (25), settings (single source of truth)
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
pytest                      # 74 tests, no keys needed
```

## Running

```bash
# 1) register the agent wallet on-chain (one-time; needs BNB for gas)
export TWAK_WALLET_PASSWORD=<wallet password>
twak compete register && twak compete status      # expect registered: true

# 2) run the agent. DRY_RUN=true (default) simulates; set false to trade live on BSC.
DRY_RUN=true  python agent.py     # paper run — nothing broadcast
DRY_RUN=false python agent.py     # LIVE — signs + broadcasts real BSC swaps
```

The rationale line is written by **Gemini Flash via Vertex AI** (ADC auth, set `VERTEX_PROJECT`);
it is off the hot path and falls back to a deterministic template on any error — it never blocks a trade.

## Status

Built and operational, registered on-chain for Track 1, **74 tests pass**.

- Config foundations — settings, 148-token allowlist, 25-token watchlist; addresses resolved 111/148 (watchlist 23/25)
- Signal collectors — twitter, reddit, onchain (smart-wallet flow), cmc
- Brain — divergence detector, conviction scorer, sqlite memory
- Risk guardrails — drawdown kill switch, sizing, daily cap + day-end floor — and TWAK execution
- Main loop + offline backtest
- Registered on-chain via `twak compete register` — wallet `0x4d5812150DBBd2D0116c54b420BB10d1dB9BB583` (BSC)

## Timeline

Live trading **June 22–28** · judging **June 29 – July 5**.
