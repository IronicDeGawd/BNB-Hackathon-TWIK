"""TWAK (Trust Wallet Agent Kit) — the execution + signing layer.

Trades go through the TWAK CLI (TypeScript; no Python SDK) via subprocess, so keys
stay client-side and the agent signs + broadcasts its own BSC txs. Competition
registration goes through the TWAK CLI `compete` command
(`twak compete register` / `twak compete status`).

SAFETY: DRY_RUN defaults TRUE. In dry-run nothing is broadcast — calls return a
deterministic simulated tx hash so the whole loop is exercisable without spending.
The real path requires DRY_RUN=false.

Setup (one-time, on the machine):
    twak auth setup --api-key <k> --api-secret <s>   # from portal.trustwallet.com
    twak wallet create --password <pw>               # creates the self-custody agent wallet
    twak wallet keychain save --password <pw>         # passwordless CLI use
Verified TWAK CLI (developer.trustwallet.com/developer/agent-sdk/cli-reference):
    twak swap <amount> <from> <to> --chain bsc [--slippage <pct>] [--json]
    twak wallet portfolio --chains bsc [--json]
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess

from config.settings import SLIPPAGE_BPS
from config.tokens import is_eligible

log = logging.getLogger("conviction.twak")

TWAK_BIN = os.getenv("TWAK_BIN", "twak")
QUOTE_TOKEN = os.getenv("QUOTE_TOKEN", "USDT")          # base currency we buy/sell against on BSC

_TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")           # a real BSC tx hash
_sim_nonce = 0
_live_frozen: bool | None = None                        # cached simulate/live decision


# --------------------------------------------------------------------------- #
def _dry_run() -> bool:
    """True unless DRY_RUN is explicitly false/0/no.

    Frozen on first call so the simulate/live decision cannot flip mid-process
    (e.g. a later load_dotenv(override=True)). Tests reset via _reset_dry_run().
    """
    global _live_frozen
    if _live_frozen is None:
        _live_frozen = os.getenv("DRY_RUN", "true").strip().lower() not in ("false", "0", "no")
    return _live_frozen


def _reset_dry_run() -> None:
    """Test hook: clear the frozen value so the next _dry_run() re-reads the env."""
    global _live_frozen
    _live_frozen = None


def _sim_hash(*parts: str) -> str:
    """Deterministic fake tx hash for dry-run (clearly tagged, never a real broadcast)."""
    global _sim_nonce
    _sim_nonce += 1
    digest = hashlib.sha256("|".join([*parts, str(_sim_nonce)]).encode()).hexdigest()
    return "0xDRYRUN" + digest[:58]


def _fmt(amount: float) -> str:
    """Trim float for the CLI: enough precision for token qty, no trailing zeros."""
    return f"{amount:.8f}".rstrip("0").rstrip(".") or "0"


def _run(args: list[str]) -> str:
    """Run a TWAK CLI command, return stdout. Raises on failure (caller decides)."""
    cmd = [TWAK_BIN, *args]
    log.info("twak: %s", " ".join(cmd))
    env = os.environ.copy()
    # CLI expects TWAK_WALLET_PASSWORD; bridge from TWAK_PASSWORD if only that is set.
    if not env.get("TWAK_WALLET_PASSWORD") and env.get("TWAK_PASSWORD"):
        env["TWAK_WALLET_PASSWORD"] = env["TWAK_PASSWORD"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"twak failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


def _require_live_config() -> None:
    if not os.getenv("TWAK_WALLET_ADDRESS"):
        raise RuntimeError("live execution requested but TWAK_WALLET_ADDRESS not set (.env)")


# --------------------------------------------------------------------------- #
def is_registered() -> bool:
    """True if the agent wallet is registered for the competition.

    Reads `twak compete status --json` (read-only; needs the wallet password to derive
    the participant address, never the private key). Returns False on any error.
    """
    try:
        data = json.loads(_run(["compete", "status", "--json"]))
        return bool(data.get("registered"))
    except Exception as e:
        log.warning("registration status check failed: %s", e)
        return False


def register() -> str:
    """Register the agent wallet via `twak compete register` (one-time, on-chain, BSC).

    Self-custody: TWAK signs locally with the wallet password (TWAK_WALLET_PASSWORD or
    keychain); the private key is never exposed. The wallet needs BNB for gas.
    Idempotent — returns "" if already registered. Simulated under DRY_RUN.
    """
    if _dry_run():
        return _sim_hash("register", "compete")
    if is_registered():
        log.info("already registered")
        return ""
    _require_live_config()
    out = _run(["compete", "register", "--json"])
    try:
        d = json.loads(out)
        return d.get("txHash") or d.get("hash") or out
    except Exception:
        return out


def get_balance() -> dict[str, float]:
    """Current in-scope holdings {symbol: usd_value}. Empty in dry-run.

    Parses `twak wallet portfolio --chains bsc --json`. Schema is defensive — TWAK's
    portfolio JSON nests token holdings; adjust the keys here if the live shape differs.
    """
    if _dry_run():
        return {}
    try:
        data = json.loads(_run(["wallet", "portfolio", "--chains", "bsc", "--json"]))
        out: dict[str, float] = {}
        # tolerate a few likely shapes: {tokens:[{symbol,usdValue}]} or {bsc:{tokens:[...]}}
        buckets = []
        if isinstance(data, dict):
            if "tokens" in data:
                buckets = data["tokens"]
            else:
                for v in data.values():
                    if isinstance(v, dict) and "tokens" in v:
                        buckets += v["tokens"]
        for tk in buckets:
            sym = tk.get("symbol") or tk.get("ticker")
            usd = tk.get("usdValue") or tk.get("valueUsd") or tk.get("usd")
            if sym and usd is not None:
                out[sym.upper()] = float(usd)
        return out
    except Exception as e:
        log.warning("balance read failed: %s", e)
        return {}


def execute_trade(symbol: str, side: str, amount: float) -> str:
    """Swap via TWAK on BSC, sign LOCALLY, broadcast. Respects SLIPPAGE_BPS.

    side="buy"  -> spend `amount` of QUOTE_TOKEN (USD≈USDT) to acquire `symbol`.
    side="sell" -> sell `amount` units of `symbol` back to QUOTE_TOKEN.
    Returns tx hash (simulated under DRY_RUN — never broadcasts in dry-run).
    """
    if side not in ("buy", "sell"):
        raise ValueError(f"bad side: {side}")
    if _dry_run():
        h = _sim_hash("trade", symbol, side, _fmt(amount))
        log.info("[DRY_RUN] %s %s %s -> %s", side, symbol, _fmt(amount), h)
        return h

    if not is_eligible(symbol):                  # defense in depth — never broadcast off-allowlist
        raise RuntimeError(f"refusing to trade off-allowlist symbol: {symbol}")
    _require_live_config()
    slippage_pct = SLIPPAGE_BPS / 100  # bps -> percent (100 bps = 1.0)
    frm, to = (QUOTE_TOKEN, symbol) if side == "buy" else (symbol, QUOTE_TOKEN)
    # Verified syntax: twak swap <amount> <from> <to> --chain bsc --slippage <pct> --json
    out = _run(["swap", _fmt(amount), frm, to,
                "--chain", "bsc", "--slippage", f"{slippage_pct}", "--json"])
    try:
        d = json.loads(out)
        tx = d.get("txHash") or d.get("hash") or ""
    except Exception:
        tx = out.strip()
    if not _TX_HASH.match(tx):                    # don't let arbitrary stdout become a "confirmed" trade
        raise RuntimeError(f"swap did not return a valid tx hash (output: {out[:200]!r})")
    return tx


def pay_x402(endpoint: str) -> bool:
    """Pay-per-request via x402 for data/inference within the loop."""
    if _dry_run():
        log.info("[DRY_RUN] x402 pay -> %s", endpoint)
        return True
    _require_live_config()
    try:
        _run(["x402", "request", endpoint, "--yes"])      # confirm flag shape vs TWAK docs
        return True
    except Exception as e:
        log.warning("x402 payment failed: %s", e)
        return False
