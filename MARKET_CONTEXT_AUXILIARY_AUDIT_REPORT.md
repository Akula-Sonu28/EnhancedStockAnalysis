# Market Context & Auxiliary Modules — Final Line-by-Line Audit Report

**Date:** March 13, 2026  
**Scope:** market_regime_detector.py, crisis_detector.py, adaptive_market_strategy.py, early_breakout_detector.py, recommendation_history.py  
**Goal:** (A) Find every remaining bug/gap, (B) Identify concrete upgrades for bear-market scoring accuracy

---

## Executive Summary

The scoring system fails in bear markets due to **three critical integration issues**:
1. **Regime key mismatch**: `MarketRegimeDetector` returns `BULL`/`BEAR`/`SIDEWAYS`, but `AdaptiveMarketRegimeStrategy` expects `BULL_MODERATE`/`BEAR_MODERATE` — lookups silently fall back to wrong regime (CALM/SIDEWAYS).
2. **Breadth signal broken**: Uses Nifty high/low touch counts instead of true advance-decline; often returns 0 or near-binary values.
3. **Adaptive weights never applied**: `get_adaptive_scoring_weights()` exists but is never called — hybrid scorer uses its own `_REGIME_WEIGHTS` with different keys.

---

## FILE 1: market_regime_detector.py

### 1.1 `detect_regime()` — Nifty fetch failure handling

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 41-45 | GAP | MEDIUM | `_get_index_data()` returns `None` on yfinance failure; `len(nifty_data) < 50` triggers default regime. No retry, no cache, no fallback index. | Single fetch failure → entire run uses UNKNOWN regime; bear detection lost. | Add retry (2–3 attempts), optional fallback to Bank Nifty (`^NSEBANK`) if Nifty fails. |
| 98-100 | BUG | LOW | `_get_default_regime()` returns `current_nifty: 0.0` — downstream may divide by zero or treat as valid. | Minor; most consumers check regime string. | Use `None` or omit `current_nifty` when unavailable. |

### 1.2 `_calculate_trend_signal()` — SMA logic

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 132 | GAP | LOW | `ma_200` uses `ma_100` when `len(close) < 200` — effectively comparing MA-100 to itself, always neutral. | Long-term trend component always -0.25 in short histories. | Use shorter MA (e.g. MA-100 vs MA-50) when data < 200 days. |
| 156-161 | GAP | LOW | MA crossover not explicitly detected; only current price vs MA. No golden/death cross logic. | Misses regime transitions (e.g. death cross in bear). | Add MA-50 vs MA-200 crossover as additional signal. |

### 1.3 `_calculate_momentum_signal()` — RSI division by zero

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 199-201 | BUG | HIGH | `rs = gain / loss` — when `loss == 0` (all gains in 14 days), `rs` = inf; when both 0, NaN. `rsi.iloc[-1]` can be NaN. | NaN propagates → regime_score corrupted → regime misclassified. | Add: `rs = gain / loss if loss != 0 else (float('inf') if gain > 0 else 0)`; handle NaN: `current_rsi = 50 if np.isnan(rsi.iloc[-1]) else rsi.iloc[-1]`. |
| 205 | BUG | MEDIUM | `close.iloc[-20]` — if `len(close) < 20`, IndexError. | Crashes on short histories. | Add: `roc_20 = ... if len(close) >= 20 else 0`. |

### 1.4 `_calculate_breadth_signal()` — BROKEN (known)

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 213-242 | BUG | **CRITICAL** | Uses Nifty single-index high/low touch counts. Not advance-decline. Counts "bars touching recent high" vs "bars touching recent low". In many cases new_highs≈new_lows → breadth_ratio≈0. | 20% weight on broken signal; bear markets under-detected when breadth would show deterioration. | **UPGRADE**: Fetch NSE advance-decline ratio (or Nifty 500 vs Nifty 50 relative strength) from free source; or use Nifty Midcap 100 vs Nifty 50 ratio as breadth proxy. |
| 225 | GAP | MEDIUM | `lookback = min(20, len(df) - 1)` — when `len(df)==21`, lookback=20; when `len(df)==20`, lookback=19. Edge case. | Minor. | Use `min(20, max(1, len(df)-1))`. |

