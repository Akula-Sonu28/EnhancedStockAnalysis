# AUXILIARY MODULES — FINAL EXHAUSTIVE AUDIT REPORT

**Scope:** market_regime_detector.py, adaptive_market_strategy.py, crisis_detector.py, improved_scoring_engine.py, corrected_scoring_engine.py, run_backtest_v2.py, config.py, recommendation_history.py

**Exclusions (already fixed):** Multi-index regime, VIX dynamic weighting, ROC div-by-zero, _calculate_change guard, _calculate_volatility_signal NaN guard, regime_strength .get(), UNKNOWN regime handler, adaptive quintile/price_30d/sma guards, corrected engine 52w fallback, outcome tracking tz, fcntl locking, walk-forward backtest, backtest loss.replace/RSI fillna, _denom guards, vol_sma_20 guard, start_price guard, tz_localize conditional in run_backtest, recommendation history NaT cooldown guard (check_cooldown_period only), tz normalization (partial).

---

## REAL ISSUES (with exact line numbers)

### 1. run_backtest_v2.py — Line 286

**Issue:** `tz_localize(None)` on a naive DatetimeIndex raises `TypeError`.

**Code:**
```python
idx = hist.index.tz_localize(None)
```

**Problem:** If `hist.index` is already naive (`tz is None`), `tz_localize(None)` raises `TypeError: Cannot localize tz-naive timestamps`.

**Fix:** Use the same conditional as line 133:
```python
idx = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
```

---

### 2. recommendation_history.py — Lines 84, 92, 114 (update_outcomes)

**Issue:** `rec_date` can be NaT; `(now - rec_date).days` then fails.

**Code:**
```python
rec_date = pd.to_datetime(row['date'])
# ...
if pd.isna(row.get(col_price)) and (now - rec_date).days >= days:
```

**Problem:** If `row['date']` is NaT or invalid, `rec_date` is NaT. `(now - rec_date).days` raises `AttributeError` (NaT has no `.days`).

**Fix:** Add guard at start of loop body:
```python
rec_date = pd.to_datetime(row['date'], errors='coerce')
if pd.isna(rec_date):
    continue
```

Also normalize timezone for comparison with naive `hist.index`:
```python
if hasattr(rec_date, 'tzinfo') and rec_date.tzinfo is not None:
    rec_date = rec_date.tz_localize(None)
```

---

### 3. recommendation_history.py — Lines 342–346 (validate_recommendation)

**Issue:** `last_date` can be NaT; no tz normalization before `datetime.now() - last_date`.

**Code:**
```python
last_date = pd.to_datetime(last_rec.get('date'))
days_since = (datetime.now() - last_date).days
```

**Problem:** If `last_rec['date']` is NaT, `(datetime.now() - last_date).days` fails. If `last_date` is timezone-aware, comparison with naive `datetime.now()` can raise.

**Fix:**
```python
last_date = pd.to_datetime(last_rec.get('date'), errors='coerce')
if pd.isna(last_date):
    # skip days_since block or use default
    continue  # or handle appropriately
if hasattr(last_date, 'tzinfo') and last_date.tzinfo is not None:
    last_date = last_date.tz_localize(None)
days_since = (datetime.now() - last_date).days
```

---

### 4. recommendation_history.py — Lines 447, 485 (get_flip_flop_stocks, generate_stability_report)

**Issue:** `(date1 - date2).days` fails when either date is NaT.

**Code (line 447):**
```python
days_between = (dates[i+1] - dates[i]).days
```

**Code (line 485):**
```python
days = (symbol_recs.iloc[i+1]['date'] - symbol_recs.iloc[i]['date']).days
```

**Problem:** If either date is NaT, the subtraction yields NaT and `.days` raises `AttributeError`.

**Fix:** Guard before using `.days`:
```python
d1, d2 = dates[i+1], dates[i]
if pd.isna(d1) or pd.isna(d2):
    continue  # or skip this flip-flop
days_between = (d1 - d2).days
```

Same pattern for line 485.

---

### 5. market_regime_detector.py — Line 296 (_get_vix_level)

**Issue:** `vix_data['Close'].iloc[-1]` can be NaN and is returned as-is.

**Code:**
```python
return vix_data['Close'].iloc[-1]
```

**Problem:** NaN propagates into `vix_level`, affecting `vix > 25`, `vix < 12`, etc. Comparisons with NaN are False, but downstream logic may expect a valid float.

**Fix:**
```python
val = float(vix_data['Close'].iloc[-1])
return val if not (np.isnan(val) or np.isinf(val)) else 15.0
```

---

### 6. adaptive_market_strategy.py — Line 233 (generate_regime_specific_recommendations)

**Issue:** `np.percentile(scores, [20, 40, 60, 80])` with NaN in `scores` yields NaN thresholds.

**Code:**
```python
scores = [score for _, score in sorted_stocks]
quintile_thresholds = np.percentile(scores, [20, 40, 60, 80])
```

**Problem:** If any `score` is NaN, `quintile_thresholds` can contain NaN. Comparisons like `score >= quintile_thresholds[3]` then behave unpredictably (all False for NaN).

**Fix:** Filter NaN before percentile:
```python
scores = [s for _, s in sorted_stocks if isinstance(s, (int, float)) and not np.isnan(s)]
if not scores:
    recommendations['positions'] = []
    return recommendations
quintile_thresholds = np.percentile(scores, [20, 40, 60, 80])
```

---

### 7. recommendation_history.py — Line 64 (_save_history)

**Issue:** `os.makedirs(os.path.dirname(self.history_file), exist_ok=True)` can fail when `history_file` has no directory.

**Code:**
```python
os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
```

**Problem:** If `history_file` is e.g. `'recommendation_history.csv'`, `dirname` is `''`. `os.makedirs('', exist_ok=True)` may raise on some systems.

**Fix:**
```python
parent = os.path.dirname(self.history_file)
if parent:
    os.makedirs(parent, exist_ok=True)
```

---

## ADDITIONAL OBSERVATIONS (lower priority)

### adaptive_market_strategy.py — Lines 335–337

**File I/O:** `open(config_filename, 'w')` has no try/except. Write failures (permissions, disk full) will propagate. Consider wrapping in try/except for clearer error handling.

### config.py — Line 90

**Directory creation:** `os.makedirs(directory, exist_ok=True)` can raise on permission errors. Typically acceptable at startup; optional try/except if robustness is desired.

### crisis_detector.py

**Status:** No issues found. Divisions guarded, `.get()` used for dict access, NaN handled in VIX spike calculation.

### improved_scoring_engine.py

**Status:** No issues found. NaN checks via `pd.notna()` are in place.

### corrected_scoring_engine.py

**Status:** No issues found. `year_high > year_low` avoids division by zero; `year_high <= 0` fallback is present.

---

## SUMMARY

| File                     | Critical | Line(s) | Issue                                      |
|--------------------------|----------|---------|--------------------------------------------|
| run_backtest_v2.py       | Yes      | 286     | tz_localize on naive index                 |
| recommendation_history.py| Yes      | 84, 92, 114 | rec_date NaT in update_outcomes         |
| recommendation_history.py| Yes      | 342–346 | last_date NaT/tz in validate_recommendation |
| recommendation_history.py| Yes      | 447, 485 | NaT in date subtraction .days            |
| market_regime_detector.py| Yes      | 296     | VIX can return NaN                         |
| adaptive_market_strategy.py | Yes   | 233     | NaN in scores → percentile                |
| recommendation_history.py| Medium   | 64      | makedirs with empty dirname                |

**Total: 7 distinct fix locations across 4 files.**
