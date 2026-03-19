# Layer 2 Signal Generator Modules — Final Line-by-Line Audit Report

**Audit Date:** March 13, 2025  
**Scope:** ml_predictor.py, sentiment_analyzer.py, volume_analyzer.py, pattern_recognition.py  
**Context:** Backtesting shows ±22 points of noise (ML ±8, sentiment ±5, volume ±5, pattern ±4) causing ranking flips in bear markets.

---

## Executive Summary

| Module | Bugs | Gaps | Upgrades | Critical/High |
|--------|------|------|----------|----------------|
| ml_predictor.py | 4 | 2 | 3 | 2 |
| sentiment_analyzer.py | 4 | 2 | 2 | 1 |
| volume_analyzer.py | 6 | 2 | 2 | 0 |
| pattern_recognition.py | 8 | 2 | 2 | 0 |

**Key Finding:** Sentiment and volume largely re-process price/momentum data. ML adds value only when trained and when `predict_from_ohlcv` is used. Pattern recognition has no Indian-market validation.

---

# FILE 1: ml_predictor.py

## Feature Preparation — Every Feature and Expected Range/Unit

| Index | Feature | Expected Range/Unit | Source |
|-------|---------|---------------------|--------|
| 0 | real_rsi | 0–100 | RSI(14) |
| 1 | enhanced_rsi_14 | 0–100 | Same as above (duplicate in prepare_features) |
| 2 | enhanced_macd | Any (typically -2 to +2) | MACD line |
| 3 | enhanced_signal_line | Any | Signal line |
| 4 | enhanced_bb_position | 0–1 | Position in BB (0=lower, 1=upper) |
| 5 | enhanced_bb_width | 0+ | BB width as fraction of price |
| 6 | enhanced_atr_14 | 0+ % | ATR as % of price |
| 7 | enhanced_adx | 0–100 | ADX |
| 8 | enhanced_cci | -200 to +200 | CCI(20) |
| 9 | enhanced_stoch_k | 0–100 | Stochastic %K |
| 10 | enhanced_stoch_d | 0–100 | Stochastic %D |
| 11 | enhanced_williams_r | -100 to 0 | Williams %R |
| 12 | enhanced_roc | % | Rate of change |
| 13 | enhanced_mfi | 0–100 | Money Flow Index |
| 14 | enhanced_obv_trend | -1 to 1 | OBV slope normalized |
| 15 | enhanced_vwap_distance | % | Distance from VWAP |
| 16–19 | ma_20, ma_50, ma_200, enhanced_price_vs_ma20 | Price / % | MAs and price vs MA20 |
| 20–29 | Price momentum (1d, 5d, 20d, 50d, momentum, volatility, 52w high) | % | Returns and ratios |
| 30–37 | Volume features | Ratios, 0–1 | Volume ratio, trend, MFI (duplicate) |
| 38–52 | Fundamental metrics | Various | PE, PB, ROE, profit_margin (%), etc. |
| 53–59 | Sentiment & flow proxies | 0–100, -1 to 1 | Institutional, FII/DII, MTF |
| 60–64 | Multi-timeframe | -1 to 1, 0–100 | Daily/weekly/monthly trend, composite, advanced_tech |

---

## Issue 1.1: Fallback Checks BUY/SELL but Data Has BULLISH/BEARISH

- **File:Line(s):** ml_predictor.py:363–375
- **Type:** BUG
- **Severity:** HIGH
- **Description:** Fallback uses `'BUY' in str(macd_signal).upper()` and `'SELL' in str(macd_signal).upper()`. Actual values from analyzer are `'BULLISH'`, `'BEARISH'`, `'NEUTRAL'`. Similarly `real_momentum` is `'STRONG_BULLISH'`, `'BULLISH'`, `'NEUTRAL'`, `'STRONG_BEARISH'`, `'BEARISH'` — `'WEAK'` never matches.
- **Impact on accuracy:** When ML is unavailable, fallback ignores MACD and momentum; predictions default to neutral.
- **Fix:** Use `'BULLISH' in str(macd_signal).upper() or 'BUY' in str(macd_signal).upper()` and `'BEARISH' in str(macd_signal).upper() or 'SELL' in str(macd_signal).upper()`. For momentum: `'BULLISH'`/`'STRONG_BULLISH'` → bullish, `'BEARISH'`/`'STRONG_BEARISH'` → bearish.