### 1.5 `_calculate_volatility_signal()` — VIX interpretation

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 165-186 | GAP | MEDIUM | Uses 20-day historical vol from Nifty returns; VIX fetched separately in `_get_vix_level()` but not used in volatility_signal. Vol signal and VIX are independent. | VIX spike (e.g. 25→35) not reflected in volatility_signal until Nifty returns catch up. | **UPGRADE**: Blend India VIX level into volatility_signal (e.g. VIX>25 → -0.5, VIX>30 → -1.0). |
| 176 | GAP | LOW | `avg_vol = volatility.mean()` — includes NaN from initial rolling window. | Slight bias. | Use `volatility.dropna().mean()`. |

### 1.6 `adjust_stock_score_by_regime()` — adjustment logic

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 363-354 | GAP | MEDIUM | No `regime_confidence` gating — adjustment applied at full magnitude even when confidence is low. | Low-confidence regime (e.g. SIDEWAYS with score 0.1) still applies ±10 pts. | Scale adjustment by `regime_data.get('regime_confidence', 0.5)`. |
| 387-398 | GAP | LOW | BULL adjustments: growth +5, high beta +3, momentum +2. No cap on combined BULL bonuses. | Can over-reward in weak bull. | Already clipped ±10 at line 343; OK. |
| 404-421 | GAP | MEDIUM | BEAR: oversold (RSI<30) +3, overbought (RSI>70) -5. But RSI 30–70 band gets no BEAR-specific treatment. | Mid-RSI stocks in bear get only value/low-beta boost; momentum penalty only at RSI>70. | Consider RSI 50–70 mild penalty in BEAR. |

### 1.7 Regime score aggregation

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 55-59 | GAP | MEDIUM | Fixed weights: trend 35%, momentum 25%, volatility 20%, breadth 20%. VIX not in formula. | High VIX (panic) doesn't override trend in regime_score. | **UPGRADE**: When VIX>25, increase volatility weight to 35%, reduce trend to 25%. |
| 62-70 | GAP | LOW | `regime_strength` uses 0.8/-0.8 thresholds; STRONG vs MODERATE binary. | Fine for now. | Optional: add WEAK for 0.5–0.6 / -0.5–-0.6. |

### 1.8 Fallback/error paths

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 252-254 | GAP | LOW | Bare `except: pass` in `_get_vix_level()` — swallows all errors. | Hard to debug VIX fetch failures. | Use `except Exception as e: self.logger.debug(f"VIX fetch failed: {e}")`. |

---

## FILE 2: crisis_detector.py

### 2.1 `detect()` — cross-asset signal analysis

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 334-348 | GAP | LOW | `_classify_event()` uses strict thresholds (crude>3, gold>1, usdinr>0.3). No hysteresis — small noise can flip NONE↔crisis. | Possible flip-flop on borderline days. | Add hysteresis: require 2 consecutive days above threshold. |
| 352-354 | GAP | MEDIUM | US_MARKET_CRISIS: `sp500 < -2.0 and nifty < -1.5 and crude < 2.0`. Nifty must drop; if Nifty lags (e.g. timezone), may miss. | US-led crash detected late. | Consider SP500 alone if drop >3%. |

### 2.2 Crisis type detections

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 384-386 | GAP | LOW | Priority order: WAR → OIL → US → CURRENCY → PANIC. First match wins. WAR and OIL can overlap. | If both crude+gold spike and crude alone, WAR wins. Correct. | OK. |

### 2.3 `get_stock_crisis_adjustment()` — sector matching, symbol overrides

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 56 | BUG | **CRITICAL** | `OIL_UPSTREAM_SYMBOLS = {'ONGC', 'OIL', 'CAIRN', 'GIPCL'}`. **CAIRN** renamed to **VEDL** (Vedanta) in 2011. **GIPCL** is Gujarat Industries Power (power/coal), not oil. | CAIRN lookup never matches; GIPCL wrongly gets +8 in OIL_SHOCK. | Replace CAIRN→VEDL; remove GIPCL from OIL_UPSTREAM. |
| 318-319 | BUG | MEDIUM | Defence override returns early with `return round(10.0 * scale, 1)` — does not `return` for oil upstream. Code falls through. Actually it does `return` — re-read. Defence returns. Then oil check. But oil check uses `if` not `elif` — so both can apply? No: defence returns. Oil is separate `if`. OK. | — | — |
| 318-319 | GAP | LOW | Defence symbols return +10*scale immediately; sector rules never checked. Correct. | — | OK. |

### 2.4 Severity scaling

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 296-298 | GAP | LOW | scale = severity/3. Severity 1→33%, 2→67%, 3→100%. Linear. | OK. | Optional: use sqrt(severity/3) for milder scaling. |

