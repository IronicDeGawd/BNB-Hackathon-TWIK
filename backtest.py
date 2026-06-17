"""Offline replay harness — build EARLY, use throughout.

Replay a sequence of recorded signal frames through the REAL decision logic
(divergence -> conviction -> risk gate) against a paper ledger priced per frame, so tuning
CONVICTION_THRESHOLD / weights / risk params reflects production behavior. Social history
will be approximate; even rough replay catches logic bugs and bad thresholds before risking
real funds.

A Frame is one cycle: per-token signal objects + a price map. replay() returns summary
stats including max drawdown and whether the run would have been DISQUALIFIED (>= 30%).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import settings
from brain.divergence import detect
from brain.conviction import score
from risk.guardrails import RiskManager


@dataclass
class Frame:
    ts: float
    prices: dict[str, float]                       # symbol -> USD price this cycle
    onchain: dict = field(default_factory=dict)
    twitter: dict = field(default_factory=dict)
    reddit: dict = field(default_factory=dict)
    cmc: dict = field(default_factory=dict)


@dataclass
class BacktestResult:
    n_trades: int
    n_wins: int
    win_rate: float
    total_return_pct: float
    max_drawdown_pct: float
    final_usd: float
    disqualified: bool


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class _Paper:
    """Minimal paper ledger: cash + positions with average cost, valued at frame prices."""
    def __init__(self, cash: float):
        self.cash = cash
        self.pos: dict[str, list[float]] = {}      # symbol -> [tokens, cost_usd]

    def value(self, prices: dict[str, float]) -> float:
        held = sum(toks * prices.get(s, 0.0) for s, (toks, _) in self.pos.items())
        return self.cash + held

    def buy(self, symbol: str, usd: float, price: float) -> None:
        toks = usd / price
        cur = self.pos.get(symbol, [0.0, 0.0])
        self.pos[symbol] = [cur[0] + toks, cur[1] + usd]
        self.cash -= usd

    def held_tokens(self, symbol: str) -> float:
        return self.pos.get(symbol, [0.0, 0.0])[0]

    def sell_all(self, symbol: str, price: float) -> float:
        """Liquidate the position; return realized PnL in USD."""
        toks, cost = self.pos.pop(symbol, [0.0, 0.0])
        if toks <= 0:
            return 0.0
        proceeds = toks * price
        self.cash += proceeds
        return proceeds - cost


def replay(frames: list[Frame], starting_usd: float = 100.0) -> BacktestResult:
    clock = _Clock()
    rm = RiskManager(now_fn=clock)
    paper = _Paper(starting_usd)
    peak = starting_usd
    max_dd = 0.0
    n_trades = n_wins = 0

    for fr in frames:
        clock.t = fr.ts
        value = paper.value(fr.prices)
        rm.update_drawdown(value)
        peak = max(peak, value)
        max_dd = max(max_dd, 0.0 if peak <= 0 else (peak - value) / peak * 100)

        for sym in fr.prices:
            conv = score(detect(sym, fr.twitter.get(sym), fr.reddit.get(sym),
                                fr.onchain.get(sym), fr.cmc.get(sym)))
            price = fr.prices[sym]

            if conv.direction == "exit" and paper.held_tokens(sym) > 0:
                realized = paper.sell_all(sym, price)
                n_trades += 1
                n_wins += realized > 0

            elif conv.direction == "long" and conv.score >= settings.CONVICTION_THRESHOLD:
                size = rm.position_size(conv.score, value)
                ok, _ = rm.allows(sym, size, value)
                if ok and paper.cash >= size > 0:
                    paper.buy(sym, size, price)
                    rm.record_trade(sym)
                    n_trades += 1

    final = paper.value(frames[-1].prices) if frames else starting_usd
    return BacktestResult(
        n_trades=n_trades,
        n_wins=n_wins,
        win_rate=round(n_wins / n_trades, 3) if n_trades else 0.0,
        total_return_pct=round((final - starting_usd) / starting_usd * 100, 2),
        max_drawdown_pct=round(max_dd, 2),
        final_usd=round(final, 2),
        disqualified=max_dd >= settings.DISQUALIFY_DRAWDOWN_PCT,
    )


if __name__ == "__main__":
    from signals.onchain import OnchainSignal
    from signals.twitter import TwitterSignal
    from signals.cmc import CmcSignal

    S = settings.ONCHAIN_STRONG_FLOW_USD * 2
    cmc_ok = {"CAKE": CmcSignal("CAKE", 1e6, 0.0, True)}
    frames = [
        # t0: accumulation (whales in, retail quiet), price 2.00 -> buy
        Frame(0, {"CAKE": 2.00}, {"CAKE": OnchainSignal("CAKE", S, S, 5, "in")},
              {"CAKE": TwitterSignal("CAKE", 40, 0.4)}, {}, cmc_ok),
        # t1: price rallies to 2.60, no new signal
        Frame(3600, {"CAKE": 2.60}, {}, {}, {}, {}),
        # t2: distribution (whales out, retail euphoric) -> exit at 2.60
        Frame(7200, {"CAKE": 2.60}, {"CAKE": OnchainSignal("CAKE", -S, -S, 5, "out")},
              {"CAKE": TwitterSignal("CAKE", 900, 2.7)},
              {"CAKE": __import__("signals.reddit", fromlist=["RedditSignal"]).RedditSignal("CAKE", 0.6, 0.8)},
              cmc_ok),
    ]
    print(replay(frames))