---

## Issue 1.2: Fallback Receives Empty Dict When Called from predict_from_ohlcv

- **File:Line(s):** ml_predictor.py:306–307, 316–317, 336–337
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** When `predict_from_ohlcv` fails (no hist, model not trained, features None, exception), it calls `_get_fallback_prediction({})` with an empty dict. Fallback never receives RSI, MACD, momentum from stock_data.
- **Impact on accuracy:** Fallback always uses defaults (RSI=50, etc.) when invoked from main pipeline.
- **Fix:** When `predict_from_ohlcv` is called, pass `info` or a minimal dict with RSI/MACD derived from `hist` into fallback, or compute simple RSI/MACD from `hist` inside fallback when `stock_data` is empty.

---

## Issue 1.3: Duplicate enhanced_mfi in prepare_features

- **File:Line(s):** ml_predictor.py:145, 176
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** `enhanced_mfi` appears in Technical Indicators (index 14) and Volume Patterns (index 38). Same value counted twice.
- **Impact on accuracy:** MFI gets 2× weight in dict-based prediction path.
- **Fix:** Remove line 176; replace with `enhanced_obv_trend` or another distinct volume feature. Note: `train_ml_model.build_features_from_hist` uses MFI only once in g3 (line 312); ml_predictor.prepare_features has the duplicate.

---

## Issue 1.4: prepare_features vs build_features_from_hist Schema Mismatch

- **File:Line(s):** ml_predictor.py:123–233 vs train_ml_model.py:105–324
- **Type:** GAP
- **Severity:** CRITICAL (if dict path used)
- **Description:** `prepare_features()` expects dict keys like `enhanced_rsi_14`, `enhanced_macd`. Main analyzer uses `predict_from_ohlcv(hist, info)` (line 1662), which uses `build_features_from_hist` — correct. But any caller using `predict_price_movement(stock_data)` with a dict may have misaligned features.
- **Impact on accuracy:** Wrong predictions if dict path is used with incomplete schema.
- **Fix:** Prefer `predict_from_ohlcv` everywhere. Deprecate or validate dict path; reject prediction when critical fields are missing.

---

## Issue 1.5: Confidence Calculation — Max Probability Only

- **File:Line(s):** ml_predictor.py:266, 321
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** `confidence = np.max(probabilities) * 100`. A 34/33/33 split yields 34% confidence; a 90/5/5 split yields 90%. Both are treated the same for adjustment magnitude. No calibration to actual forward returns.
- **Impact on accuracy:** Low-confidence predictions get same ±8 cap as high-confidence; adds noise when confidence is low.
- **Fix/Upgrade:** Use confidence-weighted adjustment: `adj = base_adj * (confidence / 70)` when confidence < 70, else full adj.

---

## Issue 1.6: Model Path and Loading

- **File:Line(s):** ml_predictor.py:35–49
- **Type:** GAP
- **Severity:** LOW
- **Description:** Loads from `models/ml_predictor_latest.pkl`. Path is relative; may fail if CWD differs. No version check vs `build_features_from_hist` schema.
- **Impact on accuracy:** Silent fallback to rule-based if path wrong or schema changed.
- **Fix:** Use `Path(__file__).parent.parent / 'models' / 'ml_predictor_latest.pkl'` or config. Add feature_count validation against expected 65.

---

## Issue 1.7: Expected Return Heuristic Not Calibrated

- **File:Line(s):** ml_predictor.py:274, 323, 394
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** `expected_return = prediction * confidence * 0.2` is arbitrary. HOLD always 0. BUY with 70% confidence → 14%.
- **Impact on accuracy:** Downstream use for sizing could be misleading.
- **Fix:** Document as "directional magnitude proxy" or calibrate from backtest.

