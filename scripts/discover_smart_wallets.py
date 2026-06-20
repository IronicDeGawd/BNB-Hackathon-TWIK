#!/usr/bin/env python3
"""Seed SMART_WALLETS by finding recent net-accumulator EOAs on the watchlist tokens.

Heuristic (keyless, via BSC RPC): over a recent block window, pull Transfer logs per
watchlist token, net each address (received - sent), drop contracts (routers, pairs,
the token itself, most CEX infra) via eth_getCode, and rank wallets that quietly
accumulate ACROSS multiple tokens. That's the "smart money quietly buying" signal.

This is a heuristic seed, not Nansen-grade labels — refine with a labeled set later.
Run:  python -m scripts.discover_smart_wallets [--blocks N] [--tokens N] [--top K]
Writes the ranked list to config/smart_wallets.py (SMART_WALLETS).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from signals.onchain import connect, ERC20_TRANSFER_ABI
from config.tokens import address_of
from config.watchlist import WATCHLIST

BURN = {"0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead"}
# Known BSC infra (routers/factories/CEX) — skip without an RPC call.
INFRA = {a.lower() for a in {
    "0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeSwap router v2
    "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",  # PancakeSwap router v3 (smart)
    "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",  # PancakeSwap factory v2
    "0x1b81D678ffb9C0263b24A97847620C99d213eB14",  # PancakeSwap v3 factory
    "0x3C783c21a0383057D128bae431894a5C19F9Cf06",  # Binance hot wallet 6
    "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",  # Binance hot wallet 14
    "0xF977814e90dA44bFA03b6295A0616a897441aceC",  # Binance 8
    "0x0000000000000000000000000000000000001004",  # BSC system
}}
MAX_CODE_CHECKS = 60   # cap eth_getCode calls (RPC-heavy)


def _fetch_all_transfers(w3, contract, from_block, to_block, chunk=500, cap=40000):
    """All Transfer events in [from_block,to_block], chunked; halves range on RPC errors."""
    out = []
    b = from_block
    while b <= to_block and len(out) < cap:
        end = min(b + chunk - 1, to_block)
        try:
            logs = contract.events.Transfer.get_logs(from_block=b, to_block=end)
            out.extend((l["args"]["from"], l["args"]["to"], int(l["args"]["value"])) for l in logs)
            b = end + 1
        except Exception as e:
            if chunk > 1:
                chunk = max(1, chunk // 2)  # response too big / range too wide -> shrink
                continue
            b = end + 1     # give up this slice, move on
    return out


def discover(blocks: int, n_tokens: int, top: int, chunk: int = 500) -> list[str]:
    w3 = connect()
    head = w3.eth.block_number
    frm = max(0, head - blocks)
    print(f"scanning blocks {frm}..{head} ({blocks}) over top {n_tokens} watchlist tokens")

    net_by_addr: dict[str, float] = defaultdict(float)      # token-normalized net (sum of per-token fractions)
    tokens_acc: dict[str, set] = defaultdict(set)           # which tokens each addr accumulated
    seen_addrs: set[str] = set()

    for sym in WATCHLIST[:n_tokens]:
        addr = address_of(sym)
        if not addr:
            print(f"  {sym}: no address, skip"); continue
        c = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=ERC20_TRANSFER_ABI)
        try:
            dec = c.functions.decimals().call()
        except Exception:
            dec = 18
        evs = _fetch_all_transfers(w3, c, frm, head, chunk=chunk)
        scale = 10 ** dec
        per: dict[str, float] = defaultdict(float)
        for f, t, v in evs:
            per[f.lower()] -= v / scale
            per[t.lower()] += v / scale
        # normalize by this token's gross volume so big-cap tokens don't dominate
        gross = sum(abs(x) for x in per.values()) or 1.0
        for a, net in per.items():
            if net > 0:                       # accumulators only
                net_by_addr[a] += net / gross
                tokens_acc[a].add(sym)
            seen_addrs.add(a)
        print(f"  {sym}: {len(evs)} transfers, {sum(1 for x in per.values() if x>0)} accumulators")

    # rank: prefer wallets accumulating across MULTIPLE tokens, then by normalized net
    ranked = sorted(net_by_addr, key=lambda a: (len(tokens_acc[a]), net_by_addr[a]), reverse=True)

    # filter out burn/infra + contracts (routers/pairs/token); keep EOAs.
    smart: list[str] = []
    checks = 0
    for a in ranked:
        if len(smart) >= top or checks >= MAX_CODE_CHECKS:
            break
        if a in BURN or a in INFRA:
            continue
        checks += 1
        try:
            code = w3.eth.get_code(Web3.to_checksum_address(a))
            if code and code not in (b"", b"0x"):
                continue  # has code -> contract, skip
        except Exception:
            continue
        smart.append(Web3.to_checksum_address(a))
    print(f"(get_code checks: {checks})")
    return smart


def write_out(addrs: list[str]) -> None:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "smart_wallets.py")
    body = ('"""Auto-seeded by scripts/discover_smart_wallets.py — recent net-accumulator EOAs.\n'
            'Heuristic seed; review/curate before relying on it for live capital."""\n\n'
            "SMART_WALLETS = [\n" + "".join(f'    "{a}",\n' for a in addrs) + "]\n")
    open(path, "w").write(body)
    print(f"wrote {len(addrs)} wallets -> {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=3000)   # ~40 min at 0.75s blocks
    ap.add_argument("--tokens", type=int, default=6)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--chunk", type=int, default=500)  # getLogs block range; Alchemy free caps at 10
    a = ap.parse_args()
    wallets = discover(a.blocks, a.tokens, a.top, a.chunk)
    print(f"\n=== {len(wallets)} smart-wallet candidates ===")
    for w in wallets:
        print(" ", w)
    if wallets:
        write_out(wallets)
