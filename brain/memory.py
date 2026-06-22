"""SQLite state across 15-min wakes — signal history, trades, portfolio, holdings.

This is what makes the agent stateful between cycles: velocity/flow baselines and current
holdings are read back from here.

Tables:
  signals(ts, symbol, source, metric, value)
  trades(ts, symbol, side, size_usd, tx_hash, conviction)
  portfolio(ts, total_usd, drawdown_pct)

Holdings are derived from the trades table (buys add, sells subtract), so there is one
source of truth. A clock is injectable for testing; pass db_path=":memory:" in tests.
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Callable

DB_PATH = "data/conviction.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    ts REAL, symbol TEXT, source TEXT, metric TEXT, value REAL
);
CREATE INDEX IF NOT EXISTS ix_signals ON signals(symbol, source, metric, ts);
CREATE TABLE IF NOT EXISTS trades (
    ts REAL, symbol TEXT, side TEXT, size_usd REAL, tx_hash TEXT, conviction REAL
);
CREATE INDEX IF NOT EXISTS ix_trades ON trades(symbol, ts);
CREATE TABLE IF NOT EXISTS portfolio (
    ts REAL, total_usd REAL, drawdown_pct REAL
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY, value REAL
);
"""


class Memory:
    def __init__(self, db_path: str = DB_PATH, now_fn: Callable[[], float] = time.time):
        self.now_fn = now_fn
        if db_path not in (":memory:", "") and os.path.dirname(db_path):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # -- writes ----------------------------------------------------------- #
    def log_signal(self, symbol: str, source: str, metric: str, value: float,
                   ts: float | None = None) -> None:
        self.conn.execute("INSERT INTO signals VALUES (?,?,?,?,?)",
                          (ts if ts is not None else self.now_fn(), symbol, source, metric, value))
        self.conn.commit()

    def log_trade(self, symbol: str, side: str, size_usd: float, tx_hash: str,
                  conviction: float, ts: float | None = None) -> None:
        if side not in ("buy", "sell"):
            raise ValueError(f"bad side: {side}")
        self.conn.execute("INSERT INTO trades VALUES (?,?,?,?,?,?)",
                          (ts if ts is not None else self.now_fn(), symbol, side,
                           size_usd, tx_hash, conviction))
        self.conn.commit()

    def log_portfolio(self, total_usd: float, drawdown_pct: float,
                      ts: float | None = None) -> None:
        self.conn.execute("INSERT INTO portfolio VALUES (?,?,?)",
                          (ts if ts is not None else self.now_fn(), total_usd, drawdown_pct))
        self.conn.commit()

    # -- reads ------------------------------------------------------------ #
    def baseline(self, symbol: str, source: str, metric: str, hours: int,
                 now: float | None = None) -> float:
        """Rolling average of a metric over the trailing `hours` (0.0 if no data)."""
        cutoff = (now if now is not None else self.now_fn()) - hours * 3600
        row = self.conn.execute(
            "SELECT AVG(value) FROM signals WHERE symbol=? AND source=? AND metric=? AND ts>=?",
            (symbol, source, metric, cutoff)).fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    def holding(self, symbol: str) -> float:
        """Current position size in USD (buys - sells), floored at 0."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN side='buy' THEN size_usd ELSE -size_usd END),0) "
            "FROM trades WHERE symbol=?", (symbol,)).fetchone()
        return max(0.0, float(row[0]))

    def holdings(self) -> dict[str, float]:
        """All non-zero positions {symbol: size_usd}."""
        rows = self.conn.execute(
            "SELECT symbol, SUM(CASE WHEN side='buy' THEN size_usd ELSE -size_usd END) "
            "FROM trades GROUP BY symbol").fetchall()
        return {s: float(v) for s, v in rows if v and v > 0}

    def trade_count(self) -> int:
        """Total trades ever executed (persists across restarts — for PnL/activity reporting)."""
        return int(self.conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0])

    def recent_trades(self, symbol: str, limit: int = 5) -> list[dict]:
        """Most recent trades for a token (newest first) — context for the LLM confirm layer."""
        rows = self.conn.execute(
            "SELECT ts, side, size_usd, conviction FROM trades WHERE symbol=? "
            "ORDER BY ts DESC LIMIT ?", (symbol, limit)).fetchall()
        return [{"ts": r[0], "side": r[1], "size_usd": r[2], "conviction": r[3]} for r in rows]

    def recent_signals(self, symbol: str, source: str, metric: str, limit: int = 5) -> list[float]:
        """Most recent raw signal values for a token/source/metric (newest first)."""
        rows = self.conn.execute(
            "SELECT value FROM signals WHERE symbol=? AND source=? AND metric=? "
            "ORDER BY ts DESC LIMIT ?", (symbol, source, metric, limit)).fetchall()
        return [float(r[0]) for r in rows]

    # -- durable scalar state (survives restarts) ------------------------- #
    def get_state(self, key: str, default: float = 0.0) -> float:
        """Read a persisted scalar (e.g. drawdown peak, kill-switch flag)."""
        row = self.conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return float(row[0]) if row else default

    def set_state(self, key: str, value: float) -> None:
        """Persist a scalar; upsert keyed by name."""
        self.conn.execute(
            "INSERT INTO state(key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, float(value)))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
