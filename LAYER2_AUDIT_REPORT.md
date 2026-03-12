# Layer 2 Signal Generator Modules — Audit Report

**Audit Date:** March 13, 2025  
**Scope:** ml_predictor.py, sentiment_analyzer.py, volume_analyzer.py, pattern_recognition.py

---

## 1. ml_predictor.py — ML Prediction Engine

### Issue 1.1: Fallback MACD/Momentum Logic Never Matches
- **File:** ml_predictor.py, lines 363-371
- **Severity:** HIGH
- **Category:** Logic Flaw
- **Description:** The fallback prediction checks `'BUY' in str(macd_signal).upper()` and `'SELL' in str(macd_signal).upper()`, but `real_macd_signal` from the main analyzer is `'BULLISH'`, `'BEARISH'`, or `'NEUTRAL'` — never `'BUY'` or `'SELL'`. Similarly, `real_momentum` is `'STRONG_BULLISH'`, `'BULLISH'`, `'NEUTRAL'`, `'STRONG_BEARISH'`, `'BEARISH'` — the check for `'WEAK'` will never match.
- **Impact:** When ML model is unavailable, fallback predictions ignore MACD and momentum signals entirely, reducing accuracy of rule-based predictions.
- **Suggested fix:** Change to `'BUY' in macd_signal or 'BULLISH' in macd_signal` and `'SELL' in macd_signal or 'BEARISH' in macd_signal`. For momentum, add checks for `'BEARISH'` as bearish and `'BULLISH'` as bullish.

### Issue 1.2: prepare_features vs build_features_from_hist Field Mismatch
- **File:** ml_predictor.py, lines 123-233
- **Severity:** CRITICAL (when using dict-based path)
- **Category:** Logic Flaw / Missing Validation
- **Description:** `prepare_features()` expects stock_data as a dict with keys like `enhanced_rsi_14`, `enhanced_macd`, etc. The main analyzer may not populate all 65 fields with these exact names. When `predict_price_movement(stock_data)` is called with comprehensive dict data, missing keys default to 0/50, producing a different feature vector than `build_features_from_hist()` used in training. The `predict_from_ohlcv()` path correctly uses `build_features_from_hist()`.
- **Impact:** If the main pipeline calls `predict_price_movement(stock_data)` with dict data instead of `predict_from_ohlcv(hist, info)`, features will be misaligned with the trained model, causing wrong predictions.
- **Suggested fix:** Prefer `predict_from_ohlcv` when OHLCV is available. If dict path is required, ensure the dict is built from the same schema as `build_features_from_hist`, or add a validation step that rejects dict-based prediction when critical fields are missing.

### Issue 1.3: Duplicate enhanced_mfi in prepare_features
- **File:** ml_predictor.py, lines 145, 176
- **Severity:** MEDIUM
- **Category:** Logic Flaw
- **Description:** `enhanced_mfi` appears twice in the feature vector: once in Technical Indicators (index 14) and again in Volume Patterns (index 38). This double-counts the same signal.
- **Impact:** MFI gets 2x weight in the feature vector, potentially skewing model predictions.
- **Suggested fix:** Remove the duplicate from Volume Patterns (line 176) or replace with a different volume-based feature (e.g., OBV divergence or volume-price trend).

### Issue 1.4: Division by Zero in 52-Week High Feature
- **File:** ml_predictor.py, line 165
- **Severity:** LOW (edge case)
- **Category:** Edge Case
- **Description:** `current_price / max(self._safe_float(stock_data.get('52_week_high', current_price)), 1)` — if `52_week_high` is 0 and `current_price` is used as fallback, the max(0, 1)=1 protects. But if `52_week_high` is explicitly 0 in stock_data, `_safe_float` returns 0, and max(0, 1)=1. Actually safe. However, if `current_price` is 0, we get 0/1=0. The real risk: if `52_week_high` is very small (e.g., 0.001), we get a huge ratio. Consider validating 52_week_high > 0.
- **Impact:** Minor; extreme edge case for bad data.
- **Suggested fix:** Use `max(get_52_week_high, current_price * 0.5, 1)` to avoid degenerate ratios.

