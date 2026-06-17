"""TWAK (Trust Wallet Agent Kit) — the ONLY signer.

TWAK is a TypeScript CLI (no Python SDK), so this is a subprocess wrapper. Keys stay
client-side; the agent signs + broadcasts its own BSC txs. Every tx hash is logged.

SAFETY: DRY_RUN defaults TRUE. In dry-run nothing is broadcast — calls return a
deterministic simulated tx hash so the whole loop is exercisable without spending funds.
The real path requires DRY_RUN=false AND a configured key, and runs the TWAK CLI.

# The exact TWAK CLI sub-commands below are UNVERIFIED against official docs (the
# hackathon brief confirms `twak compete register` exists; swap/balance/x402 flags are
# best-effort from research). Confirm against the Trust Wallet portal before live use.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess

log = logging.getLogger("conviction.twak")

COMPETITION_CONTRACT = "0x212c61b9b72c95d95bf29cf032f5e5635629aed5"  # BSC, from hackathon rules
TWAK_BIN = os.getenv("TWAK_BIN", "twak")

_sim_nonce = 0


# --------------------------------------------------------------------------- #
def _dry_run() -> bool:
    return os.getenv("DRY_RUN", "true").strip().lower() not in ("false", "0", "no")


def _sim_hash(*parts: str) -> str:
    """Deterministic fake tx hash for dry-run (clearly tagged, never a real broadcast)."""
    global _sim_nonce
    _sim_nonce += 1
    digest = hashlib.sha256("|".join([*parts, str(_sim_nonce)]).encode()).hexdigest()
    return "0xDRYRUN" + digest[:58]


def _run(args: list[str]) -> str:
    """Run a TWAK CLI command, return stdout. Raises on failure (caller decides)."""
    cmd = [TWAK_BIN, *args]
    log.info("twak: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"twak failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


def _require_live_config() -> None:
    if not os.getenv("TWAK_PRIVATE_KEY") and not os.getenv("TWAK_WALLET_ADDRESS"):
        raise RuntimeError("live execution requested but no TWAK wallet configured (.env)")


# --------------------------------------------------------------------------- #
def is_registered() -> bool:
    """Check on-chain registration state (for idempotent register())."""
    if _dry_run():
        return False
    try:
        out = _run(["compete", "status", "--json"])      # UNVERIFIED command
        return bool(json.loads(out).get("registered"))
    except Exception as e:
        log.warning("registration status check failed: %s", e)
        return False


def register() -> str:
    """Register the agent wallet to the competition contract on BSC (idempotent).

    Via `twak compete register` (or the `competition_register` MCP action). Must run
    BEFORE the June 22 trading window — the contract rejects late entries. Returns tx hash.
    """
    if _dry_run():
        return _sim_hash("register", COMPETITION_CONTRACT)
    _require_live_config()
    if is_registered():
        log.info("already registered — skipping")
        return ""
    return _run(["compete", "register"])                  # UNVERIFIED exact flags


def get_balance() -> dict[str, float]:
    """Current in-scope holdings: {symbol: usd_value}. Empty in dry-run."""
    if _dry_run():
        return {}
    try:
        return json.loads(_run(["balance", "--json"]))    # UNVERIFIED command
    except Exception as e:
        log.warning("balance read failed: %s", e)
        return {}


def execute_trade(symbol: str, side: str, size_usd: float) -> str:
    """Build the swap, sign LOCALLY, broadcast on BSC. Respects SLIPPAGE_BPS.

    side: "buy" | "sell". Returns tx hash (simulated under DRY_RUN). NEVER broadcasts
    in dry-run — that is the default, so accidental real trades cannot happen.
    """
    if side not in ("buy", "sell"):
        raise ValueError(f"bad side: {side}")
    if _dry_run():
        h = _sim_hash("trade", symbol, side, f"{size_usd:.2f}")
        log.info("[DRY_RUN] %s %s $%.2f -> %s", side, symbol, size_usd, h)
        return h

    _require_live_config()
    from config.settings import SLIPPAGE_BPS
    slippage_pct = SLIPPAGE_BPS / 100
    # UNVERIFIED command shape — confirm against TWAK docs before live trading.
    return _run(["swap", side, symbol, "--usd", f"{size_usd:.2f}",
                 "--chain", "bsc", "--slippage", f"{slippage_pct}"])


def pay_x402(endpoint: str) -> bool:
    """Pay-per-request via x402 for data/inference within the loop."""
    if _dry_run():
        log.info("[DRY_RUN] x402 pay -> %s", endpoint)
        return True
    _require_live_config()
    try:
        _run(["x402", "request", endpoint, "--yes"])      # UNVERIFIED command
        return True
    except Exception as e:
        log.warning("x402 payment failed: %s", e)
        return False
