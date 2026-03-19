# Hybrid Optimized Scoring Engine (V4) — Code Audit Report

**File:** `hybrid_optimized_scoring.py`  
**Date:** 2026-03-13  
**Scope:** Bugs, logic flaws, data contract mismatches, regime handling, edge cases, dead code

---

## Executive Summary

The audit identified **4 CRITICAL**, **5 HIGH**, **4 MEDIUM**, and **3 LOW** severity issues. The most severe are: (1) `debt_to_equity` unit mismatch causing high-debt stocks to score as excellent, (2) RSI/volume/SMA field name mismatches with the pipeline, (3) regime not passed to momentum in backtest/standalone mode, and (4) division-by-zero risk when `sma_50` is explicitly 0.

---

## 1. BUGS

### CRITICAL

| # | Line(s) | Description | Suggested Fix |
|---|---------|-------------|---------------|
| 1.1 | 206 | **Division by zero when `sma_50` is 0:** `price_vs_sma = ((current_price - sma_50) / sma_50) * 100 if sma_50 != 0 else 0`. If upstream passes `sma_50: 0` explicitly, `_safe_float(stock_data.get('sma_50'), current_price)` returns 0 (not the default), so division occurs. | Use: `sma_50 = self._safe_float(stock_data.get('sma_50'), current_price); sma_50 = sma_50 if sma_50 and sma_50 > 0 else current_price; price_vs_sma = ((current_price - sma_50) / sma_50) * 100 if sma_50 else 0` |
| 1.2 | 78-80 | **`debt_to_equity` unit mismatch:** Code expects percentage (30, 60, 100). Pipeline/yfinance returns **ratio** (e.g. 1.082 = 108.2%). With ratio 1.082, `debt_equity < 30` is True → 25 points for a 108% D/E stock. | Normalize: `debt_equity = self._safe_float(stock_data.get('debt_to_equity'), 50); debt_equity = debt_equity * 100 if debt_equity and debt_equity <= 5 else debt_equity` (treat values ≤5 as ratio) |

### HIGH

| # | Line(s) | Description | Suggested Fix |
|---|---------|-------------|---------------|
| 1.3 | 155 | **RSI field mismatch:** Code uses `stock_data.get('rsi', 50)`. Pipeline provides `real_rsi` and `enhanced_rsi_14`. Cache shows no `rsi` key → RSI always defaults to 50. | Use: `rsi = self._safe_float(stock_data.get('real_rsi') or stock_data.get('enhanced_rsi_14') or stock_data.get('rsi'), 50)` |
| 1.4 | 231 | **Volume ratio field mismatch:** Code uses `volume_ratio`. Pipeline provides `enhanced_volume_ratio`. | Use: `volume_ratio = self._safe_float(stock_data.get('enhanced_volume_ratio') or stock_data.get('volume_ratio'), 1.0)` |
| 1.5 | 158 | **SMA field mismatch:** Code uses `sma_50`. Pipeline stores `legacy_sma_50`. Main analyzer never adds `sma_50` → `price_vs_sma` always 0 when using pipeline data. | Use: `sma_50 = self._safe_float(stock_data.get('sma_50') or stock_data.get('legacy_sma_50'), current_price)` |

### MEDIUM

| # | Line(s) | Description | Suggested Fix |
|---|---------|-------------|---------------|
| 1.6 | 228-230 | **Volume strength uses raw `.get()` without `_safe_float`:** `volume_ratio = stock_data.get('volume_ratio', 1.0)`. If value is `None` or non-numeric, comparisons like `volume_ratio > 3.0` can raise `TypeError`. | Use `_safe_float` for `volume_ratio` |
| 1.7 | 361 | **`stock_data` can be `None`:** `stock_data.get(...)` will raise `AttributeError` if `stock_data` is `None`. | Add guard at start: `if not stock_data or not isinstance(stock_data, dict): return {'hybrid_score': 0, ...}` |

---

## 2. LOGIC FLAWS

### CRITICAL