### Issue 1.5: Expected Return Heuristic May Be Misleading
- **File:** ml_predictor.py, lines 274, 323, 394
- **Severity:** MEDIUM
- **Category:** Logic Flaw
- **Description:** `expected_return = prediction * confidence * 0.2` (or 0.15 in fallback). For HOLD (prediction=0), expected_return is always 0. For BUY (1) with 70% confidence: 1 * 70 * 0.2 = 14%. The formula is arbitrary and not calibrated to actual forward returns.
- **Impact:** Downstream consumers may over-rely on expected_return for position sizing; values are not empirically validated.
- **Suggested fix:** Document as "directional magnitude proxy, not a return forecast" or calibrate from backtest.

### Issue 1.6: train_model Uses Different Hyperparameters Than train_ml_model.py
- **File:** ml_predictor.py, lines 77-84
- **Severity:** MEDIUM
- **Category:** Logic Flaw
- **Description:** `train_model()` uses `n_estimators=100`, `learning_rate=0.1`, `max_depth=5` with no `subsample`, `min_samples_leaf`, or `min_impurity_decrease`. The production trainer (`train_ml_model.py`) uses `n_estimators=200`, `learning_rate=0.08`, `max_depth=3`, `subsample=0.7`, `min_samples_leaf=30`, `min_impurity_decrease=1e-4`. If someone trains via `train_model()` instead of `train_ml_model.py`, the model will be different.
- **Impact:** Inconsistent model quality if both code paths are used.
- **Suggested fix:** Import and reuse the same hyperparameters from `train_ml_model.py`, or deprecate `train_model()` in favor of the CLI trainer.

---

## 2. sentiment_analyzer.py — Sentiment Analysis

### Issue 2.1: profit_margin Unit Ambiguity (Double Conversion Risk)
- **File:** sentiment_analyzer.py, lines 313-314
- **Severity:** HIGH
- **Category:** Unit Mismatch
- **Description:** `profit_margin = stock_data.get('profit_margin', 0) * 100` assumes profit_margin is in decimal (0–1). The main analyzer may pass `profit_margin` from `profitMargins` (decimal) or from `enhanced_fundamental_analyzer` which uses `* 100` (percentage). If the latter, we get double conversion (e.g., 15 → 1500).
- **Impact:** Earnings sentiment fallback can be wildly wrong when profit_margin is already in percentage.
- **Suggested fix:** `pm = stock_data.get('profit_margin', 0)`; use `pm * 100 if pm is not None and pm <= 1 else pm` to handle both formats.

### Issue 2.2: _calculate_confidence Variance Formula
- **File:** sentiment_analyzer.py, lines 306-314
- **Severity:** MEDIUM
- **Category:** Math Error
- **Description:** `confidence = np.clip(100 - variance * 50, 40, 100)`. For 5 signals with values [-1,-1,0,1,1], variance ≈ 0.96. Then 100 - 48 = 52. For perfect agreement [1,1,1,1,1], variance=0, confidence=100. For max disagreement [-2,-2,0,2,2], variance ≈ 3.2, 100 - 160 = -60 → clipped to 40. The formula is reasonable but the multiplier 50 is arbitrary; variance for 5 samples in [-2,2] can exceed 4, so 100 - 200 could heavily penalize.
- **Impact:** Confidence may be overly sensitive to a single outlier signal.
- **Suggested fix:** Use `100 - min(variance * 25, 60)` to cap the penalty, or normalize variance by number of signals.

### Issue 2.3: STRONG_BUY/STRONG_SELL Not in _calculate_confidence signal_map
- **File:** sentiment_analyzer.py, lines 298-302
- **Severity:** LOW
- **Category:** Logic Flaw
- **Description:** `signal_map` includes `'VERY_POSITIVE'`, `'POSITIVE'`, `'BULLISH'` but not `'STRONG_BUY'`. The overall sentiment can be `'STRONG_BUY'` or `'STRONG_SELL'` (lines 70, 82), but these map to 0 via `signal_map.get(s, 0)`.
- **Impact:** STRONG_BUY/STRONG_SELL are treated as neutral in confidence calculation, slightly understating agreement when they appear.
- **Suggested fix:** Add `'STRONG_BUY': 2`, `'STRONG_SELL': -2` to signal_map.

