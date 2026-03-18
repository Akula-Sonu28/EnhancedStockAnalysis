# Layer 2 Scoring Engines — Audit Report

**Audit Date:** March 13, 2025  
**Scope:** `hybrid_optimized_scoring.py` (V4), `improved_scoring_engine.py` (V3), `corrected_scoring_engine.py` (V2)

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 4 |
| HIGH | 6 |
| MEDIUM | 8 |
| LOW | 3 |

---

## 1. hybrid_optimized_scoring.py (V4)

### CRITICAL

#### ISSUE 1.1: Debt-to-Equity Unit Mismatch
- **File:** `hybrid_optimized_scoring.py`  
- **Lines:** 81, 112–118  
- **Severity:** CRITICAL  
- **Category:** Unit Mismatch  
- **Description:** `debt_to_equity` from yfinance/enhanced_fundamental_analyzer is a **ratio** (e.g., 1.5 for 1.5x). The engine uses thresholds 30, 60, 100 as if they were **percentages**.  
- **Impact:** Almost all companies get high debt scores (e.g., 1.5 < 30 → +20). Banks with D/E ~5–10x would score 0 (correct) but the 30/60/100 thresholds are wrong for ratio inputs.  
- **Suggested fix:** Either (a) convert ratio to percentage before use: `debt_pct = debt_equity * 100 if debt_equity < 10 else debt_equity`, or (b) use ratio thresholds: `< 0.3`, `< 0.6`, `< 1.0` for low/moderate/high.

#### ISSUE 1.2: ROE Unit Mismatch in Test Data
- **File:** `hybrid_optimized_scoring.py`  
- **Lines:** 79–81, 382  
- **Severity:** CRITICAL  
- **Category:** Unit Mismatch  
- **Description:** Engine expects ROE as **percentage** (10, 15, 20). Test data uses `'roe': 0.18` (decimal).  
- **Impact:** Test gives `roe_score = 0` (0.18 < 5) instead of intended score for 18% ROE.  
- **Suggested fix:** Either use `'roe': 18` in test, or add: `roe = roe * 100 if roe is not None and 0 < roe <= 1 else roe`.

### HIGH

#### ISSUE 1.3: Division by Zero — price_vs_sma
- **File:** `hybrid_optimized_scoring.py`  
- **Lines:** 181  
- **Severity:** HIGH  
- **Category:** Edge Case  
- **Description:** `price_vs_sma = ((current_price - sma_50) / sma_50) * 100`. If `sma_50` is 0, division by zero.  
- **Impact:** Crash when `sma_50` is 0 or missing and default is not used.  
- **Suggested fix:** `sma_50 = stock_data.get('sma_50') or current_price` and guard: `sma_50 = sma_50 if sma_50 and sma_50 > 0 else current_price`.

#### ISSUE 1.4: Missing NaN/None Handling
- **File:** `hybrid_optimized_scoring.py`  
- **Lines:** 79–81, 88–98, 104–108, 112–118  
- **Severity:** HIGH  
- **Category:** Edge Case  
- **Description:** No `pd.notna()` or `np.isnan()` checks. If `roe` is `np.nan`, comparisons like `roe > 20` are False, so `roe_score = 0`.  
- **Impact:** Silent mis-scoring when upstream returns NaN.  
- **Suggested fix:** Add `if pd.isna(roe): roe = 10` (or equivalent defaults) before use.

### MEDIUM

#### ISSUE 1.5: Dead Code — price_change_1w
- **File:** `hybrid_optimized_scoring.py`  
- **Lines:** 146  
- **Severity:** MEDIUM  
- **Category:** Dead Code  
- **Description:** `price_change_1w = stock_data.get('price_change_1w', 0)` is retrieved but never used.  
- **Impact:** Wasted logic; possible confusion if someone intended to use it.  
- **Suggested fix:** Remove the line or use it in momentum (e.g., short-term price change).

#### ISSUE 1.6: Dead Code — component_weights
- **File:** `hybrid_optimized_scoring.py`  
- **Lines:** 37–43  
- **Severity:** MEDIUM  
- **Category:** Dead Code  
- **Description:** `self.component_weights` is set but never used. `_REGIME_WEIGHTS` is used instead.  
- **Impact:** Misleading; suggests default weights are used when they are not.  
- **Suggested fix:** Remove or add a comment that it is legacy/unused.

#### ISSUE 1.7: Sector Mapping — Consumer Defensive
- **File:** `hybrid_optimized_scoring.py`  
- **Lines:** 306, 401  
- **Severity:** MEDIUM  
- **Category:** Logic Flaw  
- **Description:** `'consumer defensive'` (FMCG) is mapped to `'Consumer Durables'`. Sector semantics differ.  
- **Impact:** FMCG stocks may get wrong sector multiplier.  
- **Suggested fix:** Either add a separate `'Consumer Defensive'` or `'FMCG'` entry, or document the mapping.

### LOW

