"""Vantage — main loop.

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
from brain.conviction import score, Conviction
from brain import llm_confirm
from risk.guardrails import RiskManager
from brain.memory import Memory
from execution import twak, notify

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


def portfolio_value(mem: Memory | None = None) -> float:
    """Scored portfolio value in USD = spendable USDT + alt-token positions (mark-to-market).

    Excludes BNB (gas reserve — the leaderboard doesn't count it). Counts each held alt ONCE
    via twak.get_token_value: twak's portfolio listing is inconsistent (sometimes includes
    alt tokens), so summing it AND the held tokens double-counts. This matches the official
    leaderboard value, so drawdown / kill switch / PnL track reality.

    In LIVE mode an empty/zero read is a hard error so the caller skips the cycle.
    """
    bal = twak.get_balance()
    if twak._dry_run():                              # paper: liquid + cost-basis holdings
        held = sum(mem.holdings().values()) if mem is not None else 0.0
        total = (sum(bal.values()) if bal else 0.0) + held
        return total if total > 0 else settings.PAPER_PORTFOLIO_USD
    liquid = bal.get(twak.QUOTE_TOKEN, 0.0)          # spendable stablecoin only (exclude BNB gas)
    held = sum(twak.get_token_value(s) for s in mem.holdings()) if mem is not None else 0.0
    total = liquid + held
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
    _check_exits(rm, actions, mem)               # stop-loss + take-profit before anything else
    below_threshold: list = []                   # sub-threshold longs (preferred floor candidates)
    floor_pool: list = []                        # (momentum, Conviction) — day-end qualification fallback
    held = set(mem.holdings()) if mem is not None else set()
    held_scores: dict = {}                       # held token -> its current conviction (rotation laggard)
    blocked_longs: list = []                     # strong longs we couldn't fund (rotation targets)

    for sym in watchlist:
        div = detect(sym, twitter_map.get(sym), reddit_map.get(sym),
                     onchain_map.get(sym), cmc_map.get(sym))
        conv = score(div)
        if sym in held:
            held_scores[sym] = conv.score

        # positive-momentum, structurally-OK token = last-resort floor candidate (keeps >=1 trade/day)
        if div.cmc_momentum_pct > 0 and div.structural_ok and conv.direction != "exit":
            floor_pool.append((div.cmc_momentum_pct,
                               Conviction(sym, "long", max(conv.score, 1.0),
                                          conv.confidence, conv.rationale_text)))

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
                continue
            act = _try_enter(rm, sym, conv.score, conv.rationale_text, portfolio_usd, mem)
            actions.append(act)
            if not act.executed and "insufficient" in act.reason and sym not in held:
                blocked_longs.append((conv.score, sym))   # strong setup we couldn't fund -> rotate to it
        else:
            below_threshold.append(conv)

    _maybe_rotate(rm, actions, held_scores, blocked_longs, mem)

    _maybe_daily_floor(rm, state, actions, below_threshold, floor_pool, portfolio_usd, mem)
    return actions


def _check_exits(rm: RiskManager, actions: list, mem: Memory | None) -> None:
    """Stop-loss + take-profit on held positions, independent of the distribution signal.

    Exit when market value is down > STOP_LOSS_PCT (cut the bleed) or up > TAKE_PROFIT_PCT
    (bank the gain + free cash). Skipped when a position can't be priced (dry-run / read failure).
    """
    if mem is None:
        return
    for sym, cost in list(mem.holdings().items()):
        cur = twak.get_token_value(sym)
        if cur <= 0 or cost <= 0:
            continue
        pnl = (cur - cost) / cost * 100
        if pnl <= -settings.STOP_LOSS_PCT:
            tag = f"stop-loss {pnl:+.1f}%"
        elif pnl >= settings.TAKE_PROFIT_PCT:
            tag = f"take-profit {pnl:+.1f}%"
        else:
            continue
        log.info("%s %s: value $%.2f vs cost $%.2f", tag, sym, cur, cost)
        act = _try_exit(rm, sym, 0.0, mem)
        actions.append(Action(act.symbol, "exit", act.score, act.size_usd, act.tx_hash,
                              tag + ": " + act.reason, act.executed))


def _try_exit(rm: RiskManager, sym: str, sc: float, mem: Memory | None) -> Action:
    """Close a held position on a distribution signal. Needs memory to size the sell."""
    if mem is None:
        return Action(sym, "exit", sc, 0.0, "", "exit signal; no memory to size holdings", False)
    if not is_eligible(sym):                      # never touch an off-allowlist symbol
        return Action(sym, "exit", sc, 0.0, "", f"{sym} not on allowlist", False)
    held = mem.holding(sym)                       # USD cost basis (for the ledger close)
    if held <= 0:
        return Action(sym, "exit", sc, 0.0, "", "exit signal but no open position", False)
    try:
        tx = twak.execute_trade(sym, "sell", held)   # execute_trade sells the full on-chain balance
    except Exception as e:                        # broadcast failed — do NOT mutate state
        log.warning("exit %s failed: %s", sym, e)
        return Action(sym, "exit", sc, held, "", f"sell failed: {e}", False)
    rm.record_trade(sym)                          # a sell is on-chain activity too — count it
    mem.log_trade(sym, "sell", held, tx, sc)
    return Action(sym, "exit", sc, held, tx, "distribution — closed position", True)


def _try_enter(rm: RiskManager, sym: str, sc: float, rationale: str,
               portfolio_usd: float, mem: Memory | None) -> Action:
    size = rm.position_size(sc, portfolio_usd)
    if not twak._dry_run():                       # cap to spendable cash — can't buy with locked-up tokens
        cash = twak.get_balance().get(twak.QUOTE_TOKEN, 0.0)
        size = min(size, max(0.0, cash - 0.50))   # leave a small buffer
        if size < 1.0:
            return Action(sym, "long", sc, 0.0, "", f"insufficient {twak.QUOTE_TOKEN} (${cash:.2f})", False)
    pos = twak.get_token_value(sym)               # current exposure -> cumulative position cap
    ok, reason = rm.allows(sym, size, portfolio_usd, position_usd=pos)
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


def _maybe_rotate(rm, actions, held_scores, blocked_longs, mem) -> None:
    """Free cash for a strong setup we couldn't fund by selling the weakest holding —
    only when the conviction gap is large (avoids churn). Next cycle buys the stronger setup."""
    if mem is None or not blocked_longs or not held_scores:
        return
    best_score, best_sym = max(blocked_longs)
    weak_sym, weak_score = min(held_scores.items(), key=lambda kv: kv[1])
    if best_score - weak_score < settings.ROTATION_SCORE_GAP:
        return
    log.info("rotate: sell laggard %s (%.0f) to fund %s (%.0f)", weak_sym, weak_score, best_sym, best_score)
    act = _try_exit(rm, weak_sym, 0.0, mem)
    actions.append(Action(act.symbol, "exit", act.score, act.size_usd, act.tx_hash,
                          f"rotate->{best_sym}: " + act.reason, act.executed))


def _maybe_daily_floor(rm, state, actions, below_threshold, floor_pool, portfolio_usd, mem) -> None:
    """Near day-end, guarantee the >=1 trade/day rule. Prefer a sub-threshold long that
    clears DAILY_FLOOR_MIN_SCORE; if there are none, fall back to the best positive-momentum
    eligible token (a small qualifying trade). Tries candidates until one passes the risk gate."""
    already = any(a.executed and a.direction == "long" for a in actions)
    if already or state.kill_switch_tripped or not rm.needs_daily_floor_trade():
        return
    primary = sorted([c for c in below_threshold if c.score >= settings.DAILY_FLOOR_MIN_SCORE],
                     key=lambda c: c.score, reverse=True)
    fallback = [c for _, c in sorted(floor_pool, key=lambda x: x[0], reverse=True)]
    for conv in primary + fallback:               # first that clears the risk gate wins
        act = _try_enter(rm, conv.symbol, conv.score, "daily-floor: " + conv.rationale_text,
                         portfolio_usd, mem)
        actions.append(act)
        if act.executed:
            return


def main() -> None:
    load_dotenv(override=False)                  # load .env (shell/systemd env still wins; can't flip mid-run)
    logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
    mem = Memory()
    rm = RiskManager(mem=mem)                     # restores drawdown peak + kill switch from prior runs
    live = not twak._dry_run()
    heartbeat_every = int(os.getenv("HEARTBEAT_CYCLES", "4"))   # 4 cycles @15m = hourly
    log.info("Vantage up | cycle=%dm | watchlist=%d | dry_run=%s",
             settings.CYCLE_MINUTES, len(WATCHLIST), twak._dry_run())
    notify.send(f"🟢 <b>Vantage up</b>\nmode: {'LIVE' if live else 'paper'} | "
                f"cycle {settings.CYCLE_MINUTES}m | watchlist {len(WATCHLIST)}")
    cycles, last_err = 0, ""
    while True:
        try:
            maps = collect_signals(WATCHLIST, mem=mem)
            pf = portfolio_value(mem)
            actions = run_cycle(rm, WATCHLIST, *maps, pf, mem)
            traded = [a for a in actions if a.executed]
            log.info("cycle done | portfolio=$%.2f | actions=%d | executed=%d",
                     pf, len(actions), len(traded))
            for a in traded:
                log.info("  TRADE %s %s $%.2f %s | %s", a.direction, a.symbol,
                         a.size_usd, a.tx_hash, a.reason)
                emoji = "🟢" if a.direction == "long" else "🔴"
                notify.send(f"{emoji} <b>{a.direction.upper()} {a.symbol}</b> ${a.size_usd:.2f}\n"
                            f"{a.reason}\nhttps://bscscan.com/tx/{a.tx_hash}")
            if mem.get_state("start_usd", 0.0) <= 0:      # persist starting capital once
                mem.set_state("start_usd", pf)
            start = mem.get_state("start_usd", pf) or pf
            pnl = pf - start
            pct = (pnl / start * 100) if start > 0 else 0.0
            dd = ((rm.peak_usd - pf) / rm.peak_usd * 100) if rm.peak_usd > 0 else 0.0
            total_trades = mem.trade_count()
            for a in traded:                              # PnL line on every trade
                sign = "🟢" if pnl >= 0 else "🔴"
                notify.send(f"{sign} <b>PnL ${pnl:+.2f} ({pct:+.1f}%)</b> | portfolio ${pf:.2f} "
                            f"| since start ${start:.2f} | trades: {total_trades}")
                break
            cycles += 1
            if heartbeat_every and cycles % heartbeat_every == 0:
                ks = " | ⛔ kill-switch" if rm.kill_switch else ""
                sign = "🟢" if pnl >= 0 else "🔴"
                notify.send(f"💓 <b>${pf:.2f}</b> | {sign} PnL ${pnl:+.2f} ({pct:+.1f}%) | "
                            f"dd {dd:.1f}% | trades: {total_trades} (today {rm.trades_today}){ks}")
            last_err = ""
        except Exception as e:                   # noqa: BLE001 — loop must never die
            log.exception("cycle failed, continuing: %s", e)
            msg = str(e)[:200]
            if msg != last_err:                   # dedupe repeated errors to avoid TG spam
                notify.send(f"⚠️ <b>cycle error</b>\n{msg}")
                last_err = msg
        time.sleep(settings.CYCLE_MINUTES * 60)


if __name__ == "__main__":
    main()
