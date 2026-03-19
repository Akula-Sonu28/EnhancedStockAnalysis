# FINAL EXHAUSTIVE AUDIT: All 5 Signal Generator Modules

**Date:** 2025-03-13  
**Scope:** ml_predictor.py, sentiment_analyzer.py, volume_analyzer.py, pattern_recognition.py, early_breakout_detector.py

---

## 1. ml_predictor.py

### ✅ CLEAN (no new issues)

**Already fixed:** VWAP/volume profile guards, ML probabilities IndexError guard, score clamping.

**Verified safe:**
- **Division:** Line 166 `current_price / max(..., 1)` — denominator guarded by `max(..., 1)`.
- **Dict access:** All `stock_data.get()` use defaults; `data.get()` in pickle load.
- **Index access:** `probabilities[0/1/2]` guarded with `len(probabilities) > N` checks (lines 285-287, 334-336).
- **Float conversion:** `_safe_float()` handles None, str, int, float; `float(np.max(probabilities)*100)` safe.
- **Return:** `_get_fallback_prediction` always returns full dict; `predict_price_movement`/`predict_from_ohlcv` return fallback on exception.
- **Empty data:** `len(hist) < 60` returns fallback before any processing.
- **Exception handlers:** Broad `Exception` catch is appropriate for pickle/model failures.

**Cross-module:** Callers (analyze_top200) expect `prediction`, `confidence`, `signal`, `expected_return`, `probabilities` — all present. Fallback returns `probabilities: {}`; caller uses `ml_results.get('probabilities', {})` — safe.

---

## 2. sentiment_analyzer.py

### ✅ MOSTLY CLEAN

**Already fixed:** RSI explicit None check, To Grade dynamic column, overall_sentiment .get(), composite/confidence NaN guard, earnings column resolution, buzz volatility/momentum dropna.

**Verified safe:**
- **Division:** `avg_volume > 0`, `older_volume > 0`, `handle_high != 0`, `previous_earnings != 0` guards in place.
- **iloc:** `hist.empty` checked at entry; `ma_20 = rolling(20).mean().iloc[-1]` — when hist has <20 rows, ma_20 is NaN; `ma_20 > 0` is False → use 0.
- **Dict access:** `.get()` with defaults throughout; `signal_map.get(s, 0)` handles unknown/None.
- **String ops:** `str(macd_signal).upper()`, `str(momentum).upper()` — safe for non-str (converts first).
- **adjust_score_by_sentiment:** composite_score/confidence NaN/None guard at lines 364-367.

### ⚠️ MINOR: Final composite_score NaN propagation

**Location:** `analyze_sentiment()` return (lines 94-106)

**Issue:** If any sub-component (`news_sentiment`, `market_sentiment`, etc.) returns a score that is NaN (e.g. edge-case in `_analyze_market_sentiment` with very short hist), `composite_score` can be NaN. The `adjust_score_by_sentiment` caller has a guard, but the raw `analyze_sentiment` return could contain `sentiment_composite_score: nan`.

**Recommendation:** Add a final sanitization before return:
```python
composite_score = float(composite_score) if not (composite_score is None or (isinstance(composite_score, float) and np.isnan(composite_score))) else 50.0
```

**Severity:** Low — adjust_score_by_sentiment already guards; other consumers may not.

---

## 3. volume_analyzer.py

### ✅ CLEAN (no new issues)

**Already fixed:** VWAP cumsum replace(0,nan)+ffill, current_vwap/vwap_slope 0 guards, volume profile empty/single-bin guards.

**Verified safe:**
- **Division:** `vol_cumsum` handled; `total_vol > 0`, `total_volume > 0`, `profile_mean == 0`, `nearest_zone` from filtered positive levels; `_vwap_base` 0-guard.
- **iloc:** `len(data) >= 20` at entry; `iloc[-1]`, `iloc[-10]` safe; exception handler uses `len(data) > 0` before `iloc[-1]`.
- **volume_profile:** Empty guard, zero-volume filter, single-bin case — all handled.
- **zone_distance_pct:** When `all_levels` empty, `nearest_zone = current_price`, `zone_distance_pct = 0`; when non-empty, levels filtered to `> 0`.
- **Dict access:** All component dicts built explicitly; `.get()` in `adjust_score_by_volume`.

---

## 4. pattern_recognition.py

### ✅ CLEAN (no new issues)

**Already fixed:** H&S/double-top/bottom/cup-handle/flag zero guards, triangle slopes normalized.

**Verified safe:**
- **Division:** `left_shoulder == 0`/`head == 0`/`first_peak == 0`/`first_trough == 0` continue; `avg_peak`/`avg_trough` 0→1.0; `handle_high != 0`; `_flag_mean == 0` early return; `len(recent_peaks/troughs) >= 2`.
- **iloc:** All indices from `argrelextrema` or validated ranges; `prices.iloc[-1]` after `len` checks.
- **detect_cup_and_handle:** When `handle_prices` is empty (df 40–59 rows), `handle_high`/`handle_low` are NaN → `handle_depth` is NaN → `handle_depth < 0.15` short-circuits to False → `handle_prices.iloc[-1]` never evaluated. Safe.
- **detect_flag:** `_flag_mean == 0` returns early.
- **get_pattern_score:** `total > 0` before division; `.get('confidence', 0.5)`, `.get('direction', 'neutral')`.

