# Signal Generator Modules — Full Audit Report

**Date:** 2025-03-13  
**Scope:** ml_predictor.py, sentiment_analyzer.py, volume_analyzer.py, pattern_recognition.py, early_breakout_detector.py

---

## 1. ml_predictor.py

### 1.1 CRITICAL — Feature Vector Mismatch (prepare_features vs train_ml_model)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 177-178 | **CRITICAL** | `prepare_features()` expects `enhanced_cmf` (Chaikin Money Flow) as the 8th volume feature, but `train_ml_model.build_features_from_hist()` produces `enhanced_mfi` (Money Flow Index) in that slot. CMF ≠ MFI — different indicators. When `predict_price_movement(stock_data)` is called with a dict, the 8th volume feature is 0 (default) instead of MFI, producing a misaligned feature vector vs. the trained model. | Change line 178 to `self._safe_float(stock_data.get('enhanced_mfi', 50))` to match `train_ml_model`; or add CMF computation to `train_ml_model` and keep predictor as-is. Prefer aligning with trainer since pipeline uses `predict_from_ohlcv`. |

### 1.2 MEDIUM — Probability Index Assumption (predict_proba)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 282-285 | **MEDIUM** | `probabilities` dict assumes `probabilities[0]=DOWN, [1]=HOLD, [2]=UP`. sklearn sorts classes, so for labels `-1, 0, 1` the order is correct. If the model is retrained with different labels, the mapping could break. No validation of `model.classes_` is performed. | Add assertion: `assert list(self.model.classes_) == [-1, 0, 1]` at load/predict, or map by `model.classes_` dynamically. |

### 1.3 HIGH — Fallback Receives Empty Dict from predict_from_ohlcv

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 306, 316, 318 | **HIGH** | When `predict_from_ohlcv` fails (no hist, model not trained, features None, exception), it calls `_get_fallback_prediction({})` with an empty dict. Fallback expects `real_rsi`, `real_macd_signal`, `real_momentum`, `volume_trend` — all missing, so fallback uses defaults (RSI=50, etc.) and produces generic HOLD. | Compute simple RSI/MACD from `hist` when available and pass a minimal dict to fallback; or compute inside fallback when `stock_data` is empty and `hist` is in scope. |

### 1.4 HIGH — Scaler Transform on Unseen Features

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 261 | **HIGH** | `self.scaler.transform(features.reshape(1, -1))` is called. If `prepare_features` returns a vector with different statistics than training (e.g., many zeros from missing dict keys), the scaled values can be extreme. `np.nan_to_num` caps Inf but not necessarily extreme scaled values. | Ensure `prepare_features` dict path produces values in similar ranges to `build_features_from_hist`, or reject dict-based prediction when critical fields are missing. |

### 1.5 MEDIUM — Data Contract Mismatches (prepare_features)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 135-216 | **MEDIUM** | Pipeline provides: `current_price`, `pe_ratio`, `roe`, `debt_to_equity`, `real_rsi`, `enhanced_rsi_14`, `enhanced_macd`, `enhanced_signal_line`, `enhanced_volume_ratio`, `enhanced_adx`, `enhanced_price_change_5d/20d/50d`, `sma_50`, `52_week_high`, `52_week_low`, `volume_trend`, `sector`. Many features in `prepare_features` are NOT provided: `enhanced_bb_position`, `enhanced_bb_width`, `enhanced_atr_14`, `enhanced_cci`, `enhanced_stoch_k/d`, `enhanced_williams_r`, `enhanced_roc`, `enhanced_mfi`, `enhanced_obv_trend`, `enhanced_vwap_distance`, `ma_20/50/200`, `enhanced_price_change_1d`, `price_momentum_5d/20d`, `volatility_20d/6m`, `enhanced_high_low_range`, `enhanced_volume_trend`, `volume_spike`, `avg_volume`, `volume_ma_ratio`, `enhanced_obv`, `enhanced_cmf`, and all fundamental/sentiment/MTF fields. These default to 0/50, producing a very different vector than training. | Document that `predict_price_movement(stock_data)` requires a fully populated dict matching `build_features_from_hist` schema, or deprecate dict path in favor of `predict_from_ohlcv`. |

### 1.6 MEDIUM — Division by Zero (prepare_features)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 165 | **MEDIUM** | `current_price / max(self._safe_float(stock_data.get('52_week_high', current_price)), 1)` — if `current_price` is 0 and `52_week_high` is 0, `max(..., 1)` yields 1, so 0/1=0. Safe. But if `52_week_high` is negative (data error), `max(negative, 1)=1`, still safe. No bug. | None. |

### 1.7 LOW — Duplicate train_test_split Import

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 71 | **LOW** | `from sklearn.model_selection import train_test_split` is imported inside `train_model`; it is already imported at top (line 12). | Remove the inner import. |

### 1.8 LOW — Fallback Uses Non-Pipeline Keys

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 347-350 | **LOW** | Fallback uses `real_macd_signal`, `real_momentum`, `real_volume_trend`. Pipeline provides `volume_trend` (not `real_volume_trend`). If dict is from pipeline, these keys may be missing. | Use `stock_data.get('volume_trend', stock_data.get('real_volume_trend', 'AVERAGE'))` for volume. |

