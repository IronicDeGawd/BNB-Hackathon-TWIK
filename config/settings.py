"""Single source of truth for all tunable parameters.

Thresholds and risk params live here ONLY. Modules import from this file —
never hardcode a number that belongs here. Tune via backtest.py before going live.
"""

# --- Cadence ---
CYCLE_MINUTES = 15                 # 96 cycles/day
TWITTER_CALLS_PER_CYCLE = 10       # batched; keeps under the daily budget

# --- Conviction ---
CONVICTION_THRESHOLD = 65          # min 0-100 score to trigger a trade

# --- Risk (the disqualifier defense) ---
MAX_DRAWDOWN_PCT = 25              # internal kill-switch cap, BELOW the 30% disqualifier
MAX_POSITION_PCT = 40             # max % of portfolio per trade (raised for ~$20 size: fewer, bigger trades beat fee drag)
SLIPPAGE_BPS = 100               # 1% max slippage
COOLDOWN_MINUTES = 60            # no re-trade of same token within this window
DUST_FLOOR_USD = 1.0             # never let portfolio sit at or below this (those hours score 0%)

# --- Stop-loss (risk-off on held positions, independent of the distribution signal) ---
STOP_LOSS_PCT = 8                 # exit a held token once its market value is down this % from entry cost

# --- Qualification rules ---
DAILY_TRADE_FLOOR = 1             # must trade at least once/day
DAILY_FLOOR_HOUR_UTC = 1          # force the daily qualifying trade early in the UTC day (lock scoring)
DAILY_FLOOR_MIN_SCORE = 40        # never force a daily-floor trade below this conviction (skip junk)
WEEKLY_TRADE_FLOOR = 7           # must trade at least 7x over the week
MAX_TRADES_PER_DAY = 6           # hard cap on new entries/day (anti-churn; fee drag bites at small size)
DISQUALIFY_DRAWDOWN_PCT = 30      # hard gate from hackathon rules (do not breach)

# --- Budgets ---
TWITTER_DAILY_BUDGET = 1000       # hard stop; degrade gracefully when hit
CAPITAL_AT_RISK_USD = 20          # ceiling on capital exposed (funding ~$20, not $100)
PAPER_PORTFOLIO_USD = 20.0        # assumed portfolio value in DRY_RUN when balances are empty

# --- Signal windows ---
ONCHAIN_FLOW_WINDOW_HOURS = 1     # trailing window for smart-money net flow (small enough for public dataseed getLogs)
SOCIAL_BASELINE_HOURS = 24        # rolling baseline for mention-velocity ratio
REDDIT_EVERY_N_CYCLES = 2         # poll Reddit less often (fallback-quality source)

# --- Conviction scorer weights (rules-based core; must sum ~1.0) ---
# Decision is deterministic. LLM is used ONLY to write rationale_text.
WEIGHT_CMC_MOMENTUM = 0.50        # primary — CMC price/volume momentum (the intended data source)
WEIGHT_SOCIAL_VELOCITY = 0.25
WEIGHT_SOCIAL_AGREEMENT = 0.15    # Twitter + Reddit pointing the same way
WEIGHT_CMC_STRUCTURAL = 0.10      # structural OK (veto handled separately)
WEIGHT_ONCHAIN_BONUS = 0.10       # optional smart-money wallet flow, ADDED only if a keyed RPC feeds it

# --- CMC structural veto (tune via backtest.py) ---
CMC_MIN_LIQUIDITY_USD = 250_000.0   # 24h volume floor; below this = thin -> veto (slippage risk)
CMC_MAX_FUNDING_ABS = 0.05         # |funding rate| above this, against intended direction -> veto

# --- Divergence thresholds (brain; tune via backtest.py) ---
CMC_MOMENTUM_STRONG_PCT = 0.4     # |1h % price change| at/above = strong directional (primary axis)
ONCHAIN_STRONG_FLOW_USD = 5000    # |net smart-money flow| considered strong (bonus axis, if RPC feeds it)
SOCIAL_VEL_HOT = 2.0              # mention velocity at/above this = retail euphoric
SOCIAL_VEL_FLAT = 1.2            # velocity at/below this = retail asleep (good for accumulation)
REDDIT_HOT_ACTIVITY = 0.5       # normalized reddit activity at/above this = social agreement
REDDIT_ACTIVITY_NORM_POSTS = 10  # post count that maps to activity = 1.0

# Runtime DRY_RUN is read from the environment at execution time (execution/twak.py),
# defaulting to simulate. There is no module-level flag — env is the single source.
