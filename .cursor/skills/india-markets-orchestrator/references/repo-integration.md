# Stock_Analysis Repo Integration

This desk is tuned for **`/Users/akulakavyashree/TestNetstock/Stock_Analysis`** — an NSE equity pipeline with hybrid v2 scoring, Zerodha/Kite holdings, Excel/HTML reports, and outcome tracking.

## Always load first (repo work)

| Skill | When |
|-------|------|
| `stock-analysis-system` | Any change to scoring, config, analyzer, reports, v2 promotion |
| `post-analysis-audit` | User says **ANALYSE** after a run |
| `turbo-mtf-weekly-trader` | Weekly rebalance, dry-run vs live, Turbo MTF cadence |
| `five-agent-council` | Architecture / system-wide scoring or exit-logic changes |

The india-markets desks add **investment research framing** on top of this pipeline — they do not replace repo contracts.

## Canonical commands

```bash
cd /Users/akulakavyashree/TestNetstock/Stock_Analysis

# Weekly flow (Kite sync → analyze)
python3 scripts/run_analysis.py --dry-run --fast          # preview, no history writes
python3 scripts/run_analysis.py                           # live when committing

# Direct analyzer
python3 analyze_top200_stocks_enhanced.py --dry-run --fast --portfolio-amount 500000 --risk-profile aggressive
python main.py -s RELIANCE --risk-profile aggressive      # single symbol

# Post-run audit
python3 scripts/post_analysis_audit.py

# Backtest (preferred engine)
python3 -m backtest.runner path1
python3 -m backtest.runner path2
```

## Module → desk mapping

| Desk skill | Repo modules | Primary outputs |
|------------|--------------|-----------------|
| `india-markets-fundamental` | `src/enhanced_fundamental_analyzer.py`, v2 components `fundamental_quality`, `growth`, `value` | Cache JSON, Complete Data sheet |
| `india-markets-technical` | `src/technical_analyzer.py`, `enhanced_technical_analyzer.py`, `pattern_recognition.py`, `early_breakout_detector.py` | Trading Levels, Multi-Timeframe sheets |
| `india-markets-macro` | `market_regime_detector.py`, `adaptive_market_strategy.py`, `crisis_detector.py` | Regime in history, `_Metadata` |
| `india-markets-portfolio` | Allocation in `analyze_top200_stocks_enhanced.py`, `recommendation_history.py`, hard-stop/rotation | Portfolio Allocation sheet, `data/recommendation_history.csv` |
| `india-markets-regulatory` | `backtest/costs.py` (Zerodha STT/stamp/GST/STCG/LTCG) | Cost assumptions in backtests |
| Quant / scoring (no separate desk) | `hybrid_scoring_v2.py`, `src/turbo_entry.py`, `src/vmq_strategy.py`, `src/path2_balanced.py`, `src/flow_quality_oracle.py`, `src/breakout_radar.py` | Score, action enum, Top Picks |

**Not implemented in repo** (desk = research-only, no pipeline output): `india-markets-derivatives`, `india-markets-ipo`.

## Data sources (this repo)

| Source | Path / module | Notes |
|--------|---------------|-------|
| yfinance | `{SYMBOL}.NS` via `StockDataBundle` | Default OHLCV + `.info` fundamentals |
| Upstox | `src/upstox_data.py`, `UPSTOX_DATA_ENABLED` | Preferred OHLCV when enabled |
| Zerodha Kite | `src/zerodha_holdings.py`, `scripts/kite_login.py` | Holdings → `Holding/holdings*.csv` or API |
| Groww | `src/groww_history.py`, `data/cache/groww/` | Optional backfill |
| Per-symbol cache | `data/cache/{SYMBOL}_comprehensive_*.json` | Post-run fundamental bundle |
| Regime cache | `data/last_known_regime.json` | BULL/BEAR/SIDEWAYS |
| History | `data/recommendation_history.csv` | Actions, scores, outcomes |
| Latest report | `reports/Enhanced_Stock_Report_*.xlsx` | 23+ sheets |
| HTML dashboard | `Portfolio_Allocation_Dashboard.html` | Root output |
| Sentiment | `sentiment_analyzer.py` | Google News RSS + lexicon |

Do **not** invent prices or scores — read cache, latest Excel, or run analyzer.

## Action & score contract

From `config.py` / `docs/config-contract.md` (live overrides may be in `config.json`):

- Score 0–100; v2 live when `V2_SHADOW_MODE=False`
- Baseline actions: `HOLD`, `SELL`, `INCREASE`, `NEW POSITION`, `WATCHLIST`, `EXIT NOW - Heavy exhaustion`, `HIGH MOMENTUM NEW POSITION`
- Thresholds: STRONG BUY ≥70, BUY ≥60, HOLD ≥50, SELL <40 (verify live config)

## Universe

- Default: `stock_list_template500.csv` (Nifty 500)
- Filter: `src/universe_filter.py` — drops ETFs/InvITs, ADV gate
- Symbols: bare NSE ticker (`RELIANCE`, not `RELIANCE.NS` in CSV)

## Strategy lanes (Turbo MTF primary)

Controlled in `config.py`:

- **Turbo MTF** — `DUAL_STRATEGY_PROFILES['turbo_mtf']`, `src/turbo_entry.py`
- **VMQ** — `src/vmq_strategy.py`
- **Path2 Balanced** — `src/path2_balanced.py`
- **Flow-quality oracle** — `src/flow_quality_oracle.py`, `docs/oracle-recovery-plan.md`
- **Breakout radar** — `src/breakout_radar.py`

When explaining picks, tie narrative to these lanes where the Excel row shows driver/tags.

## When to run pipeline vs narrative-only

| User ask | Do |
|----------|-----|
| "What does the system say about X?" | Read latest report/cache OR `python main.py -s X` |
| "Full desk view on X" | Run single-stock analyze if stale, then multi-desk synthesis |
| "Why did we get SELL on X?" | Read history + report row; map to v2 components |
| "Change hard-stop logic" | `five-agent-council` + `stock-analysis-system`, not india-markets desks |
| "Weekly plan" | `turbo-mtf-weekly-trader` + orchestrator portfolio/macro desks |