### Issue 2.4: News Sentiment Uses Overlapping Return Thresholds
- **File:** sentiment_analyzer.py, lines 121-124
- **Severity:** LOW
- **Category:** Logic Flaw
- **Description:** `positive_days = (recent_returns > 0.01).sum()` and `negative_days = (recent_returns < -0.01).sum()`. Days with returns in [-0.01, 0.01] are counted in neither. So 20 days could sum to e.g. 8 positive + 5 negative + 7 neutral. The momentum_score `(positive_days - negative_days) / 20 * 100` ignores the 7 neutral days. This is intentional but the 1% threshold is hardcoded.
- **Suggested fix:** Make threshold configurable (e.g., 0.5% or 1.5% for different volatility regimes).

### Issue 2.5: adjust_score_by_sentiment KeyError Risk
- **File:** sentiment_analyzer.py, line 399
- **Severity:** LOW
- **Category:** Edge Case
- **Description:** `sentiment_data['overall_sentiment']` is accessed directly. If `_get_default_sentiment()` or a malformed result omits this key, KeyError.
- **Impact:** Crash when sentiment analysis fails or returns partial data.
- **Suggested fix:** Use `sentiment_data.get('overall_sentiment', 'NEUTRAL')`.

---

## 3. volume_analyzer.py — Volume Analysis

### Issue 3.1: VWAP Uses Cumulative Anchored VWAP, Not Session VWAP
- **File:** volume_analyzer.py, lines 142-144
- **Severity:** MEDIUM
- **Category:** Logic Flaw (design choice)
- **Description:** `data['vwap'] = (data['typical_price'] * data['Volume']).cumsum() / data['Volume'].cumsum()` computes cumulative VWAP from the start of the series. Standard VWAP is per-session. For daily data, this is "anchored VWAP" from the first day — a valid choice but different from typical daily VWAP.
- **Impact:** VWAP distance and position may not match trader expectations of "today's VWAP."
- **Suggested fix:** Document as "anchored cumulative VWAP" or add an option for rolling N-day VWAP.

### Issue 3.2: VWAP Trend Division by Zero
- **File:** volume_analyzer.py, line 164
- **Severity:** LOW
- **Category:** Edge Case
- **Description:** `vwap_slope = (data['vwap'].iloc[-1] - data['vwap'].iloc[-10]) / data['vwap'].iloc[-10]`. If `vwap.iloc[-10]` is 0, division by zero.
- **Impact:** Crash on degenerate data (e.g., zero prices).
- **Suggested fix:** Use `data['vwap'].iloc[-10] + 1e-9` or check for zero before dividing.

### Issue 3.3: Order Flow Inference Is Crude
- **File:** volume_analyzer.py, lines 201-204
- **Severity:** MEDIUM
- **Category:** Logic Flaw
- **Description:** `buy_volume = np.where(price_change > 0, Volume, 0)` and vice versa. This assumes all volume on up days is buying and all volume on down days is selling. In reality, both occur every day; this is a rough proxy.
- **Impact:** Order flow direction can be wrong on mixed days (e.g., gap up then sell-off).
- **Suggested fix:** Document as "simplified proxy" or use a more sophisticated method (e.g., close vs typical price, or tick-level if available).

### Issue 3.4: Block Trade Direction Uses Candle Color Only
- **File:** volume_analyzer.py, lines 261-264
- **Severity:** MEDIUM
- **Category:** Logic Flaw
- **Description:** `block_direction = np.where(Close > Open, 'BUY', np.where(Close < Open, 'SELL', 'NEUTRAL'))`. A green candle does not mean institutional buying — could be short covering or retail. Similarly for red.
- **Impact:** Institutional activity direction may be misclassified.
- **Suggested fix:** Document limitation; consider combining with order flow or volume profile.