---

## Issue 1.8: train_model Hyperparameters Differ from train_ml_model.py

- **File:Line(s):** ml_predictor.py:77–84
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** `train_model()` uses `n_estimators=100`, `max_depth=5`. Production trainer uses `n_estimators=200`, `max_depth=3`, `subsample=0.7`, `min_samples_leaf=30`.
- **Impact on accuracy:** Inconsistent models if both paths used.
- **Fix:** Import hyperparameters from `train_ml_model` or deprecate `train_model()`.

---

## UPGRADE 1.1: Reduce ML Adjustment Cap from ±8 to ±4

- **Rationale:** ±8 on 0–100 scale is large. Combined with other signals (±22 total), causes ranking flips. Backtest suggests ML adds noise in bear markets.
- **Fix:** In scoring pipeline, cap ML adjustment at ±4. Consider confidence-weighted: full ±4 only when confidence ≥ 70%.

---

## UPGRADE 1.2: Confidence-Weighted ML Adjustment

- **Rationale:** Low-confidence predictions (e.g. 40%) should not move score as much as 85% confidence.
- **Fix:** `ml_adj = base_cap * min(1.0, confidence / 70)`.

---

## UPGRADE 1.3: Is ML Adding Value or Noise?

- **Assessment:** ML adds value only when: (1) model is trained on sufficient data, (2) `predict_from_ohlcv` is used (not dict path), (3) market regime matches training. In bear markets, momentum-based features may flip; model trained in bull market can underperform.
- **Recommendation:** Backtest ML contribution by regime. Consider disabling or reducing ML adjustment in BEAR regime until validated.

---

# FILE 2: sentiment_analyzer.py

## Sub-Score Summary

| Sub-Score | Weight | Data Source | Proxy? |
|-----------|--------|-------------|--------|
| news_sentiment | 30% | Price momentum + volume surge | Yes — no real news API |
| analyst_sentiment | 25% | yfinance recommendations or PE fallback | Real when available |
| market_sentiment | 20% | RSI, volume trend, price vs MA20 | Yes — technical indicators |
| earnings_sentiment | 15% | yfinance earnings or profit_margin | Real/fallback |
| buzz_sentiment | 10% | Volume ratio, volatility, momentum | Yes — price/volume derived |

---

## Issue 2.1: profit_margin Unit Handling

- **File:Line(s):** sentiment_analyzer.py:313–314
- **Type:** BUG
- **Severity:** HIGH
- **Description:** `profit_margin = stock_data.get('profit_margin', 0) * 100` assumes decimal (0–1). `enhanced_fundamental_analyzer` and `train_ml_model` use `* 100` (percentage). If stock_data has 15 (%), we get 1500.
- **Impact on accuracy:** Earnings fallback misclassifies when profit_margin is already in %.
- **Fix:** `pm = stock_data.get('profit_margin', 0)`; use `pm * 100 if pm is not None and 0 <= pm <= 1 else pm`.

---

## Issue 2.2: _calculate_confidence Missing STRONG_BUY/STRONG_SELL

- **File:Line(s):** sentiment_analyzer.py:296–302, 398
- **Type:** BUG
- **Severity:** LOW
- **Description:** `signal_map` has `'BULLISH'`, `'BEARISH'` but not `'STRONG_BUY'` or `'STRONG_SELL'`. These map to 0 (neutral). `sentiment_data['overall_sentiment']` accessed directly — KeyError if missing.
- **Impact on accuracy:** STRONG_BUY/STRONG_SELL understated in confidence; possible crash.
- **Fix:** Add `'STRONG_BUY': 2`, `'STRONG_SELL': -2`. Use `sentiment_data.get('overall_sentiment', 'NEUTRAL')`.

---

## Issue 2.3: News Sentiment Is Momentum Proxy

