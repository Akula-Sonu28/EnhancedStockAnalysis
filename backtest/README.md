# backtest/ — High-fidelity v2 scoring model stress-test

Self-contained backtest engine that imports the production scoring (`hybrid_scoring_v2`) and action lifecycle (`_evaluate_hard_stop`, rotation, trailing, scale-out) directly — so backtest results cannot drift from production behaviour.

## Why a new engine

The existing scripts (`backtest_engine.py`, `scripts/monthly_rebalance_backtest.py`, `scripts/six_month_return_check.py`) all have one of the following issues:

- Use v1 only, not v2 (`backtest_engine.py`)
- Lookahead on fundamentals (yfinance TTM applied to past dates)
- No per-trade simulation — aggregate `mean(return_30d)` of picks, no T+1 fills, no within-window stops
- No action-lifecycle replay (production has 8 modifiers; old scripts apply zero)
- No Indian cost model in the v2 path
- Equal-weight buckets, no sector caps, no concentration limits
- No per-trade ledger

This engine fixes those. See `../docs/dev-log.md` (or chat history) for the full audit.

## Two run modes

| Mode | Accuracy ceiling | Window | Data source | Build |
|---|---|---|---|---|
| `path1` | **~95%** | 2026-03-17 → 2026-05-07 (~7 weeks) | Dense `hybrid_*` rows from `data/historical_outcomes.csv` | Recommended first run |
| `path2` | ~75-80% | trailing 6 months | Re-score from OHLCV + PIT fundamentals where available | Documents fundamentals lookahead in output |

## Quick start

```bash
# Path 1: high-fidelity 7-week stress test, ₹1L starting capital, top-10
python3 -m backtest.runner path1 --capital 100000 --top-n 10 --rebalance weekly

# Path 2: medium-fidelity 6-month re-scoring backtest
python3 -m backtest.runner path2 --capital 100000 --top-n 10 --months 6 --rebalance weekly

# QMST stack: fq pick (top 20%) + turbo entry + VMQ exits (path1 window)
python3 -m backtest.runner qmst --capital 100000 --top-n 10 --rebalance weekly

# QMST trailing 3 months (OHLCV rescore) with day-3/5 VMQ validation
python3 -m backtest.runner qmst --months 3 --capital 100000 --top-n 10 --rebalance weekly

# Head-to-head v1 vs v2 (Path 1 only — Path 2 v1 needs PIT fundamentals)
python3 -m backtest.runner path1 --engine v1 --capital 100000 --top-n 10
python3 -m backtest.runner path1 --engine v2 --capital 100000 --top-n 10

# Run tests
python3 -m pytest backtest/tests/ -v

# LowVol→Mom (Nifty 200, monthly, production ranker)
python3 -m backtest.runner lvm --months 24 --capital 1000000 --monthly-injection 100000
python3 -m backtest.runner lvm --months 12 --compare-stops --monthly-injection 100000

# Quality + LowVol→Mom (PIT Screener fundamentals) and head-to-head vs baseline
python3 -m backtest.runner quality-lvm --months 24 --capital 1000000 --stop-pct 10
python3 -m backtest.runner compare-lvm --months 120 --capital 1000000 --stop-pct 10

# Cooldown policy grid (Path 1, compares off / prod_3d|5d|7d / profit-bypass variants)
python3 scripts/backtest_cooldown_comparison.py --rebalance weekly --top-n 10

# Single run with cooldown (default off for backward compatibility)
python3 -m backtest.runner path1 --cooldown prod_5d --capital 100000 --top-n 10
```

Results land in `backtest/results/<run_id>/`:
- `summary.json` — headline metrics
- `trades.csv` — per-trade ledger
- `equity.csv` — daily equity curve + drawdown
- `report.xlsx` — single-file Excel with all sheets

## Architecture

```
backtest/
├── __init__.py
├── runner.py              # CLI entry point
├── engine.py              # Event loop (daily)
├── strategy.py            # Score -> action (imports production logic)
├── execution.py           # Fill model (T+1 next-day open)
├── costs.py               # Zerodha + STT + GST + stamp duty + LTCG/STCG
├── portfolio.py           # Cash, positions, weights, sector caps
├── metrics.py             # Sharpe, Sortino, Calmar, MaxDD, turnover
├── data/
│   ├── universe.py        # Eligible symbols per date
│   ├── prices.py          # OHLCV cache + adjusted close (yfinance backed)
│   ├── fundamentals.py    # PIT from recommendation_history (Path 2)
│   ├── regime.py          # Historical regime replay
│   └── path1_loader.py    # Dense-window v2 scores from historical_outcomes.csv
├── reports/
│   ├── trade_ledger.py
│   ├── equity_curve.py
│   └── excel_writer.py
├── tests/
│   ├── test_costs.py
│   ├── test_execution.py
│   ├── test_lookahead_guard.py
│   └── test_replay_deterministic.py
└── README.md
```

## Honest accuracy notes

### What's replayed accurately (≥95%)

- v2 score logic (we read or re-compute from production formulas)
- v2 walk-forward weight calibration (no lookahead)
- Action lifecycle: hard-stops, trailing, scale-out, rotation, hysteresis, score smoothing
- Indian cost model (Zerodha Equity Delivery): brokerage, STT, exchange, SEBI, stamp duty, GST
- Capital gains: STCG 20%, LTCG 10% above ₹1L (post-Budget-2024 rates, effective 2024-07-23)

### Known limits (un-fixable without paid feeds)

1. **Point-in-time fundamentals before 2026-03-24** — yfinance returns current TTM. Path 2 falls back to current TTM for the older 4 months and tags those scores `lookahead=True` in the trade ledger.
2. **Bid-ask spread / true fills** — yfinance is daily close only. We use next-day open + configurable slippage (default 15bps for large-caps, 25bps for mid/small).
3. **Survivorship bias** — universe = today's `nifty200_stocks.csv`. Companies that delisted/merged are absent. Net effect: results biased ~1-3%/yr upward. Path 1 (7 weeks) is essentially unaffected.
4. **Historical sentiment** — set to neutral (suppressed) in backtest.
5. **ML signal** — set to neutral 50 in backtest (running today's model on past dates = lookahead).

### What's deliberately not modelled

- Intraday volatility (we're a delivery-trading system, not intraday)
- Block-trade impact (small ₹1L portfolio doesn't move markets)
- Options / derivatives (not in scope of scoring model)
