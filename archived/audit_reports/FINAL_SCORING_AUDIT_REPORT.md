# Final Line-by-Line Scoring Engine Audit Report

**Audit Date:** March 13, 2026  
**Scope:** `hybrid_optimized_scoring.py`, `improved_scoring_engine.py`  
**Context:** Bull market works (+0.46 correlation, 75% win rate); bear market fails (inverted quintile spread). Regime adaptation broken; momentum bias doesn't self-correct.

**Excluded (per user: already fixed):** D/E percentage scale, ROE double-conversion, sector lookup, 52_week field names, enhanced_technical_analyzer div-by-zero, bare except blocks.

---

## FILE 1: hybrid_optimized_scoring.py

---

### BUG: Division by Zero — price_vs_sma
- **File:Line(s):** hybrid_optimized_scoring.py:181
- **Type:** BUG
- **Severity:** CRITICAL
- **Description:** `price_vs_sma = ((current_price - sma_50) / sma_50) * 100`. If `sma_50` is 0, division by zero occurs. Default is `current_price` (line 147), but if upstream explicitly passes `sma_50: 0`, the default is not used.
- **Impact on accuracy:** Crash when `sma_50` is 0; no score returned for affected stocks.
- **Fix:** Guard before division:
  ```python
  sma_50 = stock_data.get('sma_50') or current_price
  sma_50 = sma_50 if sma_50 and sma_50 > 0 else current_price
  price_vs_sma = ((current_price - sma_50) / sma_50) * 100 if sma_50 else 0
  ```

---

### BUG: NaN/None Handling — Fundamental Quality
- **File:Line(s):** hybrid_optimized_scoring.py:79-82, 88-130
- **Type:** BUG
- **Severity:** HIGH
- **Description:** No `pd.notna()` or `np.isnan()` checks for `pe_ratio`, `roe`, `debt_equity`, `market_cap`. If upstream returns `np.nan`, comparisons like `roe > 20` evaluate to False (NaN comparisons return False), yielding `roe_score = 0`. Similarly, `pe_ratio` NaN falls to `else: pe_score = 0`. `market_cap` NaN yields `size_score = 5` (else branch).
- **Impact on accuracy:** Silent mis-scoring; fundamentally strong stocks with missing data get penalized as weak.
- **Fix:** Add safe extraction before use:
  ```python
  def _safe(val, default):
      return default if (val is None or (hasattr(val, '__float__') and np.isnan(float(val)))) else val
  pe_ratio = _safe(stock_data.get('pe_ratio'), 15)
  roe = _safe(stock_data.get('roe'), 10)
  debt_equity = _safe(stock_data.get('debt_to_equity'), 50)
  market_cap = _safe(stock_data.get('market_cap'), 1000000000)
  ```

---

### BUG: NaN/None Handling — Momentum Technical
- **File:Line(s):** hybrid_optimized_scoring.py:144-147, 181
- **Type:** BUG
- **Severity:** HIGH
- **Description:** `rsi`, `price_change_1m`, `current_price`, `sma_50` have no NaN checks. RSI NaN → `rsi_score = 5` (weak). `price_change_1m` NaN → falls to `else: price_1m_score = 5`. `current_price` or `sma_50` NaN can cause invalid `price_vs_sma`.
- **Impact on accuracy:** Momentum scores silently deflate when data is missing.
- **Fix:** Same `_safe()` pattern; ensure `current_price` and `sma_50` are valid before division.

---

### BUG: NaN/None Handling — Volume Strength
- **File:Line(s):** hybrid_optimized_scoring.py:204-206
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** `volume_ratio` from `stock_data.get('volume_ratio', 1.0)` — if key exists but value is NaN, default is not used. `if volume_ratio > 3.0` with NaN is False, so falls through to `volume_score = 20`.
- **Impact on accuracy:** Stocks with NaN volume_ratio get penalized (20) instead of neutral (50).
- **Fix:** `volume_ratio = _safe(stock_data.get('volume_ratio'), 1.0)`.

---

