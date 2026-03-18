# Auxiliary Modules Code Audit Report

**Date:** March 13, 2026  
**Scope:** market_regime_detector, adaptive_market_strategy, crisis_detector, recommendation_history, improved_scoring_engine, corrected_scoring_engine, config, run_backtest_v2

---

## 1. market_regime_detector.py

### Findings

| Severity | Line(s) | Description | Suggested Fix |
|----------|---------|-------------|----------------|
| **MEDIUM** | 228-229 | `close.iloc[-20]` can be NaN; `close.iloc[-20] != 0` is True for NaN, so `_close_20` may be NaN, causing `roc_20` and `momentum_score` to be NaN. | Use: `_close_20 = close.iloc[-20]; _close_20 = _close_20 if (pd.notna(_close_20) and _close_20 != 0) else 1.0` |
| **LOW** | 232 | `(current_rsi - 50) / 50` — if `current_rsi` is NaN (e.g. from RSI calc edge case), returns NaN; `np.clip(nan, -1, 1)` yields NaN. | Add `current_rsi = 50.0 if pd.isna(current_rsi) else current_rsi` before use |
| **LOW** | 292-294 | Bare `except:` swallows all exceptions; no logging. | Use `except Exception as e: self.logger.debug(f"VIX fetch failed: {e}")` |

### Data Contract
- Uses `real_rsi` in `adjust_stock_score_by_regime` — matches pipeline.
- UNKNOWN regime handled correctly (lines 319-326).

### Clean
- `_calculate_change` has div-by-zero guard (line 381).
- VIX dynamic weighting, multi-index consensus, ROC guard present.

---

## 2. adaptive_market_strategy.py

### Findings

| Severity | Line(s) | Description | Suggested Fix |
|----------|---------|-------------|----------------|
| **HIGH** | 247-275 | Quintile position logic uses `current_regime` instead of `mapped`. When `current_regime='BULL'` (from market_regime_detector), it never matches `'BULL_MODERATE'` and falls to CALM logic. | Replace all `current_regime` with `mapped` in the quintile if/elif block (lines 243-272) |
| **HIGH** | 285 | `_get_quintile_performance(current_regime, quintile)` — passes raw regime; `performance_map` keys are BULL_MODERATE, etc. BULL would return `'avg +0.00%'`. | Pass `mapped` instead of `current_regime` |
| **MEDIUM** | 131 | `return_30d = (current_price - price_30d_ago) / price_30d_ago` — division by zero if `price_30d_ago == 0`. | Add: `if price_30d_ago == 0 or pd.isna(price_30d_ago): return {'regime': 'CALM', ...}` |
| **MEDIUM** | 153, 166 | `(current_price / sma_20 - 1) * 100` and `abs(price / sma_20 - 1)` — division by zero if `sma_20 == 0`. | Guard: `sma_20 = sma_20 if (sma_20 and not pd.isna(sma_20)) else current_price` |
| **LOW** | 159 | Exception handler returns dict missing `return_30d`, `volatility`, `price_vs_sma20`. | Report uses `.get()` with defaults; acceptable. |

### Clean
- REGIME_MAP correctly maps BULL/BEAR to BULL_MODERATE/BEAR_MODERATE.
- `regime_data` and `position_strategy` use `mapped` (lines 209-210).

---

## 3. crisis_detector.py

### Findings

| Severity | Line(s) | Description | Suggested Fix |
|----------|---------|-------------|----------------|
| **LOW** | 342 | `avg5 = vh['Close'].iloc[-5:-1].mean()` — if any value is NaN, mean can be NaN; `avg5 > 0` is False, so we use 0.0. Safe. | None; behavior is acceptable |
| **LOW** | 356 | `except Exception:` — bare catch in `_fetch_signals`; logs at debug. | Consider logging at warning for repeated failures |

### Clean
- All division-by-zero guarded (lines 343, 341).
- Sector rules, symbol overrides, severity scaling correct.
- Data contract: expects `sector` from pipeline; `get_stock_crisis_adjustment` receives it.

---

## 4. recommendation_history.py

### Findings

| Severity | Line(s) | Description | Suggested Fix |
|----------|---------|-------------|----------------|
| **HIGH** | 66-70 | File lock is on `tmp_path` after write. Another process can overwrite tmp before lock; lock should protect the destination. Also: lock is acquired after write — two processes can both overwrite tmp, then one replaces. | Lock the history file before writing: `with open(self.history_file, 'a') as lock_f: fcntl.flock(lock_f, fcntl.LOCK_EX); ... to_csv(tmp); os.replace(tmp, history_file)` |
| **MEDIUM** | 10, 68 | `fcntl` is Unix-only; fails on Windows with `ModuleNotFoundError`. | Use `import fcntl` in try/except with `msvcrt` or `portalocker` fallback for Windows |
| **LOW** | 109 | `hist.index.tz` — if index has no tz, `tz_localize(None)` on naive index may raise. | Use: `if hist.index.tz is not None: hist.index = hist.index.tz_localize(None)` (already present at 108-109) — verify `tz_localize(None)` on naive index: pandas allows it, no-op. Actually `tz_localize(None)` on tz-aware works; on naive it can error in older pandas. Safer: `if hasattr(hist.index, 'tz') and hist.index.tz is not None`. |

### Clean
- Outcome tracking with tz normalization (lines 108-109).
- Cooldown, score change, fundamental change logic correct.
- Outcome columns and schema defined.

---

## 5. improved_scoring_engine.py

### Findings