| # | Line(s) | Description | Suggested Fix |
|---|---------|-------------|---------------|
| 2.1 | 384-386, 366 | **Regime not passed to momentum in fallback mode:** `calculate_momentum_technical_score(stock_data)` is called before regime is detected. Regime is only determined at lines 384-386. When pipeline does not provide `market_regime` (e.g. backtest, standalone), momentum uses `_regime=''` → always non-bear branch. The detected regime is never passed to momentum. | Reorder: detect regime first (or use `stock_data.get('market_regime')` and call `detect_market_regime()` if empty), then call `calculate_momentum_technical_score(stock_data, market_regime=market_regime)` |

### HIGH

| # | Line(s) | Description | Suggested Fix |
|---|---------|-------------|---------------|
| 2.2 | 280 | **Volatility field mismatch:** Code uses `volatility`. User states pipeline has `volatility_20d`. Cache shows both `volatility` (annualized) and `enhanced_volatility_20d`. If some paths only provide `volatility_20d`, risk score would always use default 25. | Add fallback: `volatility = self._safe_float(stock_data.get('volatility') or stock_data.get('volatility_20d') or stock_data.get('enhanced_volatility_20d'), 25)` |
| 2.3 | 156 | **`price_change_1m` vs pipeline:** Pipeline has `enhanced_price_change_5d`, `enhanced_price_change_20d`, `enhanced_price_change_50d`. No `price_change_1m` in user's pipeline list. Main analyzer and backtest do provide it; if a different pipeline path omits it, momentum would default to 0. | Add fallback: `price_change_1m = self._safe_float(stock_data.get('price_change_1m') or stock_data.get('enhanced_price_change_20d'), 0)` (20d as proxy for 1m) |

### MEDIUM

| # | Line(s) | Description | Suggested Fix |
|---|---------|-------------|---------------|
| 2.4 | 100-108 | **Negative PE handling:** `pe_ratio > 0` gives 10 points. Negative PE (loss-making) gets 0. That is reasonable, but `pe_ratio == 0` also gets 0. Consider explicit handling for `pe_ratio <= 0` vs `0 < pe_ratio < 5`. | Document or add: `elif pe_ratio <= 0: pe_score = 0` for clarity |
| 2.5 | 293 | **52_week_high key:** Code uses `52_week_high`. Pipeline provides it. Cache confirms. No change needed; just verify key is consistent across all data paths. | — |

---

## 3. DATA CONTRACT MISMATCHES

| Field (Code) | Pipeline Field(s) | Status | Action |
|--------------|-------------------|--------|--------|
| `rsi` | `real_rsi`, `enhanced_rsi_14` | **MISMATCH** | Prefer `real_rsi` / `enhanced_rsi_14` (see 1.3) |
| `price_change_1m` | `enhanced_price_change_5d`, `enhanced_price_change_20d`, `enhanced_price_change_50d` | **PARTIAL** | Add fallback to `enhanced_price_change_20d` (see 2.3) |
| `sma_50` | `legacy_sma_50` (pipeline); `sma_50` (backtest) | **MISMATCH** | Add `legacy_sma_50` fallback (see 1.5) |
| `volume_ratio` | `enhanced_volume_ratio` | **MISMATCH** | Prefer `enhanced_volume_ratio` (see 1.4) |
| `volatility` | `volatility`, `volatility_20d` | **PARTIAL** | Add `volatility_20d` fallback (see 2.2) |
| `current_price`, `pe_ratio`, `roe`, `market_cap`, `52_week_high`, `sector`, `market_regime` | As listed | **OK** | — |
| `debt_to_equity` | Ratio from yfinance | **UNIT MISMATCH** | Convert ratio to percentage (see 1.2) |

---

## 4. REGIME HANDLING

| # | Line(s) | Description | Status |
|---|---------|-------------|--------|
| 4.1 | 384-386 | BULL/BEAR/SIDEWAYS correctly mapped to bullish/bearish/neutral | **OK** |
| 4.2 | 335-357 | `_REGIME_WEIGHTS` correctly defines bullish/bearish/neutral | **OK** |
| 4.3 | 366 | Momentum score does not receive detected regime in fallback (backtest/standalone) | **BUG** (see 2.1) |
| 4.4 | 311 | `detect_market_regime()` returns 'bullish'/'bearish'/'neutral' — matches `_REGIME_WEIGHTS` keys | **OK** |
| 4.5 | 391-395 | Regime multiplier (1.10 / 0.90 / 1.00) applied correctly | **OK** |

