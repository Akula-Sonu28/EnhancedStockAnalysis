# Fresh Code Audit Report — Auxiliary Modules

**Date:** March 13, 2026  
**Scope:** market_regime_detector, adaptive_market_strategy, crisis_detector, recommendation_history, improved_scoring_engine, corrected_scoring_engine, run_backtest_v2, config.py

**Excluded (already fixed):** Multi-index regime, VIX weighting, ROC div-by-zero, UNKNOWN regime, adaptive quintile mapping, 52_week_high/low fallback, outcome tz normalization, fcntl locking, walk-forward backtest, adaptive price_30d_ago/sma guards, _calculate_regime_confidence sma_20 guard, run_backtest loss.replace/RSI fillna/price change guards/tz_localize.

---

## 1. market_regime_detector.py

### 1.1 [MEDIUM] _calculate_change — NaN guard on past price
**Line:** 375–384  
**Issue:** `past = df['Close'].iloc[-days]` can be NaN. Only `past == 0` is checked; `pd.isna(past)` is not. Division by NaN yields NaN, which propagates into `nifty_change_1m` / `nifty_change_3m`.  
**Fix:**
```python
if past == 0 or pd.isna(past):
    return 0.0
```

### 1.2 [LOW] _calculate_volatility_signal — NaN in volatility
**Line:** 196–207  
**Issue:** If `volatility` is all NaN (e.g. very short series), `current_vol` and `avg_vol` can be NaN. Comparisons with NaN are always False, so the logic falls through to the final `else` and returns -1.0.  
**Fix:** Add early return when volatility is invalid:
```python
if pd.isna(current_vol) or pd.isna(avg_vol) or avg_vol <= 0:
    return 0.0  # Neutral when volatility data invalid
```

### 1.3 [LOW] adjust_stock_score_by_regime — direct dict access
**Line:** 399  
**Issue:** `regime_data['regime_strength']` uses direct access. If `regime_data` is malformed, this can raise KeyError.  
**Fix:** Use `.get()` with default:
```python
'regime_context': f"{regime} market ({regime_data.get('regime_strength', 'UNKNOWN')})"
```

**Status:** Otherwise clean. Divisions guarded, returns consistent.

---

## 2. adaptive_market_strategy.py

### 2.1 [HIGH] generate_regime_specific_recommendations — empty stocks_scores
**Line:** 229–230  
**Issue:** `scores = [score for _, score in sorted_stocks]` and `np.percentile(scores, [20, 40, 60, 80])` run when `stocks_scores` may be empty. `np.percentile([], [20, 40, 60, 80])` raises.  
**Fix:** Guard at the start of the function:
```python
if not stocks_scores:
    return {
        'market_regime': current_regime,
        'regime_performance': regime_data,
        'strategy': regime_data['strategy'],
        'positions': [],
        'portfolio_allocation': {},
        'risk_management': {}
    }
```

**Status:** Otherwise clean. price_30d_ago, sma_20, sma_50, and _calculate_regime_confidence are guarded.

---

## 3. crisis_detector.py

**Status:** Clean. All divisions guarded (yesterday != 0, avg5 > 0). Dict access uses `.get()` with defaults. No issues found.

---

## 4. recommendation_history.py

### 4.1 [MEDIUM] check_cooldown_period — invalid date handling
**Line:** 166–167  
**Issue:** `last_date = pd.to_datetime(last_rec.get('date'))` can be NaT if the date is missing or invalid. `(datetime.now() - last_date).days` then fails because NaT has no `.days`.  
**Fix:**
```python
last_date = pd.to_datetime(last_rec.get('date'))
if pd.isna(last_date) or last_date is None:
    return True, ""  # Invalid history, allow action
days_since = (datetime.now() - last_date).days
```