### Issue 3.5: Volume Profile Division by Zero and Flat Price
- **File:** volume_analyzer.py, lines 319-321, 350-351
- **Severity:** MEDIUM
- **Category:** Edge Case
- **Description:** (1) `bins = np.linspace(price_min, price_max, 21)` — if `price_min == price_max` (flat price), all bins are identical; `pd.cut` can fail or produce invalid intervals. (2) `profile_std / profile_mean` — if `profile_mean` is 0 (all bins empty or equal), division by zero.
- **Impact:** Crash or incorrect shape on flat/sideways price action.
- **Suggested fix:** If `price_max - price_min < 1e-9`, use a single bin or skip profile. Guard `profile_mean` with `profile_mean + 1e-9` or check before dividing.

### Issue 3.6: Built-in `bin` Shadowed
- **File:** volume_analyzer.py, lines 339-340
- **Severity:** LOW
- **Category:** Code Quality
- **Description:** `for bin in value_area_bins` — `bin` is a Python built-in. Shadowing it can cause subtle bugs if `bin()` is used later in the scope.
- **Suggested fix:** Rename to `b` or `interval` or `bin_label`.

### Issue 3.7: volume_sr_levels zone_distance_pct Division by Zero
- **File:** volume_analyzer.py, line 303
- **Severity:** LOW
- **Category:** Edge Case
- **Description:** `zone_distance_pct = ((current_price - nearest_zone) / nearest_zone) * 100`. If `nearest_zone` is 0, division by zero.
- **Impact:** Crash on bad data.
- **Suggested fix:** Use `nearest_zone + 1e-9` or skip if `nearest_zone <= 0`.

### Issue 3.8: MODERATE Block Activity Only Adds for BUY
- **File:** volume_analyzer.py, lines 357-365
- **Severity:** MEDIUM
- **Category:** Logic Flaw
- **Description:** For `activity_level == 'MODERATE'`, only `recent_direction == 'BUY'` adds +5. `recent_direction == 'SELL'` does not subtract. Asymmetric treatment.
- **Impact:** Bearish signal from moderate institutional selling is ignored.
- **Suggested fix:** Add `elif blocks_data['recent_direction'] == 'SELL': score -= 5` for MODERATE activity.

### Issue 3.9: adjust_score_by_volume Missing Clamp on Final Score
- **File:** volume_analyzer.py, lines 413-414
- **Severity:** MEDIUM
- **Category:** Logic Flaw
- **Description:** `adjusted_score = base_score + adjustment` — the result is not clamped to [0, 100]. If base_score is 95 and adjustment is +10, we get 105.
- **Impact:** Scores can exceed 100, breaking downstream assumptions.
- **Suggested fix:** `adjusted_score = np.clip(base_score + adjustment, 0, 100)`.

---

## 4. pattern_recognition.py — Chart Pattern Detection

### Issue 4.1: Head & Shoulders Division by Zero
- **File:** pattern_recognition.py, lines 82, 96
- **Severity:** LOW
- **Category:** Edge Case
- **Description:** `shoulder_diff = abs(left_shoulder - right_shoulder) / left_shoulder` and `head_prominence = (head - max(...)) / head`. If `left_shoulder` or `head` is 0, division by zero.
- **Impact:** Crash on zero/negative prices (data error).
- **Suggested fix:** Add `if left_shoulder <= 0 or head <= 0: continue` before division.

### Issue 4.2: Inverse H&S Same Division Risk
- **File:** pattern_recognition.py, lines 146, 157
- **Severity:** LOW
- **Category:** Edge Case
- **Description:** Same pattern as 4.1 for inverse H&S.
- **Suggested fix:** Same guard.

### Issue 4.3: Double Top/Bottom Division by Zero
- **File:** pattern_recognition.py, lines 203, 261
- **Severity:** LOW
- **Category:** Edge Case
- **Description:** `peak_diff = abs(first_peak - second_peak) / first_peak` and `trough_diff = abs(first_trough - second_trough) / first_trough`. Zero peak/trough causes division by zero.
- **Suggested fix:** Guard with `if first_peak <= 0` / `if first_trough <= 0`.