#### ISSUE 1.8: RSI > 70 Interpretation
- **File:** `hybrid_optimized_scoring.py`  
- **Lines:** 153–154  
- **Severity:** LOW  
- **Category:** Logic Flaw  
- **Description:** RSI > 70 is typically "overbought" in technical analysis; engine treats it as "strong momentum."  
- **Impact:** May over-reward overbought stocks. Design choice; may be intentional per backtest.  
- **Suggested fix:** Document as intentional; consider capping at RSI 65–70.

---

## 2. improved_scoring_engine.py (V3)

### CRITICAL

#### ISSUE 2.1: Debt-to-Equity Unit Mismatch
- **File:** `improved_scoring_engine.py`  
- **Lines:** 192–201, 234  
- **Severity:** CRITICAL  
- **Category:** Unit Mismatch  
- **Description:** Same as hybrid: engine uses 50, 100, 150, 200 as if percentages. yfinance returns ratio (0.5–10).  
- **Impact:** Most companies get "very low debt" or "moderate debt" when they should be penalized.  
- **Suggested fix:** Either convert ratio to percentage or use ratio thresholds (e.g., `< 0.5`, `< 1.0`, `> 2.0`).

### HIGH

#### ISSUE 2.2: Symbol Suffix for Sector Lookup
- **File:** `improved_scoring_engine.py`  
- **Lines:** 260–282, 326  
- **Severity:** HIGH  
- **Category:** Logic Flaw  
- **Description:** `get_sector_classification(symbol)` uses `symbol` as-is. If `symbol` is `"SBIN.NS"`, it returns `'default'` because `"SBIN.NS"` is not in the map.  
- **Impact:** Sector lookup fails for all symbols with `.NS` suffix.  
- **Suggested fix:** `base_symbol = symbol.replace('.NS', '').upper()` before lookup.

### MEDIUM

#### ISSUE 2.3: Component Breakdown Label Mismatch
- **File:** `improved_scoring_engine.py`  
- **Lines:** 343  
- **Severity:** MEDIUM  
- **Category:** Dead Code / Logic Flaw  
- **Description:** `'stability_weight'` is used for `contrarian_momentum * weight`, but the component is `contrarian_momentum`.  
- **Impact:** Misleading labels in output.  
- **Suggested fix:** Use `'contrarian_momentum_weight'` or `'momentum_strength_weight'`.

#### ISSUE 2.4: price_change_20d Used Before Definition in Volume Branch
- **File:** `improved_scoring_engine.py`  
- **Lines:** 103–105  
- **Severity:** MEDIUM  
- **Category:** Logic Flaw  
- **Description:** `if pd.notna(volume_ratio) and price_change_20d > 0` — if `price_change_20d` was never set (e.g., key missing), it uses default 0.  
- **Impact:** Volume bonus only applies when `price_change_20d > 0`; default 0 is fine. Minor edge case.  
- **Suggested fix:** Ensure `price_change_20d` is defined before use; default is safe.

### LOW

#### ISSUE 2.5: Debt-to-Equity Condition Order
- **File:** `improved_scoring_engine.py`  
- **Lines:** 192–201  
- **Severity:** LOW  
- **Category:** Logic Flaw  
- **Description:** Order is `> 200` then `> 150`. For 175, correct branch is hit. For 250, `> 200` is hit. Correct.  
- **Impact:** None; logic is correct.  
- **Suggested fix:** None.

---

## 3. corrected_scoring_engine.py (V2)

### CRITICAL

#### ISSUE 3.1: year_high / year_low Key Mismatch
- **File:** `corrected_scoring_engine.py`  
- **Lines:** 171–172, 175, 179–180  
- **Severity:** CRITICAL  
- **Category:** Logic Flaw  
- **Description:** Engine expects `year_high` and `year_low`. Main data uses `52_week_high` and `52_week_low`.  
- **Impact:** When `year_high`/`year_low` are missing, defaults `current_price * 1.2` and `current_price * 0.8` are used. Value opportunity is often wrong.  
- **Suggested fix:**  
  `year_high = float(stock_data.get('year_high') or stock_data.get('52_week_high') or current_price * 1.2)`  
  `year_low = float(stock_data.get('year_low') or stock_data.get('52_week_low') or current_price * 0.8)`

### HIGH

#### ISSUE 3.2: Volume Score Ignores Price Direction
- **File:** `corrected_scoring_engine.py`  
- **Lines:** 73–74  
- **Severity:** HIGH  
- **Category:** Logic Flaw  
- **Description:** Docstring says "higher volume on decline = capitulation" but the formula rewards any `volume_ratio > 1`, regardless of price direction.  
- **Impact:** Volume on up days is rewarded as if it were capitulation.  
- **Suggested fix:** Only add volume_score when `price_change_5d < 0` (decline).

#### ISSUE 3.3: Symbol Suffix for Sector Lookup
- **File:** `corrected_scoring_engine.py`  
- **Lines:** 193–206, 209–211  
- **Severity:** HIGH  
- **Category:** Logic Flaw  
- **Description:** Same as improved: `symbol in banking_stocks` fails if `symbol` is `"SBIN.NS"`.  
- **Impact:** Sector lookup fails for symbols with `.NS` suffix.  
- **Suggested fix:** `base_symbol = symbol.replace('.NS', '').upper()` before lookup.

