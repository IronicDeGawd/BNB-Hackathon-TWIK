# Competition Registration — how to actually do it

> **Deadline: June 25 00:00 UTC.** Registration is on-chain on BSC; late entries rejected.
> Check the live deadline any time with `twak compete status`.

## The flow (verified via the TWAK CLI)
TWAK ships a `compete` command for this hackathon:

- `twak compete register` — registers your agent wallet on-chain (BSC). Signs locally
  through TWAK with the wallet password; the private key is never exported.
- `twak compete status` — shows `registered`, the participant address, and the deadline.

Both need the wallet password — pass `--password`, set `TWAK_WALLET_PASSWORD`, or save it
to the keychain (`twak wallet keychain save --password <pw>`). `register` also needs **BNB
in the wallet for gas**, so fund the wallet first.

This repo wraps both in `execution/twak.py`:
- `twak.register()` → runs `twak compete register` (simulated under `DRY_RUN`).
- `twak.is_registered()` → reads `twak compete status --json`.

## Do this (before the deadline)
1. **Fund the agent wallet** (`TWAK_WALLET_ADDRESS`, your `0x4d58…` BSC address) with a little
   **BNB for gas** (~$3 is plenty) plus your trading capital (USDT).
2. **Register**:
   ```
   export TWAK_WALLET_PASSWORD=<your wallet password>
   twak compete register
   ```
   (or `twak compete register --password <pw>`).
3. **Verify**:
   ```
   twak compete status
   ```
   → `registered: true`. (Or `python -c "from execution import twak; print(twak.is_registered())"`.)
4. **Submit on DoraHacks**: your agent address (`0x4d58…`) + a short strategy explainer, plus a
   link to the **public** repo and a demo link/video.

## Notes
- `.env` stores the password as `TWAK_PASSWORD`; the CLI wants `TWAK_WALLET_PASSWORD`. The code
  bridges this automatically (`execution/twak.py` `_run`), but if you run the CLI by hand, export
  `TWAK_WALLET_PASSWORD`.
- Registration is one-time and idempotent — `register()` returns early if already registered.