### Issue 4.4: Triangle Slope Not Time-Normalized
- **File:** pattern_recognition.py, lines 315-316
- **Severity:** MEDIUM
- **Category:** Math Error
- **Description:** `peak_slope = (peak_prices[-1] - peak_prices[0]) / len(recent_peaks)` divides by number of peaks, not bars. Slope magnitude depends on spacing. For 2 peaks 20 bars apart vs 2 peaks 5 bars apart, same price change gives different slopes.
- **Impact:** Triangle detection may be inconsistent across different bar spacings.
- **Suggested fix:** Use `(peak_prices[-1] - peak_prices[0]) / (recent_peaks[-1] - recent_peaks[0] + 1e-9)` to normalize by bar distance.

### Issue 4.5: Flag Pattern Division by Zero
- **File:** pattern_recognition.py, lines 283, 294
- **Severity:** LOW
- **Category:** Edge Case
- **Description:** `price_range / recent_prices.mean() < 0.03` — if `recent_prices.mean()` is 0, division by zero.
- **Suggested fix:** Use `recent_prices.mean() + 1e-9` or skip if mean is 0.

### Issue 4.6: Cup & Handle Division by Zero
- **File:** pattern_recognition.py, lines 325, 328, 331
- **Severity:** LOW
- **Category:** Edge Case
- **Description:** `abs(cup_start - cup_end) / cup_start`, `(cup_start - cup_low) / cup_start`, `(handle_high - handle_low) / handle_high` — any zero denominator causes error.
- **Suggested fix:** Add guards for zero.

### Issue 4.7: get_pattern_score Normalization Changes Scale
- **File:** pattern_recognition.py, lines 391-395
- **Severity:** MEDIUM
- **Category:** Logic Flaw
- **Description:** `bullish_score = bullish_score / total` and `bearish_score = bearish_score / total` so scores sum to 1. A single high-confidence pattern (0.9) yields bullish=0.9, bearish=0.1. Two weak patterns (0.3 each) also sum to 0.6. The normalization conflates "number of patterns" with "strength of patterns."
- **Impact:** One strong pattern can dominate; multiple weak patterns get diluted.
- **Suggested fix:** Consider using max confidence or weighted average instead of sum-then-normalize, or document the behavior.

### Issue 4.8: Symmetrical Triangle Returns 'neutral' Direction
- **File:** pattern_recognition.py, line 354
- **Severity:** LOW
- **Category:** Logic Flaw
- **Description:** Symmetrical triangle has `direction: 'neutral'`. In `get_pattern_score`, `direction == 'neutral'` adds to neither bullish nor bearish score. So a detected symmetrical triangle contributes 0 to both scores.
- **Impact:** Valid pattern detection adds no signal to the composite.
- **Suggested fix:** Either add a small weight for neutral patterns (e.g., volatility/breakout likelihood) or document that symmetrical triangles are informational only.

### Issue 4.9: Pattern Detection Order and First-Match Return
- **File:** pattern_recognition.py, lines 70-112 (H&S), 204-232 (double top)
- **Severity:** LOW
- **Category:** Logic Flaw
- **Description:** Loops iterate `for i in range(len(peaks)-2)` and return on first match. The first chronological match is returned, not necessarily the most recent or strongest. For H&S, an old completed pattern may be returned instead of a newer forming one.
- **Impact:** May surface stale patterns.
- **Suggested fix:** Collect all matches and return the one with highest confidence or most recent (rightmost) pattern.

---

## Summary by Severity

| Severity  | Count |
|-----------|-------|
| CRITICAL  | 1     |
| HIGH      | 3     |
| MEDIUM    | 14    |
| LOW       | 15    |

## Recommended Priority Fixes

1. **ml_predictor.py**: Fix fallback MACD/momentum string matching (1.1).
2. **sentiment_analyzer.py**: Fix profit_margin unit handling (2.1).
3. **volume_analyzer.py**: Clamp adjusted_score to [0,100] (3.9); add SELL case for MODERATE blocks (3.8).
4. **ml_predictor.py**: Resolve prepare_features vs build_features_from_hist usage (1.2); remove duplicate enhanced_mfi (1.3).
5. **volume_analyzer.py**: Guard volume profile for flat prices and zero mean (3.5).
6. **pattern_recognition.py**: Normalize triangle slope by bar distance (4.4).