---

## 2. sentiment_analyzer.py

### 2.1 MEDIUM — NaN in returns (pct_change)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 117-119 | **MEDIUM** | `returns = hist['Close'].pct_change()` produces NaN for first row. `(recent_returns > 0.01).sum()` and `(recent_returns < -0.01).sum()` treat NaN as False. If `hist` has < 21 rows, `recent_returns.tail(20)` may have many NaNs; `positive_days` and `negative_days` can be low, and `momentum_score = (positive_days - negative_days) / 20 * 100` is still valid. | Add check: `if len(hist) < 21: return {'score': 50, 'signal': 'NEUTRAL', ...}` to avoid sparse data. |

### 2.2 MEDIUM — recommendations['To Grade'] KeyError

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 165-166 | **MEDIUM** | `recent_recs['To Grade']` — yfinance may use different column names (e.g. `To Grade` vs `ToGrade`). If column is missing, KeyError. | Use `recent_recs.columns` to find grade column, or wrap in try/except and fallback to PE proxy. |

### 2.3 MEDIUM — earnings Structure Assumption

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 278-283 | **MEDIUM** | `earnings['Earnings']` and `earnings.iloc[-1]` — yfinance `earnings` structure varies (quarterly vs annual). Accessing `['Earnings']` may fail. | Check `'Earnings' in earnings.columns` and handle missing structure. |

### 2.4 MEDIUM — adjust_score_by_sentiment KeyError

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 399 | **MEDIUM** | `sentiment_data['overall_sentiment']` — if `sentiment_data` is malformed or from a different version, KeyError. | Use `sentiment_data.get('overall_sentiment', 'NEUTRAL')`. |

### 2.5 LOW — Data Contract

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 232 | **LOW** | `_analyze_market_sentiment` uses `stock_data.get('real_rsi', 50)`. Pipeline provides `real_rsi`. OK. | None. |

---

## 3. volume_analyzer.py

### 3.1 HIGH — Division by Zero (VWAP Slope)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 164 | **HIGH** | `vwap_slope = (data['vwap'].iloc[-1] - data['vwap'].iloc[-10]) / data['vwap'].iloc[-10]` — if `data['vwap'].iloc[-10]` is 0 (e.g. zero prices), division by zero. | Add: `vwap_denom = data['vwap'].iloc[-10]; vwap_slope = (...) / vwap_denom if vwap_denom and vwap_denom > 0 else 0` |

### 3.2 HIGH — Division by Zero (distance_pct)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 154 | **HIGH** | `distance_pct = ((current_price - current_vwap) / current_vwap) * 100` — if `current_vwap` is 0, division by zero. | Add: `if current_vwap <= 0: distance_pct = 0` before division. |

### 3.3 MEDIUM — Empty DataFrame / Short Data

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 54 | **MEDIUM** | `if stock_data is None or len(stock_data) < 20` — good. But `_calculate_vwap_zones` assumes at least 10 rows for `iloc[-10]`. If `len(data) < 10`, `iloc[-10]` can index before start. | Add guard in `_calculate_vwap_zones`: `if len(data) < 10: return {...}` with safe defaults. |

### 3.4 MEDIUM — volume_profile Shape (profile_mean == 0)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 354-356 | **MEDIUM** | `if profile_mean == 0: shape = 'NORMAL'` — when all volume is 0, `profile_mean` is 0. Correct. But `profile_std / profile_mean` when `profile_mean > 0` — if `profile_std` is NaN (e.g. single bin), can cause issues. | Add `if np.isnan(profile_std) or profile_mean == 0: shape = 'NORMAL'` before division. |

### 3.5 MEDIUM — adjust_score_by_volume Key Mismatch

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 441-445 | **MEDIUM** | `adjust_score_by_volume` looks for `vwap_position`, `flow_direction`, `institutional_activity`. Volume analysis returns `vwap_position` (from `vwap_data['position']`), `flow_direction` (from `flow_data['direction']`), `institutional_activity` (from `blocks_data['activity_level']`). Keys match. | None. |

### 3.6 MEDIUM — IndexError (volume_profile)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 361-362 | **MEDIUM** | `volume_profile.iloc[0] > volume_profile.iloc[1] * 2` — if `volume_profile` has only 1 bin (e.g. flat price), `iloc[1]` raises IndexError. | Add `if len(volume_profile) < 2: shape = 'NORMAL'` before the comparison. |

### 3.7 LOW — pd.cut with Equal Bins

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 321 | **LOW** | `if price_min >= price_max or price_max == 0` returns empty profile. Good. | None. |

---

## 4. pattern_recognition.py

### 4.1 HIGH — Division by Zero (shoulder_diff)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 82, 146 | **HIGH** | `shoulder_diff = abs(left_shoulder - right_shoulder) / left_shoulder` — if `left_shoulder` is 0, division by zero. Stock prices are rarely 0 but possible (delisting, data error). | Use `shoulder_diff = abs(left_shoulder - right_shoulder) / (left_shoulder + 1e-9)` or `if left_shoulder <= 0: continue`. |

