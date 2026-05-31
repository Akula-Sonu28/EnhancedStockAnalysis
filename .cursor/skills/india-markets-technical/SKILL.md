---
name: india-markets-technical
description: >-
  Technical analysis desk for Stock_Analysis NSE pipeline. Uses
  technical_analyzer, enhanced_technical_analyzer, pattern_recognition,
  early_breakout_detector, turbo_entry MTF gates, and Trading Levels /
  Multi-Timeframe / Breakout Radar Excel sheets. Use for chart bias, support
  resistance, exhaustion exits, or explaining momentum_technical and
  multi_timeframe v2 components.
---

# Technical Desk — Stock_Analysis

## Repo modules

| Module | Role |
|--------|------|
| `src/technical_analyzer.py` | RSI, MACD, SMA/EMA, BB, ADX, ATR; `get_ohlcv` |
| `enhanced_technical_analyzer.py` | Short-term overlay |
| `pattern_recognition.py` | Chart patterns |
| `early_breakout_detector.py` | Pre-breakout; RSI exhaustion → `EXIT NOW - Heavy exhaustion` |
| `src/turbo_entry.py` | Turbo MTF entry (daily/weekly/monthly + 3d confirm) |
| `src/breakout_radar.py` | Breakout fast-track picks |

OHLCV priority: Upstox (`UPSTOX_DATA_ENABLED`) → yfinance `{SYMBOL}.NS`.

## Read data

1. Excel **Trading Levels**, **Multi-Timeframe Analysis**, **Breakout Radar**
2. Cache JSON technical fields
3. v2 components: `momentum_technical`, `multi_timeframe`, `volume_strength`

## Turbo MTF context

Primary strategy profile: `DUAL_STRATEGY_PROFILES['turbo_mtf']` — weights MTF 35%, momentum 25%. Tie technical narrative to 15–30 day hold unless user specifies otherwise.

Exhaustion tiers (from `early_breakout_detector`): RSI 72/76/82 → scale-out / trail / book.

## Report template

```markdown
# [SYMBOL] — Technical Memo

**Pipeline MTF/momentum:** | **Action:** | **Regime:**

## Levels (from Trading Levels sheet or computed)
| Level | Type | Source |
|-------|------|--------|

## Setup
- Bias / Trigger / Invalidation / Targets

## Strategy lane
[Turbo / VMQ / Path2 / Breakout — from report tags if present]

## Pipeline alignment
[Technical supports or conflicts with action]
```

## Hand off

- Fundamentals → `india-markets-fundamental`
- Regime → `india-markets-macro`
- Stops / rotation → `india-markets-portfolio`