### BUG: Exception Handler Return Value
- **File:Line(s):** hybrid_optimized_scoring.py:395-396
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** On exception, returns `{'hybrid_score': 50, 'components': {}, 'adjustments': {}}`. Callers expecting `components` or `adjustments` keys may fail on empty dicts. `generate_hybrid_recommendation` uses `hybrid_scores['hybrid_score']` and `_get_quintile(score)` — those work, but `components`/`adjustments` being empty can break downstream UI or logging.
- **Impact on accuracy:** No direct scoring impact; potential runtime errors in consumers.
- **Fix:** Return full structure with neutral defaults: `'components': {'fundamental_quality': 50, ...}, 'adjustments': {'sector_multiplier': 1.0, 'market_regime': 'neutral', ...}`.

---

### GAP: Regime Weights — No Validation
- **File:Line(s):** hybrid_optimized_scoring.py:302-324
- **Type:** GAP
- **Severity:** LOW
- **Description:** `_REGIME_WEIGHTS` sums to 1.0 for bullish, bearish, neutral. But `weights = self._REGIME_WEIGHTS.get(market_regime, self._REGIME_WEIGHTS['neutral'])` — if `market_regime` is an unexpected string (e.g. from future detector), fallback is correct. No runtime validation that weights sum to 1.0.
- **Impact on accuracy:** Minimal; weights are correct as written.
- **Fix/Upgrade:** Add assertion in tests: `assert abs(sum(weights.values()) - 1.0) < 1e-6`.

---

### GAP: Sector Multiplier — Unknown Sector
- **File:Line(s):** hybrid_optimized_scoring.py:398-417
- **Type:** GAP
- **Severity:** LOW
- **Description:** `_get_sector_multiplier` returns `self.sector_multipliers['default']` (1.0) for unknown sectors. Correct. But `sector_map` maps yfinance names (e.g. 'industrials') to internal names. Cache shows `"sector": "Industrials"` — `.lower()` yields 'industrials', which maps to 'Materials'. "Industrials" ≠ "Materials" semantically; may be intentional aggregation.
- **Impact on accuracy:** Industrials stocks get Materials multiplier (1.0); acceptable if intentional.
- **Fix/Upgrade:** Document mapping or add 'Industrials' as separate sector if needed.

---

### GAP: Volume Strength — Formula Does Not Use volume or volume_sma_20
- **File:Line(s):** hybrid_optimized_scoring.py:204-206
- **Type:** GAP
- **Severity:** LOW
- **Description:** `volume` and `volume_sma_20` are retrieved but never used. Score depends only on `volume_ratio`. If `volume_ratio` is missing, fallback 1.0 gives `volume_score = 40`. Formula is correct for ratio-based scoring; the unused vars are dead code.
- **Impact on accuracy:** None; formula is sound.
- **Fix:** Remove unused `volume` and `volume_sma_20` or use them for validation (e.g. reject if volume_sma_20 is 0 and volume_ratio would be inf).

---

### GAP: Risk Adjustment — Volatility Scale
- **File:Line(s):** hybrid_optimized_scoring.py:254-268
- **Type:** GAP
- **Severity:** LOW
- **Description:** Assumes volatility is annualized percentage (e.g. 25 = 25%). `enhanced_fundamental_analyzer` computes `volatility = hist['Close'].pct_change().std() * 100 * (252**0.5)` — correct. `run_backtest_v2` uses 20d std * 100 — not annualized. Inconsistent scale in backtest vs production.
- **Impact on accuracy:** Backtest risk scores may not match production.
- **Fix:** Document expected units; ensure backtest uses same annualization.

---

### UPGRADE: PE Negative / Loss-Making Companies
- **File:Line(s):** hybrid_optimized_scoring.py:100-108
- **Type:** UPGRADE
- **Severity:** MEDIUM
- **Description:** Negative PE (loss-making) gets `pe_score = 0`. Correct penalization. But no distinction between "slightly negative" (turnaround) vs "deeply negative" (distressed). Both get 0.
- **Impact on accuracy:** In bear markets, loss-makers and turnarounds treated identically; may over-penalize potential recoveries.
- **Fix/Upgrade:** Consider: `elif pe_ratio < 0 and pe_ratio > -10: pe_score = 5` (turnaround), `else: pe_score = 0` (distressed).