- **File:Line(s):** sentiment_analyzer.py:111–151
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** "News" score is derived from `positive_days`/`negative_days` (returns > 1%) and `volume_surge`. No real news. Same price data feeds technical score.
- **Impact on accuracy:** Sentiment adds no unique information; doubles momentum signal.
- **Fix:** Document clearly. Consider reducing news weight or disabling until real API.

---

## Issue 2.4: adjust_score_by_sentiment Cap and Logic

- **File:Line(s):** sentiment_analyzer.py:354–410
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** Base adjustment ±12/±8 by band; bonus +2 for news/analyst/earnings. Cap ±15. Neutral band 35–65 gets 0. Edge case: composite_score exactly 65 or 35 may sit on boundary.
- **Impact on accuracy:** ±15 is large; combined with other signals causes overshoot.
- **Fix:** Consider cap ±8. Add `STRONG_BUY`/`STRONG_SELL` handling in bonus logic.

---

## UPGRADE 2.1: Disable or Reduce Sentiment Until Real News API

- **Rationale:** News, market, and buzz sub-scores are price/volume proxies. Only analyst and earnings add distinct information.
- **Fix:** Option A: Set sentiment adjustment to 0 until NewsAPI/AlphaVantage integrated. Option B: Use only analyst + earnings components; cap at ±5.

---

## UPGRADE 2.2: Reduce Sentiment Cap from ±15 to ±5

- **Rationale:** ±15 on top of ML/volume/pattern is excessive. Backtest shows sentiment contributes to noise.
- **Fix:** Cap at ±5. Use confidence-weighted: `adj = base_adj * (confidence / 100)`.

---

# FILE 3: volume_analyzer.py

## VWAP Calculation

- **File:Line(s):** volume_analyzer.py:142–144
- **Description:** `vwap = (typical_price * Volume).cumsum() / Volume.cumsum()` — anchored cumulative VWAP from series start. Not per-session VWAP. Documented in LAYER2_AUDIT as design choice.

---

## Issue 3.1: VWAP Trend Division by Zero

- **File:Line(s):** volume_analyzer.py:164
- **Type:** BUG
- **Severity:** LOW
- **Description:** `vwap_slope = (...)/ data['vwap'].iloc[-10]` — division by zero if vwap is 0.
- **Impact on accuracy:** Crash on bad data.
- **Fix:** Use `data['vwap'].iloc[-10] + 1e-9` or guard.

---

## Issue 3.2: Order Flow Uses Up/Down Day as Proxy

- **File:Line(s):** volume_analyzer.py:201–204
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** `buy_volume = np.where(price_change > 0, Volume, 0)`. All volume on up days = buy, down days = sell. Ignores intraday structure.
- **Impact on accuracy:** Order flow can be wrong on mixed days (gap up then sell-off).
- **Fix:** Document as simplified proxy. Consider close vs typical price or Chaikin MF.

---

## Issue 3.3: Block Trade Direction Uses Candle Color Only

- **File:Line(s):** volume_analyzer.py:261–264
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** Green candle → BUY, red → SELL. No distinction between institutional vs retail.
- **Impact on accuracy:** Institutional direction may be wrong.
- **Fix:** Document limitation.

---

## Issue 3.4: Volume Profile Flat Price and Division by Zero

- **File:Line(s):** volume_analyzer.py:319–321, 350–351
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** If `price_min == price_max`, bins collapse. `profile_std / profile_mean` fails when mean is 0.
- **Impact on accuracy:** Crash or wrong shape.
- **Fix:** If `price_max - price_min < 1e-9`, skip or use single bin. Guard `profile_mean + 1e-9`.

---

## Issue 3.5: Built-in `bin` Shadowed

- **File:Line(s):** volume_analyzer.py:339–340
- **Type:** BUG
- **Severity:** LOW
- **Description:** `for bin in value_area_bins` shadows built-in `bin()`.
- **Fix:** Rename to `b` or `interval`.

---

## Issue 3.6: zone_distance_pct Division by Zero

