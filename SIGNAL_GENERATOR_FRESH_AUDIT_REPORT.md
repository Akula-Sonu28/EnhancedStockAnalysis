# Signal Generator Modules — Fresh Code Audit Report

**Date:** 2025-03-13  
**Scope:** `ml_predictor.py`, `sentiment_analyzer.py`, `volume_analyzer.py`, `pattern_recognition.py`, `early_breakout_detector.py`  
**Excluded (already fixed):** VWAP cumsum/ffill, current_vwap guard, vwap_slope base, volume profile single-bin guard, volume score clamp, MODERATE sell, pattern zero-price guards, cup-and-handle guards, flag _flag_mean==0, triangle slopes, early breakout guards, ML probabilities IndexError, sentiment RSI/To Grade/overall_sentiment.

---

## Summary

| File | Status | Issues Found |
|------|--------|--------------|
| `ml_predictor.py` | ✅ **CLEAN** | 0 |
| `sentiment_analyzer.py` | ⚠️ Issues | 4 |
| `volume_analyzer.py` | ⚠️ Issues | 1 |
| `pattern_recognition.py` | ✅ **CLEAN** | 0 |
| `early_breakout_detector.py` | ✅ **CLEAN** | 0 |

---

## Findings

### 1. sentiment_analyzer.py — KeyError on earnings column

**Severity:** MEDIUM  
**Line:** 285–286  
**Description:** Direct access to `earnings['Earnings']` can raise `KeyError` if yfinance returns a different structure (e.g. different column names or regional variants).

**Fix:**
```python
if earnings is not None and not earnings.empty and 'Earnings' in earnings.columns and len(earnings) >= 2:
    recent_earnings = earnings['Earnings'].iloc[-1]
    previous_earnings = earnings['Earnings'].iloc[-2]
    if previous_earnings != 0 and pd.notna(previous_earnings) and pd.notna(recent_earnings):
        # ... existing earnings_growth logic
```

---

### 2. sentiment_analyzer.py — NaN in earnings growth

**Severity:** LOW  
**Line:** 288–290  
**Description:** If `previous_earnings` is NaN, `previous_earnings != 0` is True, so the block runs. `abs(previous_earnings)` is NaN, leading to `earnings_growth = NaN` and incorrect scoring.

**Fix:**
```python
if previous_earnings != 0 and pd.notna(previous_earnings) and pd.notna(recent_earnings):
    earnings_growth = (recent_earnings - previous_earnings) / abs(previous_earnings) * 100
```

---

### 3. sentiment_analyzer.py — adjust_score_by_sentiment None/NaN

**Severity:** MEDIUM  
**Line:** 464–470  
**Description:** If `composite_score` or `confidence` is `None` or NaN (e.g. from external data), `composite_score >= 75` can raise `TypeError` or produce wrong adjustments.

**Fix:**
```python
composite_score = sentiment_data.get('composite_score', 50)
confidence = sentiment_data.get('confidence', 40)
if composite_score is None or (isinstance(composite_score, (int, float)) and np.isnan(composite_score)):
    composite_score = 50
if confidence is None or (isinstance(confidence, (int, float)) and np.isnan(confidence)):
    confidence = 40
```

---

### 4. sentiment_analyzer.py — volatility NaN in _analyze_social_buzz

**Severity:** LOW  
**Line:** 358–367  
**Description:** If `returns.std()` is NaN (e.g. very short history or all-NaN), `volatility` and `volatility_score` become NaN, and `buzz_score` can be NaN.

**Fix:**
```python
volatility_raw = returns.std() * np.sqrt(252) * 100
volatility = volatility_raw if pd.notna(volatility_raw) else 0
```

---

### 5. volume_analyzer.py — Empty volume_profile IndexError/ValueError

**Severity:** HIGH  
**Line:** 331, 346  
**Description:** If all `Close` are NaN, `pd.cut` yields all-NaN bins, `groupby` excludes them, and `volume_profile` is empty. Then:
- `volume_profile.index[0]` → `IndexError`
- `value_area_bins` stays empty → `max([])` → `ValueError`

**Fix:**
```python
volume_profile = data.groupby('price_bin')['Volume'].sum().sort_values(ascending=False)
if volume_profile.empty:
    return self._empty_volume_profile(data)
# ... rest of logic
```

---

## Files With No New Issues

### ml_predictor.py
- Divisions guarded (e.g. `max(..., 1)` for 52_week_high)
- `_safe_float` handles None, str, int, float
- `prepare_features` validates length and NaN/Inf
- Probabilities access guarded with `len(probabilities) > n`
- Fallback prediction uses `.get()` with defaults

### pattern_recognition.py
- Zero-price guards for H&S, double top/bottom, cup-and-handle, flag
- Triangle slopes normalized by price
- `find_peaks_and_troughs` handles empty input
- `get_pattern_score` handles empty patterns

### early_breakout_detector.py
- `current_price <= 0` guard
- `move_5d` and `ma_20` division guards
- Consolidation `mean_p` guard
- `len(df)` checks before `iloc` access

---

## Recommended Fix Order

1. **volume_analyzer.py** — Add empty `volume_profile` guard (HIGH)
2. **sentiment_analyzer.py** — Add `composite_score`/`confidence` None/NaN handling (MEDIUM)
3. **sentiment_analyzer.py** — Add `earnings['Earnings']` column check (MEDIUM)
4. **sentiment_analyzer.py** — Add `previous_earnings` NaN check (LOW)
5. **sentiment_analyzer.py** — Add volatility NaN guard (LOW)