---

### UPGRADE: RSI > 70 — Overbought in Bear Markets
- **File:Line(s):** hybrid_optimized_scoring.py:153-154
- **Type:** UPGRADE
- **Severity:** HIGH
- **Description:** RSI > 70 gives `rsi_score = 30` (strong momentum). In bear markets, RSI > 70 often indicates overbought bounce before further decline. Momentum bias amplifies this.
- **Impact on accuracy:** Bear market: overbought stocks score high, then fall — contributes to inverted quintile spread.
- **Fix/Upgrade:** Regime-dependent RSI interpretation: In bearish regime, cap RSI contribution or invert: `if market_regime == 'bearish' and rsi > 70: rsi_score = 5` (overbought = avoid).

---

### UPGRADE: Regime Multiplier Direction
- **File:Line(s):** hybrid_optimized_scoring.py:66-70, 374-375
- **Type:** UPGRADE
- **Severity:** HIGH
- **Description:** `regime_multiplier`: bullish 1.10, bearish 0.90. This scales the *entire* score. In bear markets, reducing all scores by 10% doesn't fix the *ordering* — high-momentum stocks still rank high. The regime *weights* (more fundamental, less momentum) help, but the multiplier is a blunt instrument.
- **Impact on accuracy:** Bear market scores compressed but ranking may remain momentum-biased.
- **Fix/Upgrade:** Consider removing regime_multiplier and relying solely on regime-adaptive weights; or apply multiplier only to momentum components.

---

### UPGRADE: Missing Relative Strength vs Index
- **File:Line(s):** hybrid_optimized_scoring.py (entire)
- **Type:** UPGRADE
- **Severity:** MEDIUM
- **Description:** No factor for "stock return vs Nifty return" over same period. A stock up 5% when index is down 10% is strong; up 5% when index is up 15% is weak.
- **Impact on accuracy:** Bear market: stocks that fall less than index are not explicitly rewarded.
- **Fix/Upgrade:** Add `relative_strength_1m = price_change_1m - index_change_1m`; incorporate into momentum or sector score.

---

### UPGRADE: No Max-Drawdown Penalty
- **File:Line(s):** hybrid_optimized_scoring.py:250-272
- **Type:** UPGRADE
- **Severity:** MEDIUM
- **Description:** Risk adjustment uses only volatility. Max drawdown (worst peak-to-trough decline) is not considered. High volatility with shallow drawdowns vs deep drawdowns are treated the same.
- **Impact on accuracy:** Bear market: stocks with large drawdowns may still score well if volatility is moderate.
- **Fix/Upgrade:** Add `max_drawdown` from price history; penalize scores when drawdown > threshold (e.g. > 20%).

---

### UPGRADE: Dead Code — price_change_1w
- **File:Line(s):** hybrid_optimized_scoring.py:146
- **Type:** GAP
- **Severity:** LOW
- **Description:** `price_change_1w` is retrieved but never used.
- **Impact on accuracy:** Wasted short-term signal.
- **Fix:** Use in momentum (e.g. weight 1w and 1m together) or remove.

---

### UPGRADE: Dead Code — component_weights
- **File:Line(s):** hybrid_optimized_scoring.py:37-43
- **Type:** GAP
- **Severity:** LOW
- **Description:** `self.component_weights` is never used; `_REGIME_WEIGHTS` is used instead.
- **Impact on accuracy:** None; misleading for maintainers.
- **Fix:** Remove or add comment: `# Legacy; _REGIME_WEIGHTS used for regime-adaptive scoring`.

---

## FILE 2: improved_scoring_engine.py

---

