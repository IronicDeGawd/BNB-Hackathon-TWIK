"""TWAK (Trust Wallet Agent Kit) — the execution + signing layer.

Trades go through the TWAK CLI (TypeScript; no Python SDK) via subprocess, so keys
stay client-side and the agent signs + broadcasts its own BSC txs. Competition
registration is a direct call to the on-chain CompetitionRegistry (TWAK has no
`compete` command — verified against the official docs 2026-06-18).

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
import subprocess

from config.settings import SLIPPAGE_BPS

log = logging.getLogger("conviction.twak")

COMPETITION_CONTRACT = "0x212c61b9b72c95d95bf29cf032f5e5635629aed5"  # CompetitionRegistry (verified, BSC)
TWAK_BIN = os.getenv("TWAK_BIN", "twak")
QUOTE_TOKEN = os.getenv("QUOTE_TOKEN", "USDT")          # base currency we buy/sell against on BSC
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
BSC_CHAIN_ID = 56

# Minimal ABI for the verified CompetitionRegistry contract.
REGISTRY_ABI = [
    {"inputs": [], "name": "register", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}],
     "name": "isRegistered", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
     "stateMutability": "view", "type": "function"},
]

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


def _fmt(amount: float) -> str:
    """Trim float for the CLI: enough precision for token qty, no trailing zeros."""
    return f"{amount:.8f}".rstrip("0").rstrip(".") or "0"


def _run(args: list[str]) -> str:
    """Run a TWAK CLI command, return stdout. Raises on failure (caller decides)."""
    cmd = [TWAK_BIN, *args]
    log.info("twak: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"twak failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


def _agent_account():
    """Load the agent web3 account from TWAK_PRIVATE_KEY (used for on-chain registration)."""
    from web3 import Web3
    pk = os.getenv("TWAK_PRIVATE_KEY")
    if not pk:
        raise RuntimeError("TWAK_PRIVATE_KEY required for on-chain registration")
    w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
    acct = w3.eth.account.from_key(pk)
    return w3, acct


def _require_live_config() -> None:
    if not os.getenv("TWAK_WALLET_ADDRESS") and not os.getenv("TWAK_PRIVATE_KEY"):
        raise RuntimeError("live execution requested but no TWAK wallet configured (.env)")


# --------------------------------------------------------------------------- #
def is_registered() -> bool:
    """True if the agent wallet is already registered on the CompetitionRegistry."""
    if _dry_run():
        return False
    try:
        from web3 import Web3
        w3, acct = _agent_account()
        reg = w3.eth.contract(address=Web3.to_checksum_address(COMPETITION_CONTRACT), abi=REGISTRY_ABI)
        return bool(reg.functions.isRegistered(acct.address).call())
    except Exception as e:
        log.warning("registration status check failed: %s", e)
        return False


def register() -> str:
    """Register the agent wallet on the CompetitionRegistry (idempotent).

    Direct call to register() on 0x212c…aed5 — TWAK has no compete command. Must run
    BEFORE the June 22 window; the contract rejects late entries. Returns tx hash.
    """
    if _dry_run():
        return _sim_hash("register", COMPETITION_CONTRACT)
    _require_live_config()
    from web3 import Web3
    w3, acct = _agent_account()
    reg = w3.eth.contract(address=Web3.to_checksum_address(COMPETITION_CONTRACT), abi=REGISTRY_ABI)
    if reg.functions.isRegistered(acct.address).call():
        log.info("already registered — skipping")
        return ""
    tx = reg.functions.register().build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": BSC_CHAIN_ID,
        "gas": 150_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(txh, timeout=180)
    h = txh.hex()
    log.info("registered on-chain: %s", h)
    return h if h.startswith("0x") else "0x" + h


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

    _require_live_config()
    slippage_pct = SLIPPAGE_BPS / 100  # bps -> percent (100 bps = 1.0)
    frm, to = (QUOTE_TOKEN, symbol) if side == "buy" else (symbol, QUOTE_TOKEN)
    # Verified syntax: twak swap <amount> <from> <to> --chain bsc --slippage <pct> --json
    out = _run(["swap", _fmt(amount), frm, to,
                "--chain", "bsc", "--slippage", f"{slippage_pct}", "--json"])
    try:
        return json.loads(out).get("txHash") or json.loads(out).get("hash") or out
    except Exception:
        return out


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