### 4.2 HIGH — Division by Zero (peak_diff, trough_diff)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 204, 262 | **HIGH** | `peak_diff = abs(first_peak - second_peak) / first_peak` and `trough_diff = abs(first_trough - second_trough) / first_trough` — same issue if `first_peak` or `first_trough` is 0. | Add small epsilon: `/ (first_peak + 1e-9)` and `/ (first_trough + 1e-9)`. |

### 4.3 MEDIUM — Division by Zero (detect_flag, detect_cup_and_handle)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 288, 331 | **MEDIUM** | `price_range / recent_prices.mean() < 0.03` and `handle_depth = (handle_high - handle_low) / handle_high` — if mean or handle_high is 0, division by zero. | Add guards: `if recent_prices.mean() <= 0: return {...}`; `if handle_high <= 0: skip`. |

### 4.5 LOW — get_pattern_score Normalization

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 393-396 | **LOW** | `bullish_score = bullish_score / total` — when `total > 0`, OK. When both scores are 0, `total` is 0 and division by zero. But loop only adds when direction is bullish/bearish, so if all patterns are `neutral`, both stay 0 and `total` is 0. | Add `if total <= 0: return {...}` before division. |

### 4.6 LOW — Asymmetric Handling

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 382-386 | **LOW** | Bullish and bearish patterns are scored symmetrically. No inversion. | None. |

---

## 5. early_breakout_detector.py

### 5.1 LOW — move_5d Formula (Safe Given Guard)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 265-266 | **LOW** | `move_5d` uses `iloc[-6]`. Guard at line 227 ensures `len(df) >= 20`, so `iloc[-6]` is valid. Formula correctly computes 5-day return. | None. |

### 5.2 HIGH — Division by Zero (move_5d, distance_from_ma)

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 265, 276 | **HIGH** | `df['Close'].iloc[-6]` and `ma_20` in denominator. If close 6 days ago is 0 or ma_20 is 0, division by zero. | Use `denom = df['Close'].iloc[-6]; move_5d = (...) / (denom + 1e-9) * 100 if denom else 0`. Same for `ma_20`. |

### 5.3 HIGH — bearish_divergence (loss.replace(0, np.nan))

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 330-332 | **HIGH** | `loss_safe = loss.replace(0, np.nan); rs = gain / loss_safe` — when all `loss` values are 0 (no down days in 14 days), `rs` becomes Inf. `rsi_series = (100 - (100 / (1 + rs))).fillna(50)` — for `rs=Inf`, `1+Inf=Inf`, `100/Inf=0`, `100-0=100`. So RSI=100. Not a crash, but extreme. | Consider capping `rs` or using `np.clip` to avoid Inf in edge cases. |

### 5.4 MEDIUM — _count_support_tests Iteration

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 371-374 | **MEDIUM** | `for low in lows:` — `lows` is a Series. Iteration works. No bug. | None. |

### 5.5 MEDIUM — expected_breakout_in_days Type

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 187 | **MEDIUM** | `expected_breakout_in_days` is set to string `"1-2"`, `"1-3"`, `"2-4"` but docstring says `int`. Callers may expect int. | Document as `str` or change to `(1, 2)` tuple / enum for consistency. |

### 5.6 LOW — Data Contract

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 103, 234 | **LOW** | Uses `real_rsi`, `enhanced_rsi_14`, `risk_adjusted_score`, `overall_score_with_value`. Pipeline may provide these. | None. |

### 5.7 LOW — print Instead of logging

| Line | Severity | Description | Fix |
|------|----------|-------------|-----|
| 203, 315 | **LOW** | `print(f"Error in pre-breakout detection: {e}")` — should use `logging` for consistency. | Replace with `logging.warning(...)`. |

---

## 6. Summary by Severity

| Module | CRITICAL | HIGH | MEDIUM | LOW |
|--------|----------|------|--------|-----|
| ml_predictor.py | 1 | 2 | 3 | 2 |
| sentiment_analyzer.py | 0 | 0 | 4 | 1 |
| volume_analyzer.py | 0 | 2 | 4 | 1 |
| pattern_recognition.py | 0 | 2 | 2 | 2 |
| early_breakout_detector.py | 0 | 2 | 2 | 2 |

---

## 7. Recommended Fix Order

1. **ml_predictor.py**: Fix enhanced_cmf vs enhanced_mfi mismatch (CRITICAL).
2. **volume_analyzer.py**: Add division-by-zero guards for VWAP (HIGH).
3. **pattern_recognition.py**: Add division-by-zero guards for shoulder/peak/trough (HIGH).
4. **early_breakout_detector.py**: Add division-by-zero guards for move_5d and ma_20 (HIGH).
5. **ml_predictor.py**: Improve fallback when called from predict_from_ohlcv (HIGH).
6. **sentiment_analyzer.py**: Add KeyError/structural guards (MEDIUM).
7. **volume_analyzer.py**: Add short-data guards (MEDIUM).

---

*End of Audit Report*