---

## 5. EDGE CASES

| # | Line(s) | Scenario | Handling | Suggested Fix |
|---|---------|----------|----------|---------------|
| 5.1 | 78-81 | NaN/None in fundamental fields | `_safe_float` handles | — |
| 5.2 | 205-206 | `sma_50 == 0` | Not fully guarded | See 1.1 |
| 5.3 | 293 | `high_52w == 0` or `current_price == 0` | Guarded by `if high_52w > 0 and current_price > 0` | — |
| 5.4 | 361 | `stock_data` is `None` | No guard | See 1.7 |
| 5.5 | 374 | `sector_performance_adj` out of range | Clamped with `max(0, min(100, ...))` | — |
| 5.6 | 228-244 | `volume_ratio` is `None` or non-numeric | No `_safe_float` | See 1.6 |
| 5.7 | 78 | ROE as decimal (0.18) vs percentage (18): pipeline uses percentage (22.391 in cache). Backtest uses `(info.get('returnOnEquity') or 0.15) * 100` → 15. So backtest is correct. Main pipeline (yfinance) may return 0.22 for 22% — need to verify. | Cache shows 22.391 (percentage). Backtest multiplies by 100. | If any path passes decimal, add: `roe = roe * 100 if roe and roe <= 1.5 else roe` |
| 5.8 | 314-331 | `detect_market_regime()` network failure | Returns 'neutral' on exception | — |

---

## 6. DEAD CODE / UNUSED BRANCHES

| # | Line(s) | Description | Suggested Fix |
|---|---------|-------------|---------------|
| 6.1 | 37-43 | `self.component_weights` is defined but never used. Scoring uses `_REGIME_WEIGHTS` only. | Remove or document as "reference/default" and use only in neutral if desired |
| 6.2 | 21-26 | `pandas` imported as `pd` — not used | Remove `import pandas as pd` |
| 6.3 | 24 | `datetime, timedelta` imported — not used in this file | Remove if unused (used by yfinance internally? No — remove) |

---

## 7. ADDITIONAL OBSERVATIONS

| # | Line(s) | Description |
|---|---------|-------------|
| 7.1 | 414-416 | `symbol.replace('.NS', '')` — `base_symbol` is computed but never used |
| 7.2 | 418-419 | Sector multiplier can push `adjusted_score` above 100 before regime multiplier; final clamp at 319 mitigates |
| 7.3 | 413-419 | `regime_multiplier` (0.90–1.10) applied after sector multiplier — order is intentional |
| 7.4 | 416-417 | `_get_sector_multiplier` uses `stock_data`; if `stock_data` is empty, returns 1.0 (default) |

---

## 8. TEST DATA BUG (Lines 414-418)

Test block uses `roe: 0.18` (decimal). With pipeline convention (0–100), 18% should be `roe: 18`. As written, `roe_score` would be 0 (0.18 fails all thresholds). Fix test: `'roe': 18`.

---

## 9. PRIORITY FIX ORDER

1. **CRITICAL:** Fix `debt_to_equity` unit handling (1.2)
2. **CRITICAL:** Fix division-by-zero for `sma_50` (1.1)
3. **CRITICAL:** Pass regime to momentum in fallback (2.1)
4. **HIGH:** Add RSI/volume/SMA field fallbacks (1.3, 1.4, 1.5)
5. **HIGH:** Add volatility fallback (2.2)
6. **MEDIUM:** Add `stock_data` None guard (1.7)
7. **MEDIUM:** Use `_safe_float` for volume_ratio (1.6)
8. **LOW:** Remove dead code (6.1–6.3)

---

## 10. SUMMARY TABLE

| Severity | Count |
|----------|-------|
| CRITICAL | 4 |
| HIGH     | 5 |
| MEDIUM   | 4 |
| LOW      | 3 |