- **File:Line(s):** volume_analyzer.py:303
- **Type:** BUG
- **Severity:** LOW
- **Description:** `(current_price - nearest_zone) / nearest_zone` — zero `nearest_zone` causes error.
- **Fix:** Use `nearest_zone + 1e-9` or skip if <= 0.

---

## Issue 3.7: MODERATE Block Activity Asymmetric — No SELL Penalty

- **File:Line(s):** volume_analyzer.py:357–365
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** For `activity_level == 'MODERATE'`, only `recent_direction == 'BUY'` adds +5. `'SELL'` does not subtract.
- **Impact on accuracy:** Bearish institutional selling ignored.
- **Fix:** Add `elif blocks_data['recent_direction'] == 'SELL': score -= 5`.

---

## Issue 3.8: adjust_score_by_volume Missing Clamp

- **File:Line(s):** volume_analyzer.py:413–414
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** `adjusted_score = base_score + adjustment` not clamped to [0, 100]. Base 95 + adj 10 = 105.
- **Impact on accuracy:** Scores can exceed 100.
- **Fix:** `adjusted_score = np.clip(base_score + adjustment, 0, 100)`.

---

## UPGRADE 3.1: Simplify Volume to Binary Confirmation

- **Rationale:** Volume composite overlaps with momentum (up days = buying). May add noise more than signal.
- **Fix:** Use volume as confirmation only: if `volume_signal` agrees with base score direction, apply +2; if disagrees, apply -2. Cap ±3. Remove continuous formula.

---

## UPGRADE 3.2: Reduce Volume Cap from ±10 to ±5

- **Rationale:** ±10 is large. Volume is a proxy; confidence-weighted adjustment preferred.
- **Fix:** `max_adjustment = 5.0`. Consider `adjustment *= (volume_confidence / 70)` when confidence < 70.

---

# FILE 4: pattern_recognition.py

## Pattern Detectors Summary

| Pattern | Direction | Confidence | Notes |
|---------|-----------|------------|-------|
| Head & Shoulders | bearish | 0.5–0.9 | Neckline break |
| Inverse H&S | bullish | 0.5–0.9 | Neckline break |
| Double Top | bearish | 0.6–0.85 | Support break |
| Double Bottom | bullish | 0.6–0.85 | Resistance break |
| Ascending Triangle | bullish | 0.75 | Flat resistance, rising support |
| Descending Triangle | bearish | 0.75 | Flat support, falling resistance |
| Symmetrical Triangle | neutral | 0.65 | No direction |
| Bull/Bear Flag | bullish/bearish | 0.70 | 5% move + tight consolidation |
| Cup & Handle | bullish | 0.80 | U-shape + handle |

---

## Issue 4.1: Division by Zero in H&S, Inverse H&S, Double Top/Bottom

- **File:Line(s):** pattern_recognition.py:82, 96, 146, 157, 203, 261
- **Type:** BUG
- **Severity:** LOW
- **Description:** `shoulder_diff = abs(...)/ left_shoulder`, `head_prominence = (...)/ head`, `peak_diff = (...)/ first_peak`, `trough_diff = (...)/ first_trough` — zero causes error.
- **Fix:** Guard `if left_shoulder <= 0 or head <= 0: continue`; same for peak/trough.

---

## Issue 4.2: Triangle Slope Not Time-Normalized

- **File:Line(s):** pattern_recognition.py:315–316
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** `peak_slope = (peak_prices[-1] - peak_prices[0]) / len(recent_peaks)` — divides by count, not bar distance. Same price change over 5 vs 20 bars gives different slopes.
- **Impact on accuracy:** Inconsistent triangle detection.
- **Fix:** Use `(peak_prices[-1] - peak_prices[0]) / (recent_peaks[-1] - recent_peaks[0] + 1e-9)`.

---

## Issue 4.3: Flag and Cup & Handle Division by Zero

- **File:Line(s):** pattern_recognition.py:283, 294, 325, 328, 331
- **Type:** BUG
- **Severity:** LOW
- **Description:** `price_range / recent_prices.mean()`, `abs(cup_start - cup_end) / cup_start`, etc.
- **Fix:** Add `+ 1e-9` or zero guards.

