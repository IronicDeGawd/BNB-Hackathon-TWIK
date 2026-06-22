"""Conviction Agent — main loop.

every CYCLE_MINUTES:
    collect signals (onchain, twitter, reddit, cmc)  — each fault-isolated
    update portfolio + drawdown (kill switch runs unconditionally)
    per watchlist token: divergence -> conviction -> risk gate -> execute
    enforce the daily trade floor (qualification)
    log every decision

One failing source never kills the loop. Structured logging throughout — the logs ARE
the demo material. DRY_RUN (default true) means nothing is broadcast.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv

from config import settings
from config.watchlist import WATCHLIST
from config.tokens import is_eligible
from signals import onchain, twitter, reddit, cmc
from brain.divergence import detect
from brain.conviction import score
from brain import llm_confirm
from risk.guardrails import RiskManager
from brain.memory import Memory
from execution import twak

log = logging.getLogger("conviction.agent")


@dataclass
class Action:
    symbol: str
    direction: str          # "long" | "exit" | "none"
    score: float
    size_usd: float
    tx_hash: str
    reason: str
    executed: bool


def _safe(label: str, fn):
    """Run a collector; on ANY failure (including not-yet-built stubs) return {}."""
    try:
        return fn()
    except Exception as e:                       # noqa: BLE001 — fault isolation is the point
        log.warning("signal source '%s' unavailable: %s", label, e)
        return {}


def collect_signals(watchlist, wallets=None, address_map=None, prices=None, mem=None):
    """Gather all four signal axes, each fault-isolated."""
    return (
        _safe("onchain", lambda: onchain.collect(watchlist, address_map, wallets, prices)),
        _safe("twitter", lambda: twitter.collect(watchlist, mem)),
        _safe("reddit", lambda: reddit.collect(watchlist)),
        _safe("cmc", lambda: cmc.collect(watchlist, {})),
    )


def portfolio_value() -> float:
    """Total in-scope holdings in USD. In dry-run, falls back to the paper portfolio.

    In LIVE mode an empty/zero balance read is a hard error so the caller skips the
    cycle — never silently fall back to a fake portfolio, which would hide real drawdown
    from the kill switch and mis-size positions.
    """
    bal = twak.get_balance()
    total = sum(bal.values()) if bal else 0.0
    if twak._dry_run():
        return total if total > 0 else settings.PAPER_PORTFOLIO_USD
    if total <= 0:
        raise RuntimeError("live balance read empty/zero — skipping cycle (no paper fallback)")
    return total


def run_cycle(rm: RiskManager, watchlist, onchain_map, twitter_map, reddit_map,
              cmc_map, portfolio_usd: float, mem: Memory | None = None) -> list[Action]:
    """One decision cycle over the watchlist. Returns the actions taken/considered."""
    state = rm.update_drawdown(portfolio_usd)    # unconditional drawdown check
    if mem is not None:
        mem.log_portfolio(portfolio_usd, state.drawdown_pct)
    actions: list[Action] = []
    below_threshold: list = []                   # daily-floor fallback candidates

    for sym in watchlist:
        div = detect(sym, twitter_map.get(sym), reddit_map.get(sym),
                     onchain_map.get(sym), cmc_map.get(sym))
        conv = score(div)

        if conv.direction == "exit":
            actions.append(_try_exit(rm, sym, conv.score, mem))
            continue

        if conv.direction != "long":
            continue

        if state.kill_switch_tripped:
            actions.append(Action(sym, "long", conv.score, 0.0, "",
                                  "kill switch tripped — no new entries", False))
            continue

        if conv.score >= settings.CONVICTION_THRESHOLD:
            allow, why = llm_confirm.confirm(div, conv, mem, state.drawdown_pct, rm.trades_today)
            if not allow:
                actions.append(Action(sym, "long", conv.score, 0.0, "", f"LLM veto: {why}", False))
            else:
                actions.append(_try_enter(rm, sym, conv.score, conv.rationale_text, portfolio_usd, mem))
        else:
            below_threshold.append(conv)

    _maybe_daily_floor(rm, state, actions, below_threshold, portfolio_usd, mem)
    return actions


def _try_exit(rm: RiskManager, sym: str, sc: float, mem: Memory | None) -> Action:
    """Close a held position on a distribution signal. Needs memory to size the sell."""
    if mem is None:
        return Action(sym, "exit", sc, 0.0, "", "exit signal; no memory to size holdings", False)
    if not is_eligible(sym):                      # never touch an off-allowlist symbol
        return Action(sym, "exit", sc, 0.0, "", f"{sym} not on allowlist", False)
    held = mem.holding(sym)
    if held <= 0:
        return Action(sym, "exit", sc, 0.0, "", "exit signal but no open position", False)
    try:
        tx = twak.execute_trade(sym, "sell", held)
    except Exception as e:                        # broadcast failed — do NOT mutate state
        log.warning("exit %s failed: %s", sym, e)
        return Action(sym, "exit", sc, held, "", f"sell failed: {e}", False)
    rm.record_trade(sym)                          # a sell is on-chain activity too — count it
    mem.log_trade(sym, "sell", held, tx, sc)
    return Action(sym, "exit", sc, held, tx, "distribution — closed position", True)


def _try_enter(rm: RiskManager, sym: str, sc: float, rationale: str,
               portfolio_usd: float, mem: Memory | None) -> Action:
    size = rm.position_size(sc, portfolio_usd)
    ok, reason = rm.allows(sym, size, portfolio_usd)
    if not ok:
        return Action(sym, "long", sc, size, "", reason, False)
    try:
        tx = twak.execute_trade(sym, "buy", size)
    except Exception as e:                        # broadcast failed — do NOT record/count
        log.warning("entry %s failed: %s", sym, e)
        return Action(sym, "long", sc, size, "", f"buy failed: {e}", False)
    rm.record_trade(sym)
    if mem is not None:
        mem.log_trade(sym, "buy", size, tx, sc)
    return Action(sym, "long", sc, size, tx, rationale, True)


def _maybe_daily_floor(rm, state, actions, below_threshold, portfolio_usd, mem) -> None:
    """If nothing traded today and the day is closing, take the best sub-threshold long
    so the >=1 trade/day rule holds — only if the risk gate otherwise passes."""
    already = any(a.executed and a.direction == "long" for a in actions)
    if already or state.kill_switch_tripped or not rm.needs_daily_floor_trade() or not below_threshold:
        return
    best = max(below_threshold, key=lambda c: c.score)
    if best.score < settings.DAILY_FLOOR_MIN_SCORE:   # don't force a junk trade just to qualify
        return
    act = _try_enter(rm, best.symbol, best.score, "daily-floor nudge: " + best.rationale_text,
                     portfolio_usd, mem)
    actions.append(act)


def main() -> None:
    load_dotenv(override=False)                  # load .env (shell/systemd env still wins; can't flip mid-run)
    logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
    mem = Memory()
    rm = RiskManager(mem=mem)                     # restores drawdown peak + kill switch from prior runs
    log.info("Conviction Agent up | cycle=%dm | watchlist=%d | dry_run=%s",
             settings.CYCLE_MINUTES, len(WATCHLIST), twak._dry_run())
    while True:
        try:
            maps = collect_signals(WATCHLIST, mem=mem)
            pf = portfolio_value()
            actions = run_cycle(rm, WATCHLIST, *maps, pf, mem)
            traded = [a for a in actions if a.executed]
            log.info("cycle done | portfolio=$%.2f | actions=%d | executed=%d",
                     pf, len(actions), len(traded))
            for a in traded:
                log.info("  TRADE %s %s $%.2f %s | %s", a.direction, a.symbol,
                         a.size_usd, a.tx_hash, a.reason)
        except Exception as e:                   # noqa: BLE001 — loop must never die
            log.exception("cycle failed, continuing: %s", e)
        time.sleep(settings.CYCLE_MINUTES * 60)


if __name__ == "__main__":
    main()
