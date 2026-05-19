"""Self-contained backtest engine for the v2 scoring model.

Two run modes:
    Path 1 (high-fidelity, ~95% accurate, dense window only):
        Use existing hybrid_* component data from data/historical_outcomes.csv
        over 2026-03-17 -> 2026-05-07. No re-scoring needed.

    Path 2 (medium-fidelity, ~75-80% accurate, 6 months):
        Re-score every (date, symbol) from raw OHLCV; use PIT fundamentals
        from data/recommendation_history.csv where available (last 50 days),
        fall back to yfinance current TTM for older dates (documented lookahead).

Both modes share the same engine (event loop, portfolio, costs, execution,
strategy, reports). Only the data layer differs.

Entry point: backtest.runner:main (or `python -m backtest.runner`).
"""

__version__ = '0.1.0'
