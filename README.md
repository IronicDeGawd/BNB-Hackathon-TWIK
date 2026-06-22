# Vantage

> An autonomous BSC trading agent for the **BNB Hack: AI Trading Agent Edition (Track 1)**.
> Reads markets via **CoinMarketCap** (price momentum + structural data), trades the **divergence**
> against retail social hype, and signs + broadcasts its own BSC trades via **Trust Wallet Agent Kit**.

## The pitch

Most social-sentiment bots are lagging indicators: by the time a coin is trending, the move is
priced in. Vantage inverts this. The **primary signal is CMC price momentum** (the intended
"read markets via CMC" data source); it trades the **divergence** against retail social: price moving
while social is still flat = early accumulation (long); falling into social euphoria = distribution
(exit). CoinMarketCap structural data (liquidity, funding, Fear & Greed) is a hard **veto** layer, and
a Gemini risk-reviewer can veto a live entry. On-chain smart-money wallet flow is an **optional bonus**
axis (off unless a keyed RPC feeds it). Trust Wallet Agent Kit (TWAK) is the self-custody execution
layer — the agent signs and broadcasts its own swaps on BSC, hands-off, inside hard risk guardrails
(mark-to-market drawdown kill switch, per-token cap). Capital at risk is small; the edge is in the signal.

## Architecture

```
   SIGNALS     CMC momentum (PRIMARY)   Twitter/Reddit     CMC structural    [on-chain flow]
               1h price move            social velocity    liquidity/F&G     optional bonus
                      └───────────────────────┼────────────────────────────────────┘
                                              ▼
                            Divergence detector  (momentum vs social)
                                              ▼
                            Conviction scorer    (0–100, setup-conditional)
                                              ▼
                            Risk gate            (mark-to-market drawdown kill switch,
                                                  allowlist, per-token cap, daily floor)
                                              ▼
                            Gemini veto          (history-aware, fail-open)
                                              ▼
                            TWAK autonomous exec (local sign + BSC swaps)
                                              ▼
                            Telegram stream      (PnL + trade alerts, every 15m)
```

Cycle cadence: **every 15 minutes** (96 cycles/day).

## Repo layout

```
config/      tokens (148 eligible), watchlist (25), settings (single source of truth)
signals/     cmc (PRIMARY momentum + structural veto), twitter, reddit, onchain (optional bonus)
brain/       divergence detector, conviction scorer, sqlite memory, llm_confirm (Gemini veto)
risk/        guardrails — mark-to-market drawdown kill switch, per-token cap, daily floor
execution/   twak (signer + balances), notify (Telegram stream)
agent.py     main loop      backtest.py  offline replay      tests/  89 tests
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill secrets — NEVER commit .env
pytest                      # 89 tests, no keys needed
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

**Gemini 2.5 (Vertex AI / ADC)** does two off-hot-path jobs: writes the one-line trade rationale,
and — when `LLM_CONFIRM=true` — acts as a history-aware **veto** on live entries. Both fail open
(any error → template / allow), so the LLM never blocks or stalls a trade.

**Telegram:** set `TELEGRAM_RELAY_URL` (a relay box that can reach Telegram) or `TELEGRAM_BOT_TOKEN`
+ `TELEGRAM_CHAT_ID` to stream PnL + trade alerts. Heartbeat cadence via `HEARTBEAT_CYCLES`.

## Status

Built, **live on BSC**, registered on-chain for Track 1, **89 tests pass**.

- **Signal** — CMC 1h momentum (primary) + Twitter velocity + CMC structural veto; on-chain wallet flow optional
- **Brain** — divergence detector, setup-conditional conviction scorer, sqlite memory, Gemini veto
- **Risk** — mark-to-market drawdown kill switch (25%, below the 30% DQ), per-token cap, cooldown, daily floor
- **Execution** — TWAK self-custody swaps on BSC (USDT↔token); registered, funded
- **Ops** — runs unattended (cron watchdog), streams PnL + trades to Telegram every 15m
- Agent wallet `0x4d5812150DBBd2D0116c54b420BB10d1dB9BB583` (BSC)

## Timeline

Live trading **June 22–28** · judging **June 29 – July 5**.