### BUG: Contrarian Momentum — Actually Trend-Following
- **File:Line(s):** improved_scoring_engine.py:113-159
- **Type:** BUG
- **Severity:** CRITICAL
- **Description:** Function is named `calculate_contrarian_momentum_score` but implements **trend-following**: `abs_change > 10` → +25, `abs_change < 1` (flat) → -15. It rewards *any* strong trend (up or down) and penalizes flat. True contrarian would favor oversold bounce (e.g. RSI < 30 + negative momentum = buy). Docstring says "Strong trending stocks... = GOOD" — so it's misnamed, not misimplemented.
- **Impact on accuracy:** In bear markets, stocks with strong *downward* trend get +25 (abs_change > 10). Falling stocks score high — directly causes inverted quintile spread.
- **Fix:** Either (a) rename to `calculate_trend_strength_score` and **exclude** negative trends: `if price_change_20d > 10: +25` but `if price_change_20d < -10: -25`, or (b) implement true contrarian: reward oversold + negative momentum.

---

### BUG: Momentum Technical — Rewards Downward MACD
- **File:Line(s):** improved_scoring_engine.py:94-99
- **Type:** BUG
- **Severity:** HIGH
- **Description:** `if macd_histogram > 0: score += 10; else: score -= 10`. Correct direction. But if `enhanced_macd_histogram` is missing, default 0 is used. `0 > 0` is False → `score -= 10`. Missing data penalizes.
- **Impact on accuracy:** Stocks without MACD data get -10; backtest with incomplete data under-rewards valid picks.
- **Fix:** When missing, don't adjust: `if pd.notna(macd_histogram): ... else: pass` (neutral).

---

### BUG: Momentum Technical — price_change_20d Used Before Definition in volume_ratio Check
- **File:Line(s):** improved_scoring_engine.py:82-104
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** `price_change_20d = stock_data.get('enhanced_price_change_20d', 0)` at line 82. At line 103: `if pd.notna(volume_ratio) and price_change_20d > 0`. If key is missing, `price_change_20d = 0`. So `0 > 0` is False — volume bonus never applied when price_change_20d is missing. Correct fallback but the condition conflates "missing" with "flat".
- **Impact on accuracy:** When enhanced_price_change_20d is absent (e.g. backtest), volume confirmation never triggers.
- **Fix:** Use explicit sentinel: `price_change_20d = stock_data.get('enhanced_price_change_20d', None)`; only apply volume bonus when `price_change_20d is not None and price_change_20d > 0`.

---

### BUG: adx_14 — Field Name Mismatch
- **File:Line(s):** improved_scoring_engine.py:145
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** Uses `stock_data.get('adx_14', 0)`. Main analyzer and cache use `enhanced_adx` (ml_predictor, excel_exporter). No `adx_14` in cache JSONs. ADX contribution is always skipped (default 0, `adx > 0` false).
- **Impact on accuracy:** Trend strength (ADX) never contributes; trend-following logic incomplete.
- **Fix:** Use `stock_data.get('adx_14') or stock_data.get('enhanced_adx', 0)`.

---

### BUG: Sector Adjustment — No stock_data['sector']
- **File:Line(s):** improved_scoring_engine.py:264-284, 288-291
- **Type:** BUG
- **Severity:** HIGH
- **Description:** `get_sector_classification(symbol)` uses **symbol-based hardcoded map** (e.g. HDFCBANK → Banking). It does NOT use `stock_data.get('sector')`. Main analyzer provides `sector` from yfinance (e.g. "Industrials"). Improved engine ignores it.
- **Impact on accuracy:** Sector multiplier based on symbol, not actual sector; new listings or symbol changes misclassified.
- **Fix:** Prefer `stock_data.get('sector')` when available; fallback to symbol map.

---

### BUG: Risk Profile — Not Regime-Adaptive
- **File:Line(s):** improved_scoring_engine.py:24-46, 307-361
- **Type:** GAP
- **Severity:** HIGH
- **Description:** `risk_profile` ('aggressive'/'moderate'/'conservative') is set at init and never changes. No market regime detection. In bear markets, 'aggressive' still gives 40% momentum weight.
- **Impact on accuracy:** Bear market: aggressive profile keeps momentum bias; contributes to inverted spread.
- **Fix/Upgrade:** Add regime detection; in bearish regime, override weights toward conservative (more fundamental, less momentum) regardless of user profile.