### 2.5 Data freshness

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 336-348 | GAP | MEDIUM | Uses `period='5d'` for assets; 1-day change. yfinance can be 15–20 min delayed. | Intraday crises (e.g. flash crash) detected with delay. | **UPGRADE**: Document delay; consider NSE/BSE real-time if available. |

---

## FILE 3: adaptive_market_strategy.py

### 3.1 Regime key mapping — CRITICAL MISMATCH

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 19-52, 87-113 | BUG | **CRITICAL** | `market_performance` and `position_sizing` use keys: `BULL_MODERATE`, `BEAR_MODERATE`, `SIDEWAYS`, `CALM`. `MarketRegimeDetector` returns `BULL`, `BEAR`, `SIDEWAYS`. **No mapping.** | When regime=BULL, `get_position_sizing_strategy('BULL')` returns CALM (fallback). Bear regime gets CALM position sizing (90% invested) instead of BEAR (60%). | **Add mapping**: `regime_map = {'BULL':'BULL_MODERATE','BEAR':'BEAR_MODERATE','SIDEWAYS':'SIDEWAYS'}`; use `regime_map.get(regime, 'CALM')` before lookup. |
| 2238-2243 | BUG | **CRITICAL** | `analyze_top200_stocks_enhanced.py` passes `regime_key = self.current_market_regime.upper()` (BULL/BEAR/SIDEWAYS) directly. `position_size = self.adaptive_strategy.get_position_sizing_strategy(regime_key)` → BULL/BEAR fall back to CALM. | **All BULL and BEAR regimes use CALM strategy.** Bear-market defensive sizing never applied. | Fix in analyzer: map BULL→BULL_MODERATE, BEAR→BEAR_MODERATE before calling adaptive_strategy. |

### 3.2 `detect_current_market_regime()` — used or bypassed?

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 115-160 | GAP | HIGH | `detect_current_market_regime()` uses 2-month Nifty, returns BULL_MODERATE/BEAR_MODERATE/SIDEWAYS/CALM. **Never called by main analyzer.** Main analyzer uses `MarketRegimeDetector.detect_regime()` which returns BULL/BEAR/SIDEWAYS. | Adaptive strategy's own detection (with correct keys) is unused. Duplicate logic. | Either: (a) Use `AdaptiveMarketRegimeStrategy.detect_current_market_regime()` and pass its result to position sizing, or (b) Map MarketRegimeDetector output to adaptive keys. |
| 139-146 | GAP | MEDIUM | Uses `period="2mo"` — shorter than regime detector's 180 days. Different lookbacks → different regimes. | Inconsistency if both used. | Align lookback or use single source of truth. |

### 3.3 `get_adaptive_scoring_weights()` — applied anywhere?

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 185-187 | BUG | **CRITICAL** | `get_adaptive_scoring_weights(current_regime)` returns regime-specific weights (e.g. BEAR_MODERATE: fundamental 60%, momentum 10%). **Never called.** `hybrid_optimized_scoring.py` uses its own `_REGIME_WEIGHTS` with bullish/bearish/neutral. | Adaptive strategy's backtest-optimized weights are never used. Scoring uses different weights. | **Integrate**: Have hybrid scorer call `adaptive_strategy.get_adaptive_scoring_weights(mapped_regime)` when regime is BULL/BEAR; map keys first. |
| 56-84 | GAP | HIGH | adaptive_weights has BULL_MODERATE, BEAR_MODERATE, etc. hybrid has bullish, bearish, neutral. Keys don't align. | Double mismatch. | Unify key space. |

### 3.4 `get_position_sizing_strategy()` — logic and defaults

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 191-193 | GAP | LOW | Returns dict with max_position, portfolio_exposure, etc. Fallback to CALM when key missing. | OK once mapping fixed. | — |

### 3.5 `generate_regime_specific_recommendations()` — KeyError risk

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 195-196 | BUG | HIGH | `regime_data = self.market_performance[current_regime]` — if `current_regime` is 'BULL' or 'BEAR', **KeyError**. | Crashes if caller passes unmapped regime. | Add: `current_regime = {'BULL':'BULL_MODERATE','BEAR':'BEAR_MODERATE'}.get(current_regime, current_regime)` before lookup; or use `.get(..., default)`. |
| 302-320 | GAP | LOW | `_get_stop_loss_for_regime`, `_get_rebalance_frequency` use `.get(regime, default)` — safe. | OK. | — |

### 3.6 Dict lookups — missing key handling

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 244-246 | GAP | LOW | `stop_losses.get(regime, -10)` — safe. | OK. | — |

---

