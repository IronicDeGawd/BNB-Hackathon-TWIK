# Competition Registration — how to actually do it

> **Deadline: register on-chain BEFORE June 22 (trading window open).** Late entries rejected.

## The situation (verified 2026-06-18 against live docs)
The hackathon rules say register via `twak compete register` or the `competition_register`
MCP action. **Neither exists** in any public documentation:
- **TWAK** (CLI / MCP / skills / key-management / auth) — no `compete`/`register` command, no
  private-key export, no arbitrary contract-call. It will NOT sign this for you.
- **CMC Agent Hub MCP** (`https://mcp.coinmarketcap.com/mcp`) — 12 tools, all data/analysis.
  No registration tool.

The on-chain target IS real and verified:
- Contract: **`CompetitionRegistry` @ `0x212c61b9b72c95d95bf29cf032f5e5635629aed5`** (BSC, verified)
- `function register() external` — caller (your agent wallet) gets added
- `mapping(address=>bool) isRegistered` — status check (read-only)
- `event Registered(address indexed participant)` — the participant list is built from these logs

## What this means
Registration is an **organizer-provided** step (participant-gated), because the trading wallet is
the non-exportable TWAK wallet — only a hackathon tool that signs through TWAK can call `register()`
for it. This repo's `twak.register()` therefore does NOT auto-register; it raises with guidance.

## Do this (before June 22)
1. **Ask in the Builder Telegram / DoraHacks BUIDL page** for the exact register tool/command:
   *"How do I register my TWAK agent wallet on `0x212c…aed5`? `twak compete register` isn't a real command."*
   (Sources: the hackathon page's "Join Builder Telegram" + "Register on DoraHacks".)
2. Run that tool for wallet **`TWAK_WALLET_ADDRESS`** (your `0x4d58…` BSC address).
3. **Verify**: `python -c "from execution import twak; import os; os.environ['DRY_RUN']='false'; print(twak.is_registered())"`
   → must print `True` (this is a key-free read; safe to run).
4. Also submit the agent address + strategy writeup on DoraHacks.

## If the organizers confirm a direct call is allowed
If they say "just call register() yourself," the only way to sign it is with the wallet key —
which TWAK won't export. In that case create a wallet you control the key for (web3/ethers),
fund + register + trade with THAT, and skip TWAK self-custody (loses the TWAK special-prize
points, but unblocks). Confirm with organizers first — don't assume.
