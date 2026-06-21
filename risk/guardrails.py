"""The disqualifier defense — runs every cycle, unconditionally.

RiskManager holds the cross-cycle state (portfolio peak, cooldowns, daily counts) and
enforces every guardrail before a trade is allowed:

  - Drawdown kill switch : peak-to-current >= MAX_DRAWDOWN_PCT (25%, below the 30% gate)
                           trips the switch — no new entries, manage exits only.
  - Allowlist            : never trade a token outside the eligible list.
  - Position sizing      : cap any single trade at MAX_POSITION_PCT of portfolio.
  - Cooldown             : no re-trade of the same token within COOLDOWN_MINUTES.
  - Daily cap            : reject new entries past MAX_TRADES_PER_DAY (anti-churn / fee drag).
  - Daily-floor nudge    : near day-end, surface a trade if none happened today (qualification).
  - Dust guard           : flag when the portfolio is at/below DUST_FLOOR_USD.

The drawdown check is unconditional even when scoring is uncertain — call
update_drawdown() every cycle. A clock is injectable for testing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from config import settings
from config.tokens import is_eligible


@dataclass
class RiskState:
    portfolio_peak_usd: float
    current_usd: float
    drawdown_pct: float
    kill_switch_tripped: bool


@dataclass
class RiskManager:
    now_fn: Callable[[], float] = time.time      # injectable clock (epoch seconds)
    peak_usd: float = 0.0
    current_usd: float = 0.0
    kill_switch: bool = False
    _last_trade_ts: dict[str, float] = field(default_factory=dict)
    _trades_today: int = 0
    _trades_total: int = 0
    _today: str = ""

    # ------------------------------------------------------------------ #
    def update_drawdown(self, current_usd: float) -> RiskState:
        """Update peak + drawdown and trip the kill switch if breached. Every cycle."""
        self.current_usd = current_usd
        self.peak_usd = max(self.peak_usd, current_usd)
        dd = 0.0 if self.peak_usd <= 0 else (self.peak_usd - current_usd) / self.peak_usd * 100
        if dd >= settings.MAX_DRAWDOWN_PCT:
            self.kill_switch = True               # latch — stays tripped once breached
        return RiskState(self.peak_usd, current_usd, round(dd, 2), self.kill_switch)

    # ------------------------------------------------------------------ #
    def allows(self, symbol: str, size_usd: float,
               portfolio_usd: float | None = None) -> tuple[bool, str]:
        """Master gate for a NEW entry. Returns (allowed, reason)."""
        if self.kill_switch:
            return False, "kill switch tripped (drawdown breached)"
        if not is_eligible(symbol):
            return False, f"{symbol} not on eligible allowlist"
        if size_usd <= 0:
            return False, "trade size is zero"

        self._roll_day()
        if self._trades_today >= settings.MAX_TRADES_PER_DAY:
            return False, (f"daily trade cap reached "
                           f"({self._trades_today}/{settings.MAX_TRADES_PER_DAY})")

        portfolio = portfolio_usd if portfolio_usd is not None else self.current_usd
        if portfolio <= settings.DUST_FLOOR_USD:
            return False, f"portfolio at dust (<= ${settings.DUST_FLOOR_USD})"

        max_size = portfolio * settings.MAX_POSITION_PCT / 100
        if size_usd > max_size + 1e-9:
            return False, (f"size ${size_usd:,.2f} exceeds {settings.MAX_POSITION_PCT}% "
                           f"cap (${max_size:,.2f})")

        last = self._last_trade_ts.get(symbol)
        if last is not None:
            elapsed_min = (self.now_fn() - last) / 60
            if elapsed_min < settings.COOLDOWN_MINUTES:
                return False, (f"{symbol} in cooldown "
                               f"({elapsed_min:.0f}/{settings.COOLDOWN_MINUTES} min)")
        return True, "ok"

    # ------------------------------------------------------------------ #
    def position_size(self, conviction_score: float, portfolio_usd: float) -> float:
        """Size a trade, scaled by conviction, capped at MAX_POSITION_PCT of portfolio."""
        cap = portfolio_usd * settings.MAX_POSITION_PCT / 100
        frac = max(0.0, min(conviction_score / 100, 1.0))
        return round(cap * frac, 2)

    # ------------------------------------------------------------------ #
    def record_trade(self, symbol: str) -> None:
        """Register an executed trade: starts the cooldown and bumps the daily/total counts."""
        self._roll_day()
        self._last_trade_ts[symbol] = self.now_fn()
        self._trades_today += 1
        self._trades_total += 1

    def needs_daily_floor_trade(self) -> bool:
        """True if no trade yet today AND the UTC day is closing — qualification (>=1 trade/day).

        Gated to the final hours (DAILY_FLOOR_HOUR_UTC) so the agent waits for a quality
        setup most of the day and only forces a sub-threshold trade near day-end.
        """
        self._roll_day()
        if self._trades_today >= settings.DAILY_TRADE_FLOOR:
            return False
        hour = datetime.fromtimestamp(self.now_fn(), tz=timezone.utc).hour
        return hour >= settings.DAILY_FLOOR_HOUR_UTC

    def is_dust(self, current_usd: float | None = None) -> bool:
        """True if the portfolio is at/below the dust floor (those hours score 0%)."""
        v = current_usd if current_usd is not None else self.current_usd
        return v <= settings.DUST_FLOOR_USD

    @property
    def trades_total(self) -> int:
        return self._trades_total

    # ------------------------------------------------------------------ #
    def _roll_day(self) -> None:
        """Reset the daily trade counter when the UTC date changes."""
        day = datetime.fromtimestamp(self.now_fn(), tz=timezone.utc).strftime("%Y-%m-%d")
        if day != self._today:
            self._today = day
            self._trades_today = 0