## FILE 4: early_breakout_detector.py

### 4.1 `detect_pre_breakout_setup()` — consolidation, volume

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 79-89 | GAP | LOW | Distance to resistance 2–4% gives +30; 0.5–2% gives +40. `distance_to_resistance > 5` penalizes -10. | Reasonable. | OK. |
| 328-346 | GAP | LOW | `_detect_volume_buildup`: gradual vs spike. last_third > second*1.2 and second > first*1.1 = building. last > second*2 = spike. | OK. | — |
| 349-361 | GAP | LOW | Consolidation: range < 5% (tight < 4%). | OK. | — |

### 4.2 Bearish divergence logic — INCORRECT (known)

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 321-334 | BUG | **HIGH** | `_check_bearish_divergence`: "Price making higher highs? RSI making lower highs?" But it only checks `price_higher_high = recent_prices.iloc[-1] > recent_prices.iloc[-5]` and `rsi < 70 and price_higher_high` → returns True. **No RSI comparison.** True divergence = price higher high AND RSI lower high. Here we use current RSI (single value) vs nothing. | False positives: any stock with price up and RSI<70 triggers "bearish divergence". | **Fix**: Compute RSI for last 10 bars; compare RSI at recent high vs RSI at prior high. If price[-1]>price[-5] and RSI[-1]<RSI[-5], then divergence. |
| 328 | BUG | MEDIUM | `rsi = stock_data.get('real_rsi', 50)` — uses pre-computed RSI from stock_data, not from df. So we're not comparing RSI over time. | Confirms: no temporal RSI comparison. | Compute RSI from df['Close'] for lookback window. |

### 4.3 `detect_momentum_exhaustion()` — exit signal logic

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 262 | GAP | LOW | Parabolic: `move_5d = (current - close[-6])/close[-6]*100`. Uses iloc[-6] for 5-day change. Correct. | OK. | — |
| 272 | GAP | LOW | `ma_20 = df['Close'].tail(20).mean()` — if len(df)==20, OK. Guard at line 226: len(df)<20 returns empty. | OK. | — |
| 278-293 | GAP | LOW | Exit thresholds: 80→EXIT NOW, 70→75-80%, 50→50-60%, 30→25%. | Reasonable. | — |

### 4.4 Math formulas and edge cases

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 324 | GAP | LOW | `support_zone_low <= low <= support_zone_high` — `low` from `lows` may be pd.Series element; comparison OK. | — | — |
| 386 | GAP | LOW | `second_half_min > first_half_min * 1.01` — 1% threshold for higher lows. | OK. | — |

---

## FILE 5: recommendation_history.py

### 5.1 Cooldown logic

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 81-121 | GAP | LOW | MIN_HOLD_DAYS=7. BUY→SELL and SELL→BUY both blocked for 7 days. | Prevents flip-flops. | OK. |
| 104-118 | GAP | MEDIUM | Cooldown overrides to HOLD but doesn't consider SCORE_CHANGE_THRESHOLD or FUNDAMENTAL_CHANGE_THRESHOLD for override. Those are checked in `validate_recommendation` but only for SELL override (lines 261-266). | Cooldown is strict; score/fundamental change can't override. | Consider: if score drops >15 and fundamentals deteriorated, allow SELL despite cooldown. |

### 5.2 CSV read/write — concurrent access, schema validation

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 34-45 | GAP | MEDIUM | `_load_history()` reads CSV; no locking. `_save_history()` writes. If multiple processes run (e.g. batch + CLI), race condition. | Corrupt or lost records. | Add file lock (fcntl, or single-writer pattern). |
| 36-38 | GAP | LOW | No schema validation — assumes columns exist. If CSV corrupted, may KeyError. | Rare. | Validate required columns on load. |
| 49-51 | GAP | LOW | `_create_empty_history()` defines schema. `record_recommendation` adds rows. | OK. | — |

### 5.3 Flip-flop detection

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 349-386 | GAP | LOW | `get_flip_flop_stocks` finds BUY→SELL or SELL→BUY within period. Correct. | OK. | — |

### 5.4 `validate_recommendation()` — does it correctly gate?

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 243-247 | GAP | MEDIUM | Cooldown check: if not cooldown_ok, sets final_action='HOLD'. But `action_type` passed in can be "HOLD CURRENT", "INCREASE", etc. `check_cooldown_period` expects BUY/SELL/HOLD/INCREASE. "HOLD CURRENT" may not match. | Need to verify callers pass canonical actions. | Map "HOLD CURRENT" → "HOLD" before cooldown check. |
| 261-266 | GAP | LOW | SELL override: if proposed SELL, score change minor, fundamentals unchanged, last action BUY/INCREASE/HOLD → override to HOLD. | Prevents premature exit. | OK. |
| 5297 | GAP | LOW | Caller passes `action_type` from recommendation logic. Ensure it's BUY/SELL/HOLD/INCREASE. | Check analyze_top200 usage. | — |

