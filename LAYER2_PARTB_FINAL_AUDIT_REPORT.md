# LAYER 2 — Part B: Signal Generators & Market Context — EXHAUSTIVE FINAL AUDIT REPORT

**Scope:** ml_predictor.py, sentiment_analyzer.py, volume_analyzer.py, pattern_recognition.py, early_breakout_detector.py, market_regime_detector.py, adaptive_market_strategy.py, crisis_detector.py, recommendation_history.py, run_backtest_v2.py

**Audit Date:** March 13, 2026

---

## SUMMARY

**Status:** 5 NEW ISSUES FOUND (below). All previously fixed items per ALREADY FIXED list were verified and remain correctly addressed.

---

## NEW ISSUES (Exact Line Numbers)

### 1. crisis_detector.py — Line 296

**Issue:** `symbol.upper()` — unsafe if `symbol` is `None` (AttributeError).

**Check:** `.lower()/.upper()/.strip()` safe from None?

**Fix:**
```python
symbol_upper = (symbol or '').upper().replace('.NS', '').strip()
```

---

### 2. volume_analyzer.py — Line 167

**Issue:** `_vwap_base` — if `data['vwap'].iloc[-10]` is `np.nan`, `np.nan != 0` is True, so `_vwap_base` becomes NaN. Division at line 168 yields NaN; comparisons at 169–171 are False, so trend falls back to 'NEUTRAL'. Add explicit NaN guard for robustness.

**Check:** NaN truthiness / division denominator guarded?

**Fix:**
```python
_vwap_val = data['vwap'].iloc[-10]
_vwap_base = 1.0 if (pd.isna(_vwap_val) or _vwap_val == 0) else _vwap_val
vwap_slope = (data['vwap'].iloc[-1] - data['vwap'].iloc[-10]) / _vwap_base
```

---

### 3. volume_analyzer.py — Line 368

**Issue:** `zone_distance_pct = ((current_price - nearest_zone) / nearest_zone) * 100` — if `nearest_zone` is 0, division by zero. `nearest_zone` comes from `min(all_levels, ...)` where levels are filtered `if s > 0`, so normally positive. When `all_levels` is empty, `nearest_zone = current_price`; if `current_price == 0`, this becomes 0/0.

**Check:** Division denominator guarded against 0?

**Fix:**
```python
zone_distance_pct = ((current_price - nearest_zone) / nearest_zone) * 100 if nearest_zone and nearest_zone != 0 else 0
```

---

### 4. market_regime_detector.py — Lines 323–325

**Issue:** `_calculate_regime_stability` — `ma = ma_50.iloc[idx]` can be NaN when `idx` is near the start (rolling(50) not yet filled). `price > ma` with NaN yields False, so the branch always appends 'DOWN'. This can misclassify regime stability.

**Check:** NaN guards in comparisons?

**Fix:**
```python
price = close.iloc[idx]
ma = ma_50.iloc[idx]
if pd.isna(ma) or pd.isna(price):
    continue
recent_trend.append('UP' if price > ma else 'DOWN')
```

---

### 5. market_regime_detector.py — Lines 318–320

**Issue:** `adjust_stock_score_by_regime` — direct dict access `regime_data['regime']`, `regime_data['regime_score']`, `regime_data['vix_level']`. If `regime_data` is None or missing keys (e.g. malformed input), KeyError/TypeError.

**Check:** Dict access with `.get()` and default?

**Fix:**
```python
regime = regime_data.get('regime', 'UNKNOWN')
regime_score = regime_data.get('regime_score', 0.0)
vix = regime_data.get('vix_level', 15.0)
```

---

## VERIFIED CLEAN (No New Issues)

| File | Status |
|------|--------|
| ml_predictor.py | Clean — fallback probabilities, _safe_float, prepare_features NaN/Inf handling, scaler/model guards |
| sentiment_analyzer.py | Clean — RSI NaN guard, To Grade column, composite_score/confidence NaN, earnings column, buzz volatility/momentum |
| pattern_recognition.py | Clean — zero-price guards, triangle slope normalization |
| early_breakout_detector.py | Clean — current_price<=0, _mean_p!=0, RSI None/NaN |
| adaptive_market_strategy.py | Clean — price_30d/sma guards, regime confidence, np.percentile NaN filter |
| recommendation_history.py | Clean — makedirs empty guard, date NaT guards, tz_localize |
| run_backtest_v2.py | Clean — RSI loss.replace, tz_localize, price change denom guards, start_price guards |

---

## FILES WITH NEW ISSUES

| File | Count |
|------|-------|
| crisis_detector.py | 1 |
| volume_analyzer.py | 2 |
| market_regime_detector.py | 2 |

---

## RECOMMENDATION

Apply the 5 fixes above. After fixes, re-run this audit to confirm: **LAYER 2 SIGNAL & CONTEXT MODULES: CLEAN — NO NEW ISSUES**.
