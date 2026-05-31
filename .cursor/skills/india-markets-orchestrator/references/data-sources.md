# Data Sources — Stock_Analysis Repo

**Repo root:** `/Users/akulakavyashree/TestNetstock/Stock_Analysis`

## Priority order (never invent data)

1. **Latest pipeline output** — `reports/Enhanced_Stock_Report_*.xlsx` (newest timestamp)
2. **Per-symbol cache** — `data/cache/{SYMBOL}_comprehensive_*.json`
3. **Recommendation history** — `data/recommendation_history.csv` (filter by symbol)
4. **Regime** — `data/last_known_regime.json`
5. **Run analyzer** — only if data is stale or symbol missing:

```bash
python main.py -s SYMBOL --risk-profile aggressive
# or full universe preview:
python3 analyze_top200_stocks_enhanced.py --dry-run --fast
```

## Live feeds (via repo modules)

| Feed | Module | Env vars |
|------|--------|----------|
| Yahoo NSE | yfinance `{SYMBOL}.NS` | — |
| Upstox candles/LTP | `src/upstox_data.py` | `UPSTOX_*`, `UPSTOX_DATA_ENABLED` |
| Zerodha holdings | `src/zerodha_holdings.py` | `KITE_*`, `KITE_USE_HOLDINGS` |
| Groww history | `src/groww_history.py` | `GROWW_*` |

## Macro proxies (in code)

| Proxy | yfinance symbol | Module |
|-------|-----------------|--------|
| Nifty 50 | `^NSEI` | `market_regime_detector.py` |
| Bank Nifty | `^NSEBANK` | regime |
| India VIX | `^INDIAVIX` | regime, crisis |
| USD/INR | `USDINR=X` | `crisis_detector.py` |
| Crude | `BZ=F` | crisis |

## External (research supplement only)

Use when repo cache lacks detail — cite source + date:

- NSE/BSE circulars, SEBI orders
- Company AR/DRHP for IPO desk
- Screener.in for manual fundamental cross-check

## Report sheets by desk

| Desk | Excel sheets |
|------|--------------|
| Fundamental | Complete Data, Undervalued, Valuation Analysis |
| Technical | Trading Levels, Multi-Timeframe Analysis, Breakout Radar |
| Macro | Dashboard (regime), Sector Analysis, Benchmark Comparison |
| Portfolio | Portfolio Allocation, Portfolio Summary, Risk Analysis, Risk Management |
| Quant/scoring | Top Picks, V2 Shadow Comparison, IC Telemetry, Rec Performance |

## HTML dashboard

`Portfolio_Allocation_Dashboard.html` — summarize allocation weights and top actions for user-facing briefs.