### 5.5 Outcome tracking — UPGRADE

| File:Line(s) | Type | Severity | Description | Impact | Fix |
|--------------|------|----------|-------------|--------|-----|
| 47-51 | UPGRADE | MEDIUM | Schema has date, symbol, action, score, price, etc. No outcome columns (price_7d, price_30d, price_90d). | Cannot measure recommendation accuracy. | **Add columns**: price_7d, price_30d, price_90d (filled asynchronously or in next run). Compute return_7d, return_30d, return_90d. |

---

## UPGRADE RECOMMENDATIONS (Bear-Market Focus)

### U1. Breadth signal — proper calculation

**Current:** Nifty high/low touch counts (not advance-decline).  
**Upgrade:** 
- Option A: Fetch NSE advance-decline ratio (e.g. from NSE website or nsepy).
- Option B: Use Nifty Midcap 100 / Nifty 50 ratio — when Midcap underperforms, breadth is weak.
- Option C: Use Nifty 500 vs Nifty 50 relative strength.

### U2. Multi-index regime detection

**Current:** Nifty 50 only.  
**Upgrade:** Add Bank Nifty (^NSEBANK) and Nifty Midcap 100. Regime = consensus of 3 indices. E.g. 2/3 bearish → BEAR. Reduces false BULL when only large caps hold up.

### U3. VIX weight in regime detection

**Current:** VIX in separate `_get_vix_level()`; not in regime_score formula.  
**Upgrade:** When VIX>25, increase volatility_signal weight to 35%, reduce trend to 25%. When VIX>30, force regime toward BEAR or at least reduce confidence.

### U4. Regime confidence gating

**Current:** Full adjustment magnitude regardless of confidence.  
**Upgrade:** `adjustment *= regime_data.get('regime_confidence', 0.5)`. Low confidence → smaller adjustment.

### U5. Crisis detector — real-time data

**Current:** yfinance, 15–20 min delay.  
**Upgrade:** Document limitation; if NSE/BSE real-time API available, use for crisis detection.

### U6. Adaptive strategy — auto regime mapping

**Current:** BULL/BEAR passed to adaptive strategy; keys don't match.  
**Upgrade:** In `AdaptiveMarketRegimeStrategy`, add:
```python
REGIME_MAP = {'BULL': 'BULL_MODERATE', 'BEAR': 'BEAR_MODERATE', 'SIDEWAYS': 'SIDEWAYS'}
def _map_regime(self, regime): return self.REGIME_MAP.get(regime, 'CALM')
```
Use in `get_position_sizing_strategy`, `get_adaptive_scoring_weights`, `market_performance.get`.

### U7. Recommendation history — outcome tracking

**Current:** No price_7d, price_30d, price_90d.  
**Upgrade:** Add columns; backfill in daily job; compute hit rate, avg return by action type.

---

## Priority Fix Order

1. **CRITICAL**: Regime key mapping (adaptive_market_strategy + analyze_top200) — fix bear sizing.
2. **CRITICAL**: CAIRN→VEDL, remove GIPCL from OIL_UPSTREAM (crisis_detector).
3. **CRITICAL**: RSI division by zero (market_regime_detector).
4. **HIGH**: Bearish divergence logic (early_breakout_detector).
5. **HIGH**: Integrate adaptive weights into hybrid scorer.
6. **HIGH**: Breadth signal replacement or proxy.
7. **MEDIUM**: VIX in regime formula.
8. **MEDIUM**: Regime confidence gating.
9. **MEDIUM**: ROC IndexError when len(close)<20.
10. **LOW**: Bare except in VIX fetch, schema validation, etc.

---

## Summary Table

| File | Bugs | Gaps | Upgrades |
|------|------|------|----------|
| market_regime_detector.py | 3 | 10 | 4 |
| crisis_detector.py | 1 | 4 | 1 |
| adaptive_market_strategy.py | 3 | 4 | 1 |
| early_breakout_detector.py | 2 | 4 | 0 |
| recommendation_history.py | 0 | 5 | 1 |

**Total: 9 bugs, 27 gaps, 7 upgrades.**
