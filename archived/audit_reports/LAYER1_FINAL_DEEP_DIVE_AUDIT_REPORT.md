# LAYER 1 FINAL DEEP-DIVE AUDIT REPORT

**Scope:** Data Acquisition & Enrichment — `analyze_top200_stocks_enhanced.py`, `src/technical_analyzer.py`, `src/enhanced_fundamental_analyzer.py`, `enhanced_technical_analyzer.py`

**Date:** 2025-03-13

---

## NEW ISSUES FOUND (Not in Already-Fixed List)

### 1. `src/technical_analyzer.py`

**Issue 1a — Empty DataFrame not guarded (Line 23)**  
- **Check:** `EVERY DataFrame operation — handles empty DataFrame?`  
- **Code:** `calculate_indicators(df)` — no `if df.empty or len(df) < 1` guard at start  
- **Problem:** `df['Close'].iloc[-1]` raises `IndexError` if `df` is empty  
- **Fix:** Add at start of `calculate_indicators`: `if df is None or df.empty or len(df) < 1: return None`

**Issue 1b — RSI can be NaN when roll_up is NaN (Lines 51–52)**  
- **Check:** `EVERY return value — consistent type? Can it return None unexpectedly?`  
- **Code:** `last_rs = safe_float(roll_up.iloc[-1]) / last_roll_down` then `indicators['rsi14'] = 100 - (100 / (1 + last_rs))`  
- **Problem:** If `roll_up.iloc[-1]` is NaN, `last_rs` is NaN; `100 - (100/(1+nan))` = NaN; `rsi14` propagates  
- **Fix:** Add `if pd.isna(last_rs) or last_rs is None: indicators['rsi14'] = 50` before computing rsi14, or use `else: indicators['rsi14'] = 50` when result is NaN

---

### 2. `enhanced_technical_analyzer.py`

**Issue 2 — Volume breakout: NaN price when _prev is NaN (Lines 320–322)**  
- **Check:** `EVERY float() / int() conversion — safe from None, NaN, string?`  
- **Code:** `_prev = prices.iloc[i-1]` then `price_change = ((prices.iloc[i] / _prev) - 1) * 100 if _prev != 0 else 0`  
- **Problem:** If `_prev` is NaN, `_prev != 0` is True; `(prices.iloc[i] / NaN) - 1` = NaN; `f"Volume spike: {price_change:.1f}%"` yields `"Volume spike: nan%"`  
- **Fix:** Add `if pd.isna(_prev) or _prev == 0: continue` before the price_change calculation

---

### 3. `src/enhanced_fundamental_analyzer.py`

**Issue 3 — company_name can be None (Lines 34–36)**  
- **Check:** `EVERY dict access — uses .get() with default or has KeyError guard?`  
- **Code:** `company_full_name = info.get('longName', symbol)` then `'company_name': company_full_name if company_full_name != symbol else symbol`  
- **Problem:** If key exists with value `None`, `company_full_name` is `None`; `None != symbol` is True, so `company_name` becomes `None`  
- **Fix:** `company_full_name = info.get('longName') or symbol`

---

### 4. `analyze_top200_stocks_enhanced.py`

**Issue 4a — _calculate_support_resistance: NaN propagation (Lines 3285–3305)**  
- **Check:** `EVERY DataFrame operation — handles empty DataFrame?` / `EVERY return value — consistent type?`  
- **Code:** `current_price = float(close.iloc[-1])`; if `close.iloc[-1]` is NaN, `current_price` is NaN. Then `round((current_price - support) / current_price * 100, 2)` yields NaN.  
- **Problem:** If `support` or `resistance` from `quantile()` is NaN (e.g. all-NaN candidates), or `current_price` is NaN, `support_level`, `resistance_level`, `distance_to_support`, `distance_to_resistance` can be NaN  
- **Fix:** Guard `current_price`: `current_price = float(close.iloc[-1]); current_price = 100.0 if (current_price is None or (isinstance(current_price, float) and np.isnan(current_price)) or current_price == 0 else current_price`. For support/resistance: `support = support if not (np.isnan(support) if isinstance(support, float) else False) else current_price * 0.95` (and similarly for resistance)

**Issue 4b — _calculate_momentum_indicators: ROC NaN and wrong momentum (Lines 3320–3334)**  
- **Check:** `EVERY division — is denominator guarded against 0 AND NaN?`  
- **Code:** `_denom_11 = prices.iloc[-11] if len(prices) > 11 else prices.iloc[0]`; `roc = ((prices.iloc[-1] - _denom_11) / _denom_11) * 100 if _denom_11 != 0 else 0`  
- **Problem:** If `_denom_11` is NaN, `_denom_11 != 0` is True; `(x - NaN) / NaN` = NaN; `roc` becomes NaN. All `roc >` conditions are False; `momentum` becomes `"STRONG_BEARISH"` incorrectly. `round(roc, 2)` yields NaN. Same for `ma10`/`ma50` when rolling mean is NaN.  
- **Fix:** Add `if np.isnan(roc) or (isinstance(roc, float) and np.isnan(roc)): roc = 0; momentum = "NEUTRAL"`. Sanitize `ma10`/`ma50` before return: `ma10 = ma10 if not (isinstance(ma10, float) and np.isnan(ma10)) else 0.0` (and similarly for ma50)

**Issue 4c — load_stocks_from_csv: company_names.get(symbol) can return None (Lines 301, 1488)**  
- **Check:** `EVERY dict access — uses .get() with default or has KeyError guard?`  
- **Code:** `self.company_names = dict(zip(df['Symbol'].str.strip(), df['Company Name']))`; later `self.company_names.get(symbol, symbol)`  
- **Problem:** If `Company Name` column has None/empty for a row, `company_names[symbol]` can be None; `get(symbol, symbol)` returns None when key exists. `company_name` becomes None.  
- **Fix:** Use `(self.company_names.get(symbol) or symbol)` when assigning company_name

---

## SUMMARY

| File | Issue Count |
|------|-------------|
| `src/technical_analyzer.py` | 2 |
| `enhanced_technical_analyzer.py` | 1 |
| `src/enhanced_fundamental_analyzer.py` | 1 |
| `analyze_top200_stocks_enhanced.py` | 3 |
| **Total** | **7** |

---

## ALREADY FIXED (Skipped — No Action)

- RSI: loss.replace(0, np.nan) + fillna(50)  
- Bollinger: current_middle != 0 guard  
- Volume: avg_volume != 0 and not NaN guard  
- Support/resistance: current_price != 0 guard  
- Momentum ROC: denominator != 0 guard  
- Timeframe: current_ma != 0 guards  
- FII: volume_ma.replace(0, np.nan).fillna(1.0)  
- Bulk deal: volume_std.replace(0, np.nan).fillna(0)  
- technical_analyzer: iloc bounds + stochastic div guard + summary .get()  
- enhanced_fundamental: _safe_pct helper + volatility NaN guard  
- enhanced_technical: _pchg helper, flag closes.iloc[-11]!=0, prices.iloc[i-1]!=0, start_price!=0, ATR Close.replace(0,np.nan), RSI fillna(50), flag mean!=0, psychological price>0  

---

**Report generated by Layer 1 final deep-dive audit.**