#### ISSUE 3.4: Division by Zero — year_high
- **File:** `corrected_scoring_engine.py`  
- **Lines:** 175  
- **Severity:** HIGH  
- **Category:** Edge Case  
- **Description:** `price_from_high = (year_high - current_price) / year_high * 100`. If `year_high` is 0, division by zero.  
- **Impact:** Crash when `year_high` is 0.  
- **Suggested fix:** `year_high = year_high or current_price` and guard: `if year_high <= 0: year_high = current_price`.

### MEDIUM

#### ISSUE 3.5: Misleading component_weights
- **File:** `corrected_scoring_engine.py`  
- **Lines:** 24–31, 233–239  
- **Severity:** MEDIUM  
- **Category:** Logic Flaw  
- **Description:** `component_weights` includes `sector_adjustment: 0.10` and `timing_factor: 0.10`, but they are not used in the weighted sum. They are applied as multipliers.  
- **Impact:** Weights sum to 1.0 but only 4 are used in the linear combination; base score is 0–80.  
- **Suggested fix:** Document that sector and timing are multipliers, not linear weights; or rename `component_weights` to reflect usage.

#### ISSUE 3.6: Debt-to-Equity Unit — Corrected
- **File:** `corrected_scoring_engine.py`  
- **Lines:** 146  
- **Severity:** MEDIUM  
- **Category:** Unit Mismatch  
- **Description:** `debt_score = max(0, 100 - debt_to_equity * 25)` assumes ratio (0–4).  
- **Impact:** If yfinance returns ratio, this is correct. If another source returns percentage, it would be wrong.  
- **Suggested fix:** Document expected unit; add conversion if needed.

#### ISSUE 3.7: Seasonal Inconsistency
- **File:** `corrected_scoring_engine.py`  
- **Lines:** 41–54  
- **Severity:** MEDIUM  
- **Category:** Logic Flaw  
- **Description:** May: 1.10, June: 0.80. improved_scoring: May and June are unfavorable (0.95).  
- **Impact:** Different engines give different timing for the same month.  
- **Suggested fix:** Align seasonal logic across engines or document as intentional.

### LOW

#### ISSUE 3.8: Limited Sector Coverage
- **File:** `corrected_scoring_engine.py`  
- **Lines:** 196–207  
- **Severity:** LOW  
- **Category:** Logic Flaw  
- **Description:** Only banking and financial sectors are mapped; others use `'Others'`.  
- **Impact:** Most stocks get neutral multiplier.  
- **Suggested fix:** Expand or document as intentional.

---

## 4. Weight Verification

| Engine | Regime/Profile | Weights | Sum |
|--------|----------------|---------|-----|
| hybrid | bullish | 0.25, 0.40, 0.20, 0.10, 0.05 | 1.00 ✓ |
| hybrid | bearish | 0.50, 0.15, 0.10, 0.10, 0.15 | 1.00 ✓ |
| hybrid | neutral | 0.45, 0.25, 0.15, 0.10, 0.05 | 1.00 ✓ |
| improved | aggressive | 0.20, 0.40, 0.30, 0.10 | 1.00 ✓ |
| improved | conservative | 0.50, 0.20, 0.15, 0.15 | 1.00 ✓ |
| improved | moderate | 0.40, 0.30, 0.20, 0.10 | 1.00 ✓ |
| corrected | — | 4 components sum to 0.80; sector + timing are multipliers | N/A |

---

## 5. Layer 1 Debt-to-Equity Fix Confirmation

User mentioned: "Layer 1 already fixed debt-to-equity thresholds (lines 194-201, 234)" in improved_scoring_engine.

- **Lines 194–201:** `debt_to_equity < 50`, `< 100`, `> 200`, `> 150` — thresholds are present; logic is correct for percentage units.
- **Line 234:** `debt_to_equity < 100` in quality_multiplier — present.

The fix is in place; the remaining issue is **unit mismatch** between yfinance (ratio) and these thresholds (percentage). Layer 1 does not convert ratio to percentage in `enhanced_fundamental_analyzer.py` line 90.

---

## 6. Recommended Fix Priority

1. **CRITICAL:** Debt-to-equity unit consistency across hybrid and improved (convert ratio → percentage or change thresholds).
2. **CRITICAL:** `year_high`/`year_low` vs `52_week_high`/`52_week_low` in corrected.
3. **HIGH:** Symbol normalization (`.NS` removal) before sector lookup in improved and corrected.
4. **HIGH:** Division-by-zero guards for `sma_50` and `year_high`.
5. **HIGH:** Volume score logic in corrected (only reward volume on decline).
6. **MEDIUM:** NaN handling in hybrid.
7. **MEDIUM:** Remove dead code and fix labels in hybrid and improved.
