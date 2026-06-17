# Experiment Findings

Throwaway PoCs in `experiment/` to confirm the core idea works on live data before
committing to the full build. Run with the local venv: `experiment/.venv/bin/python experiment/<file>.py`.

## What was PROVEN ✅

1. **The edge is readable, keyless, on live chain.** `onchain_flow.py` connects to
   `bsc-rpc.publicnode.com`, verifies the token via on-chain `symbol()`, pulls real
   BEP-20 Transfer logs over a trailing block window, and computes per-wallet net flow
   (received − sent). Live run on **CAKE** returned real accumulators/distributors.
2. **The pipeline wiring works.** `divergence_poc.py` feeds REAL on-chain flow + synthetic
   social scenarios through divergence → conviction → threshold gate. The four setups
   classify correctly and the CMC veto + conviction threshold gate fire as designed.

## What BROKE — key design flaw the experiment exposed ⚠️

The conviction scorer is a **flat weighted sum** (more social velocity + more Reddit
agreement → higher score). But our thesis says the **highest-conviction setup is early
accumulation: whales in WHILE retail is still asleep** — i.e. LOW social by definition.

Live result:

| scenario | setup | score | fired? |
|---|---|---|---|
| Whales in, retail asleep (PRIME) | accumulation | **50.1** | **no** ❌ |
| Whales in, retail euphoric (weaker) | confirmation | 74.4 | yes |
| Whales OUT, retail euphoric | distribution | 75.1 | yes (exit) |
| Mixed / weak | no_trade | 23.1 | no ✅ |
| Strong setup + CMC veto | accumulation | 0.0 | no ✅ |

The scorer **penalizes the exact edge we want to trade.** A flat positive weight on social
contradicts the divergence idea.

### Required fix (for production `brain/conviction.py`)

Scoring must be **setup-conditional**, not a single global weighted sum:
- **accumulation**: low social velocity is a **bonus**, not a penalty. Score driven mainly
  by on-chain flow magnitude; reward social *quietness*.
- **confirmation**: social velocity + agreement contribute positively (momentum).
- **distribution (exit)**: high social + negative flow drive the exit score.

Net: invert/condition the social term by setup. Re-tune via `backtest.py`. This is a
genuine thesis-vs-implementation gap, not a tuning nit — fix before Phase C scoring is final.

## Infra realities confirmed (match research/)

- Public `bsc-dataseed.binance.org` → `limit exceeded` / no getLogs. `rpc.ankr.com/bsc` →
  needs API key. **`bsc-rpc.publicnode.com` works keyless for getLogs** (our dev RPC).
- BSC is POA → `ExtraDataToPOAMiddleware` at layer 0 (web3.py 7.16) — confirmed working.
- Transfer topic0 `0xddf252...3b3ef`, indexed from/to in topics[1]/[2], value in data — confirmed.

## Caveats (PoC only)

- Net flow is in **token units**, not USD — production needs a price feed (CMC) for USD sizing.
- "Smart wallets" here = top-5 net accumulators in the window (a stand-in). Production needs
  the curated PnL-filtered wallet set (spec §8.1).
- Social data is **synthetic**. Twitter/Reddit collectors not exercised (no API keys yet).
- Short block window (~600 blocks) for speed; production uses the 6h trailing window.