### 📝 Note

`analyze_patterns(df)` has no empty-df guard; caller (analyze_top200) checks `not hist.empty and len(hist) > 30` before calling. Contract is caller’s responsibility.

---

## 5. early_breakout_detector.py

### ✅ MOSTLY CLEAN

**Already fixed:** current_price<=0, move_5d/ma_20/consolidation mean_p guards.

**Verified safe:**
- **Division:** `_price_5d_ago != 0` else 1.0; `ma_20 != 0` else 1.0; `_mean_p != 0` in consolidation; `entry_price > 0` for profit_pct.
- **iloc:** `len(df) >= 20` (exhaustion) or `>= 30` (pre-breakout) at entry; `iloc[-6]`, `iloc[-10]` valid.
- **RSI:** `stock_data.get('real_rsi', stock_data.get('enhanced_rsi_14', 50))` — no explicit None check, but 50 default covers missing.
- **_check_bearish_divergence:** `loss.replace(0, np.nan)`; `rs = gain / loss_safe`; `fillna(50)` handles all-NaN.

### ⚠️ MINOR: NaN in resistance/support from quantile

**Location:** `_calculate_dynamic_levels()` (lines 318-329), used by `detect_pre_breakout_setup`

**Issue:** If `df['High']` or `df['Low']` contain all-NaN or produce NaN from `quantile(0.90)`/`quantile(0.10)`, `resistance` and `support` can be NaN. Then:
- `distance_to_resistance = ((resistance - current_price) / current_price) * 100` → NaN
- `2 <= NaN <= 4` is False, so no breakout detection
- But `entry_range`, `stop_loss`, `target_price` use `resistance`/`support` and would be NaN in the returned dict

**Recommendation:** Guard in `_calculate_dynamic_levels`:
```python
resistance = float(highs.quantile(0.90))
support = float(lows.quantile(0.10))
if np.isnan(resistance) or np.isnan(support) or resistance <= 0 or support <= 0:
    resistance = float(df['Close'].iloc[-1] * 1.02)  # fallback
    support = float(df['Close'].iloc[-1] * 0.98)
return resistance, support
```

**Severity:** Low — requires bad/missing OHLC data.

### ⚠️ MINOR: move_5d NaN when _price_5d_ago is NaN

**Location:** `detect_momentum_exhaustion` line 264

**Issue:** `_price_5d_ago = df['Close'].iloc[-6] if df['Close'].iloc[-6] != 0 else 1.0`. If `iloc[-6]` is NaN, `NaN != 0` is True → `_price_5d_ago = NaN`. Then `move_5d = ((current_price - NaN) / NaN) * 100 = NaN`. `move_5d > 20` and `move_5d > 15` are both False, so no crash, but logic is fragile.

**Recommendation:** Add NaN guard:
```python
_price_5d_ago = df['Close'].iloc[-6]
if _price_5d_ago is None or (isinstance(_price_5d_ago, float) and np.isnan(_price_5d_ago)) or _price_5d_ago == 0:
    _price_5d_ago = 1.0
move_5d = ((current_price - _price_5d_ago) / _price_5d_ago) * 100
```

**Severity:** Low — no crash, only missed parabolic signal.

---

## 6. Cross-Module Contracts

| Module              | Return keys used by analyze_top200                         | Status   |
|---------------------|------------------------------------------------------------|----------|
| ml_predictor        | prediction, confidence, signal, expected_return, probabilities | ✅ All present |
| sentiment_analyzer   | composite_score, confidence, overall_sentiment, news/analyst/market/earnings/buzz_sentiment | ✅ All present |
| volume_analyzer     | volume_composite_score, volume_signal, volume_confidence, vwap_*, flow_*, etc. | ✅ All present |
| pattern_recognition | patterns, score (bullish_score, bearish_score, dominant_signal, confidence) | ✅ All present |
| early_breakout      | pre_breakout_detected, exhaustion_detected, signals, etc.  | ✅ All present |

---

## 7. Exception Handlers

All five modules use `try/except Exception` appropriately. No over-catch of `KeyboardInterrupt` or `SystemExit`. Logging before re-raise or fallback is consistent.

---

## 8. Summary

| File                 | Status   | New issues |
|----------------------|----------|------------|
| ml_predictor.py      | ✅ Clean | 0          |
| sentiment_analyzer.py| ✅ Clean | 1 minor (composite NaN) |
| volume_analyzer.py   | ✅ Clean | 0          |
| pattern_recognition.py | ✅ Clean | 0        |
| early_breakout_detector.py | ✅ Clean | 2 minor (quantile NaN, move_5d NaN) |

**Total new issues:** 3 minor (all low severity, no crashes).