---

## Issue 4.4: get_pattern_score Normalization

- **File:Line(s):** pattern_recognition.py:391–395
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** `bullish_score /= total`, `bearish_score /= total`. One strong pattern (0.9) vs two weak (0.3 each) — normalization conflates count and strength.
- **Impact on accuracy:** Single strong pattern dominates; multiple weak patterns diluted.
- **Fix:** Consider max confidence or weighted average; or document behavior.

---

## Issue 4.5: Symmetrical Triangle Contributes Zero

- **File:Line(s):** pattern_recognition.py:354, 386–388
- **Type:** BUG
- **Severity:** LOW
- **Description:** `direction: 'neutral'` adds to neither bullish nor bearish. Detected pattern adds no signal.
- **Impact on accuracy:** Wasted computation; could add volatility/breakout hint.
- **Fix:** Add small weight for neutral (e.g. volatility indicator) or document as informational.

---

## Issue 4.6: First-Match Return May Be Stale

- **File:Line(s):** pattern_recognition.py:70–112, 204–232
- **Type:** GAP
- **Severity:** LOW
- **Description:** Loops return first chronological match. Older completed pattern may be chosen over newer forming one.
- **Fix:** Collect all matches; return highest confidence or most recent.

---

## Issue 4.7: Double-Counting with advanced_tech_score

- **File:Line(s):** analyze_top200_stocks_enhanced.py:1959
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** `advanced_tech_score = real_tech * 0.35 + mtf * 0.22 + institutional * 0.18 + pattern_score * 0.15 + enhanced * 0.10`. Pattern contributes 15%. Then `pattern_score_contribution` (±4) is applied again in final score. Pattern affects score twice.
- **Impact on accuracy:** Pattern overweighted.
- **Fix:** Ensure pattern adjustment is either in advanced_tech OR as separate contribution, not both. Audit scoring pipeline.

---

## UPGRADE 4.1: Reduce Pattern Weight

- **Rationale:** Pattern recognition has no Indian-market validation. Thresholds (3% shoulder diff, 2% peak diff) may not be optimal for NSE.
- **Fix:** Reduce pattern_score weight in advanced_tech from 0.15 to 0.08. Or reduce pattern_score_contribution cap from ±4 to ±2.

---

## UPGRADE 4.2: Indian Market Validation

- **Rationale:** H&S, double top/bottom, etc. are from US literature. Indian markets may have different volatility and structure.
- **Fix:** Backtest pattern hit rate and forward returns on NSE. Adjust thresholds or disable low-performing patterns.

---

# Summary: Recommended Fix Order

## Critical / High (Fix First)

1. **ml_predictor.py:363–375** — Fallback BULLISH/BEARISH string matching
2. **sentiment_analyzer.py:313–314** — profit_margin unit handling

## Medium (Fix Soon)

3. **volume_analyzer.py:414** — Clamp adjusted_score to [0, 100]
4. **volume_analyzer.py:357–365** — MODERATE blocks SELL penalty
5. **ml_predictor.py:145, 176** — Remove duplicate enhanced_mfi
6. **pattern_recognition.py:315–316** — Triangle slope time-normalization
7. **volume_analyzer.py:319–351** — Volume profile flat price / div-by-zero guards

## Upgrades (Reduce Noise)

| Signal | Current Cap | Suggested Cap | Rationale |
|--------|-------------|---------------|------------|
| ML | ±8 | ±4 | Backtest shows noise in bear markets |
| Sentiment | ±15 | ±5 or 0 | No real news; proxy only |
| Volume | ±10 | ±5 | Proxy; simplify to confirmation |
| Pattern | ±4 | ±2 | No Indian validation; double-count in advanced_tech |

## Confidence-Weighted Adjustments

Apply to all four signals:
- `effective_adj = base_adj * min(1.0, confidence / 70)`
- When confidence < 50%, consider no adjustment (or ±1 max).