---

### BUG: Quality Multiplier — debt_to_equity Threshold
- **File:Line(s):** improved_scoring_engine.py:233-234
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** `debt_to_equity < 100` awards quality signal. If debt_to_equity is **ratio** (e.g. 1.08), 1.08 < 100 is True — low debt. If ratio 10 (e.g. banks), 10 < 100 still True. Threshold 100 works for percentage scale; for ratio scale, should be < 1.0 or < 2.0. User said D/E already converted; if not, this is wrong.
- **Impact on accuracy:** If data is ratio, high-debt companies (D/E 2–5) still get quality signal.
- **Fix:** Ensure debt_to_equity is in percentage before use, or use ratio threshold (e.g. < 1.5).

---

### BUG: Fundamental Quality — PE/ROE NaN Handling
- **File:Line(s):** improved_scoring_engine.py:170-214
- **Type:** BUG
- **Severity:** MEDIUM
- **Description:** `if pd.notna(pe_ratio) and pe_ratio > 0` — good. But when `pe_ratio` is None/missing, `stock_data.get('pe_ratio')` returns None; `pd.notna(None)` is True, so we skip the block. Score stays 50. For ROE: `if pd.notna(roe)` — good. For debt_to_equity, pb_ratio: similar. But `pe_ratio > 40` and `pe_ratio < 5` — if pe_ratio is negative, `pe_ratio > 0` is False so we skip; negative PE never explicitly penalized (score stays 50). Minor.
- **Impact on accuracy:** Negative PE not explicitly penalized; neutral 50.
- **Fix/Upgrade:** Add `elif pe_ratio is not None and pe_ratio < 0: score -= 15` for loss-makers.

---

### GAP: Timing Factor — Not Regime-Aware
- **File:Line(s):** improved_scoring_engine.py:293-306
- **Type:** GAP
- **Severity:** LOW
- **Description:** `calculate_timing_factor()` uses calendar month (Oct–Jan, April favorable; May–June unfavorable). No market regime. In bear markets, "favorable months" may still be negative.
- **Impact on accuracy:** Timing factor is static; doesn't adapt to regime.
- **Fix:** Consider regime in timing or reduce timing impact in bear markets.

---

### GAP: Missing enhanced_price_change_20d, enhanced_macd_histogram, adx_14
- **File:Line(s):** improved_scoring_engine.py:82, 94, 122, 145
- **Type:** GAP
- **Severity:** MEDIUM
- **Description:** When running in backtest or standalone, these fields may be missing. Defaults: 0, 0, 0. Momentum and contrarian scores degrade to neutral or penalized.
- **Impact on accuracy:** Backtest with minimal stock_data under-represents real analyzer behavior.
- **Fix:** Document required fields; ensure run_backtest_v2 and other callers populate enhanced_price_change_20d, enhanced_macd_histogram, enhanced_adx/adx_14.

---

### UPGRADE: Contrarian Momentum — Sign of Trend
- **File:Line(s):** improved_scoring_engine.py:122-132
- **Type:** UPGRADE
- **Severity:** CRITICAL
- **Description:** `abs_change > 10` rewards both +10% and -10% equally. In bear markets, -10% (falling) gets +25. This is the primary cause of inverted quintile spread.
- **Impact on accuracy:** Bear market: falling stocks rank in top quintile.
- **Fix:** Use signed change: `if price_change_20d > 10: +25`, `elif price_change_20d < -10: -25`. Reward uptrends, penalize downtrends.

---

### UPGRADE: Quality Multiiplier — Net Margin / Revenue Growth
- **File:Line(s):** improved_scoring_engine.py:246-254
- **Type:** UPGRADE
- **Severity:** LOW
- **Description:** `net_margin > 10` and `revenue_growth > 10` — no NaN check. `pd.notna(net_margin)` is used. Good. But `revenue_growth` could be negative (declining revenue); we only check `> 10`. Declining revenue companies can still get other quality signals.
- **Impact on accuracy:** Minor; quality multiplier is additive.
- **Fix:** Consider penalizing revenue_growth < -5.