| Severity | Line(s) | Description | Suggested Fix |
|----------|---------|-------------|----------------|
| **MEDIUM** | 82, 121 | `enhanced_price_change_20d` — backtest `prepare_stock_data` does not provide it; defaults to 0. Momentum/contrarian scores will be inaccurate in backtest. | Add to `run_backtest_v2.prepare_stock_data`: `'enhanced_price_change_20d': price_change_1m` (or compute 20d from df) |
| **MEDIUM** | 95-96, 152 | `enhanced_macd_histogram`, `enhanced_adx` — not provided by backtest; default to 0. | Add to backtest or document that backtest uses simplified indicators |
| **LOW** | 103 | `if pd.notna(volume_ratio) and price_change_20d > 0` — when `enhanced_price_change_20d` is missing (0), volume bonus never applied. | Acceptable; explicit sentinel would be clearer |

### Data Contract
- Uses `enhanced_rsi_14`, `real_rsi`, `enhanced_price_change_20d`, `enhanced_volume_ratio`, `enhanced_adx`, `sector` — matches pipeline when populated.
- Backtest path omits several fields.

### Clean
- No division by zero in scoring logic.
- Sector adjustment, timing factor, quality multiplier correct.

---

## 6. corrected_scoring_engine.py

### Findings

| Severity | Line(s) | Description | Suggested Fix |
|----------|---------|-------------|----------------|
| **HIGH** | 175 | `price_from_high = (year_high - current_price) / year_high * 100` — division by zero when `year_high == 0` (e.g. `current_price=0` → fallback `current_price*1.2=0`). | Add: `if year_high <= 0: return 50` before line 175 |
| **MEDIUM** | 171-172 | Fallback uses `year_high`/`year_low`; pipeline uses `52_week_high`/`52_week_low`. Code already prefers `52_week_high` first. | OK; fallback chain is correct |
| **LOW** | 63-64 | `enhanced_price_change_5d`, `enhanced_volume_ratio` — backtest does not provide `enhanced_price_change_5d`; has `price_change_1w`. | Backtest could add `enhanced_price_change_5d` or use `price_change_1w` as proxy |

### Clean
- `year_high > year_low` guard prevents div-by-zero at line 183.
- Sector classification, value opportunity logic correct.

---

## 7. config.py

### Findings

| Severity | Line(s) | Description | Suggested Fix |
|----------|---------|-------------|----------------|
| **LOW** | 70-71 | `NIFTY_50_STOCKS` and `NIFTY_200_STOCKS` default to `None` in dataclass; `__post_init__` sets them. If accessed before init (e.g. as class attr), could be None. | Acceptable; dataclass usage is standard |
| **LOW** | 109-112 | `update_config` uses `print` for unknown keys; no logging. | Use `logging.warning` for consistency |

### Clean
- No bugs; structure is sound.
- TECHNICAL_WEIGHTS, FUNDAMENTAL_WEIGHTS defined.

---

## 8. run_backtest_v2.py

### Findings

| Severity | Line(s) | Description | Suggested Fix |
|----------|---------|-------------|----------------|
| **MEDIUM** | 190-242 | `prepare_stock_data` omits: `enhanced_price_change_20d`, `enhanced_price_change_5d`, `enhanced_macd_histogram`, `enhanced_adx`, `52_week_high`, `52_week_low`, `sector`. Scoring engines get defaults, reducing backtest fidelity. | Add: `'enhanced_price_change_20d': price_change_1m`, `'enhanced_price_change_5d': price_change_1w`, `'52_week_high': close.max()`, `'52_week_low': close.min()` (or from df) |
| **MEDIUM** | 207 | `rs = gain / loss` — when `loss == 0`, `rs = inf`; RSI becomes 100. When both 0, `rs = nan`, RSI = nan. | Use `loss_safe = loss.replace(0, np.nan); rs = gain / loss_safe` and `rsi.fillna(50)` |
| **LOW** | 212 | `price_change_1m = (current_price / close.iloc[-22] - 1) * 100` — if `close.iloc[-22] == 0`, division by zero. | Add: `if close.iloc[-22] == 0 or pd.isna(close.iloc[-22]): price_change_1m = 0` |
| **LOW** | 220 | `volatility = close.pct_change().rolling(20).std().iloc[-1] * 100` — can be NaN if insufficient data. | Use `np.nan_to_num(..., nan=0.0)` or guard downstream |

### Backtest Integrity
- Walk-forward uses `score_date` and `eval_date` correctly; no price look-ahead.
- Fundamentals fetched once per symbol (documented minor look-ahead).
- tz handling for hist index (line 133, 278) correct.

### Clean
- `vol_ratio` has div-by-zero guard (line 217).
- GAP-5 fundamentals fix applied.

---

## Summary by Severity

| Severity  | Count |
|-----------|-------|
| CRITICAL  | 0     |
| HIGH      | 4     |
| MEDIUM    | 9     |
| LOW       | 12    |

---

## Recommended Priority Fixes

1. **adaptive_market_strategy.py**: Use `mapped` instead of `current_regime` in quintile logic (lines 247-275, 285).
2. **corrected_scoring_engine.py**: Guard `year_high == 0` before division (line 175).
3. **recommendation_history.py**: Lock history file before write; add Windows-safe locking.
4. **run_backtest_v2.py**: Add `enhanced_price_change_20d`, `52_week_high/low` to `prepare_stock_data`; fix RSI div-by-zero.
5. **adaptive_market_strategy.py**: Guard `price_30d_ago` and `sma_20` for division by zero.
6. **market_regime_detector.py**: Guard NaN in `_close_20` and `current_rsi`.