### 4.2 [LOW] check_score_change — NaN in last_score
**Line:** 207–209  
**Issue:** `last_score = last_rec.get('score', 0)` can be NaN from `to_dict()` when the CSV has empty/NaN score. `score_change = current_score - last_score` becomes NaN; `abs(score_change) >= threshold` is False.  
**Fix:**
```python
last_score = last_rec.get('score', 0)
if pd.isna(last_score):
    last_score = 0
```

### 4.3 [LOW] _save_history — makedirs with empty dirname
**Line:** 64  
**Issue:** `os.makedirs(os.path.dirname(self.history_file), exist_ok=True)` with `history_file='recommendation_history.csv'` gives `dirname=''`. `os.makedirs('', exist_ok=True)` can raise on some systems.  
**Fix:**
```python
dir_path = os.path.dirname(self.history_file)
if dir_path:
    os.makedirs(dir_path, exist_ok=True)
```

**Status:** Outcome tracking and fcntl locking are already fixed.

---

## 5. improved_scoring_engine.py

**Status:** Clean. Divisions guarded (pe_ratio > 0, pb_ratio > 0). Dict access uses `.get()` with defaults. Try/except around float conversions. Scores clamped to [0, 100]. No issues found.

---

## 6. corrected_scoring_engine.py

**Status:** Clean. 52_week_high/year_high <= 0 and year_high > year_low guards are in place. Divisions guarded. Try/except around conversions. No issues found.

---

## 7. run_backtest_v2.py

### 7.1 [MEDIUM] run_backtest — start_price division guard
**Line:** 146, 156  
**Issue:** `actual_return = (end_price - start_price) / start_price * 100` has no guard for `start_price == 0` or `pd.isna(start_price)`. Unlikely for real prices but can cause inf/NaN or division errors.  
**Fix:** Before computing return:
```python
if start_price == 0 or pd.isna(start_price):
    continue
```

### 7.2 [MEDIUM] WalkForwardBacktest.run — same start_price guard
**Line:** 293, 295  
**Issue:** Same as 7.1.  
**Fix:** Same guard before computing `actual_return`.

### 7.3 [LOW] prepare_stock_data — denominator NaN guards
**Line:** 215–218  
**Issue:** `_denom_22` and `_denom_6` can be NaN. The check `_denom_22 != 0` does not catch NaN; `NaN != 0` is True, so division runs and yields NaN.  
**Fix:**
```python
price_change_1m = ((current_price / _denom_22 - 1) * 100) if (len(close) > 22 and _denom_22 != 0 and not pd.isna(_denom_22)) else 0
price_change_1w = ((current_price / _denom_6 - 1) * 100) if (len(close) > 6 and _denom_6 != 0 and not pd.isna(_denom_6)) else 0
```

### 7.4 [LOW] prepare_stock_data — vol_sma_20 NaN
**Line:** 222  
**Issue:** `vol_sma_20` can be NaN (e.g. short history). `if vol_sma_20` is True for NaN, so `volume.iloc[-1] / vol_sma_20` yields NaN.  
**Fix:**
```python
vol_ratio = volume.iloc[-1] / vol_sma_20 if (vol_sma_20 and not np.isnan(vol_sma_20)) else 1.0
```

**Status:** RSI fillna(50), loss.replace(0, np.nan), and tz_localize are already fixed.

---

## 8. config.py

**Status:** Clean. No divisions, no risky dict access, no float conversions. Dataclass defaults and directory creation are safe. No issues found.

---

## Summary

| File                      | High | Medium | Low |
|---------------------------|------|--------|-----|
| market_regime_detector    | 0    | 1      | 2   |
| adaptive_market_strategy  | 1    | 0      | 0   |
| crisis_detector           | 0    | 0      | 0   |
| recommendation_history    | 0    | 1      | 2   |
| improved_scoring_engine   | 0    | 0      | 0   |
| corrected_scoring_engine  | 0    | 0      | 0   |
| run_backtest_v2           | 0    | 2      | 2   |
| config.py                 | 0    | 0      | 0   |

**Total:** 1 High, 4 Medium, 6 Low.