---

### UPGRADE: No Volatility / Risk Component
- **File:Line(s):** improved_scoring_engine.py (entire)
- **Type:** UPGRADE
- **Severity:** MEDIUM
- **Description:** Improved engine has no volatility or risk adjustment. Hybrid has `risk_adjustment`. In bear markets, low-volatility (defensive) stocks may outperform; improved engine doesn't reward them.
- **Impact on accuracy:** Bear market: no explicit preference for low-volatility names.
- **Fix/Upgrade:** Add `risk_adjustment` component (like hybrid) with weight 0.05–0.10.

---

### UPGRADE: Sector Multipliers — Limited Coverage
- **File:Line(s):** improved_scoring_engine.py:48-57, 264-284
- **Type:** UPGRADE
- **Severity:** LOW
- **Description:** Sector map has Banking, Financial Services, Capital Goods, etc. Many symbols map to 'default'. yfinance sector (Industrials, Technology, etc.) is richer but unused.
- **Impact on accuracy:** Many stocks get default 1.0; sector tilts underutilized.
- **Fix:** Use stock_data['sector'] with yfinance→internal mapping (like hybrid).

---

## Summary Table

| File | Line(s) | Type | Severity | One-Line Description |
|------|---------|------|----------|----------------------|
| hybrid | 181 | BUG | CRITICAL | Division by zero if sma_50 is 0 |
| hybrid | 79-130 | BUG | HIGH | No NaN handling in fundamental quality |
| hybrid | 144-181 | BUG | HIGH | No NaN handling in momentum |
| hybrid | 204-206 | BUG | MEDIUM | volume_ratio NaN not handled |
| hybrid | 395-396 | BUG | MEDIUM | Exception return structure incomplete |
| hybrid | 153-154 | UPGRADE | HIGH | RSI>70 overbought in bear markets |
| hybrid | 66-70, 374-375 | UPGRADE | HIGH | Regime multiplier doesn't fix ordering |
| hybrid | 100-108 | UPGRADE | MEDIUM | PE negative: no turnaround vs distressed |
| hybrid | (entire) | UPGRADE | MEDIUM | No relative strength vs index |
| hybrid | 250-272 | UPGRADE | MEDIUM | No max-drawdown penalty |
| improved | 113-159 | BUG | CRITICAL | Contrarian momentum rewards downtrends |
| improved | 122-132 | UPGRADE | CRITICAL | abs_change rewards negative trends |
| improved | 94-99 | BUG | HIGH | MACD missing → -10 penalty |
| improved | 264-284 | BUG | HIGH | Ignores stock_data['sector'] |
| improved | 24-46 | GAP | HIGH | Risk profile not regime-adaptive |
| improved | 145 | BUG | MEDIUM | adx_14 vs enhanced_adx field mismatch |
| improved | 82-104 | BUG | MEDIUM | price_change_20d missing → volume bonus never applied |
| improved | 233-234 | BUG | MEDIUM | debt_to_equity scale in quality_multiplier |
| improved | (entire) | UPGRADE | MEDIUM | No volatility/risk component |

---

## Recommended Priority Fixes (Bear Market)

1. **improved_scoring_engine.py:122-132** — Use signed `price_change_20d`; penalize downtrends.
2. **improved_scoring_engine.py:113-159** — Rename and fix: reward uptrends only, penalize downtrends.
3. **hybrid_optimized_scoring.py:153-154** — In bearish regime, cap or invert RSI>70.
4. **hybrid_optimized_scoring.py:181** — Guard sma_50 division by zero.
5. **improved_scoring_engine.py** — Add regime detection; override weights in bear markets.
6. **improved_scoring_engine.py:264-284** — Use stock_data['sector'] when available.
7. **improved_scoring_engine.py:145** — Use enhanced_adx as fallback for adx_14.
