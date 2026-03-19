# Final Score Blending Pipeline & Recommendation Engine Audit

**File:** `analyze_top200_stocks_enhanced.py`  
**Scope:** Sections 1–3 (Score computation, blending, recommendation engine, sub-functions)  
**Context:** Bear-market inverted quintile spread — higher-scored stocks perform worse. Blending pipeline is the central corruption point.

---

## SECTION 1: Score Computation and Blending (~lines 1900–2470)

### BUG: Sentiment `volume_surge` — String vs Numeric Type Mismatch

| Field | Value |
|-------|-------|
| **File:Line(s)** | 2102 |
| **Type** | BUG |
| **Severity** | CRITICAL |
| **Description** | `stock_data.get('volume_trend', 1.0)` is passed as `news_sentiment['volume_surge']`. `volume_trend` is a **string** (e.g. `'HIGH'`, `'AVERAGE'`, `'Low'`) from real/technical/volume analysis. `sentiment_analyzer.adjust_score_by_sentiment` at line 487 does `news.get('volume_surge', 1) > 2`, expecting a numeric ratio. Passing a string causes `TypeError` (str vs int comparison) or wrong comparison logic. |
| **Impact on accuracy** | Sentiment adjustment can crash or produce incorrect results. |
| **Fix** | (a) Store `news_volume_surge` from `sentiment_data['news_sentiment']['volume_surge']` when updating from sentiment (line 1822); use `stock_data.get('news_volume_surge', 1.0)`. Or (b) convert string to numeric: `{'HIGH','High','ABOVE_AVERAGE'}: 1.5`, `{'LOW','Low'}: 0.7`, else: 1.0. |

---

### BUG: `debt_to_equity` Unit Mismatch in Undervaluation Score

| Field | Value |
|-------|-------|
| **File:Line(s)** | 4311–4324 |
| **Type** | BUG |
| **Severity** | CRITICAL |
| **Description** | `calculate_undervaluation_score` uses D/E thresholds 30, 50, 70, 100 as if they were **percentages**. Cache shows `debt_to_equity` as **ratio** (e.g. ACC: 2.435, ABB: 1.082). A ratio of 2.4 gets `debt_score = 100` because `2.4 <= 30`. High-debt companies are scored as low-debt. |
| **Impact on accuracy** | Undervaluation score heavily favors high-debt companies; value scoring is inverted. |
| **Fix** | (a) Normalize: `debt_pct = debt_eq * 100 if debt_eq < 10 else debt_eq` (assume ratio if < 10). Or (b) use ratio thresholds: `< 0.3`, `< 0.5`, `< 0.7`, `< 1.0` for low/moderate/high. |

---

### BUG: `debt_to_equity` Unit Mismatch in Hybrid Engine

| Field | Value |
|-------|-------|
| **File:Line(s)** | hybrid_optimized_scoring.py:112–117 |
| **Type** | BUG |
| **Severity** | HIGH |
| **Description** | Same thresholds as undervaluation: `< 30`, `< 60`, `< 100` treated as percentage. With ratio inputs, high-debt scores get quality signal. |
| **Impact on accuracy** | Fundamental quality score inflated for leveraged firms. |
| **Fix** | Same unit normalization as undervaluation. |

---

### GAP: Regime Source Mismatch — `market_regime` vs `market_regime_detected`

| Field | Value |
|-------|-------|
| **File:Line(s)** | 2488 vs 2519 |
| **Type** | GAP |
| **Severity** | HIGH |
| **Description** | Threshold logic uses `stock_data.get('market_regime', 'SIDEWAYS')` (2488). Adaptive regime labels use `stock_data.get('market_regime_detected', 'UNKNOWN')` (2519). If hybrid fails, `market_regime_detected` is `'UNKNOWN'` but `market_regime` may be `'BEAR'`. Thresholds are correct; adaptive labels are wrong. |
| **Impact on accuracy** | Adaptive regime labels may be wrong even when thresholds are correct. |
| **Fix** | Use a single source: `_curr_regime = stock_data.get('market_regime_detected') or stock_data.get('market_regime', 'SIDEWAYS')` for both. |

---

### GAP: `base_score_for_sentiment` Undefined in Except Path

| Field | Value |
|-------|-------|
| **File:Line(s)** | 2134–2137 |
| **Type** | GAP |
| **Severity** | MEDIUM |
| **Description** | `except` block uses `base_score_for_sentiment`; if the exception occurs before line 2093, `base_score_for_sentiment` is never defined. |
| **Impact on accuracy** | Potential `NameError` and crash. |
| **Fix** | Define `base_score_for_sentiment` before the try: `base_score_for_sentiment = stock_data.get('regime_adjusted_score', phase1_adjusted_score)`. |

---

### GAP: `base_score_for_volume` Fallback in Except

| Field | Value |
|-------|-------|
| **File:Line(s)** | 2177 |
| **Type** | GAP |
| **Severity** | LOW |
| **Description** | `stock_data['volume_adjusted_score'] = base_score_for_volume if 'base_score_for_volume' in locals() else ...` — `locals()` is fragile; `base_score_for_volume` is always set at 2145 in the try. |
| **Impact on accuracy** | Minor; fallback logic is correct but redundant. |
| **Fix** | Simplify: `base_score_for_volume = stock_data.get('sentiment_adjusted_score', base_score_for_sentiment)` before try. |

---

### GAP: Two Different Data Quality Implementations

| Field | Value |
|-------|-------|
| **File:Line(s)** | 623–678 (`calculate_data_quality_score`) vs 1468–1488 (`_calculate_data_quality_score`) |
| **Type** | GAP |
| **Severity** | MEDIUM |
| **Description** | `enhanced_data_validation` calls `_calculate_data_quality_score` (critical: 15 each, important: 5 each). `calculate_data_quality_score` uses different penalties (25,20,15,10 for critical). Final score overwrites with the public method. The validation’s internal score is unused. |
| **Impact on accuracy** | Redundant work; inconsistent quality definitions if used elsewhere. |
| **Fix** | Use a single implementation; have `enhanced_data_validation` call `calculate_data_quality_score` or vice versa. |

---

### BUG: Quality Penalty — Binary Step Function

| Field | Value |
|-------|-------|
| **File:Line(s)** | 2423–2428 |
| **Type** | BUG (design) |
| **Severity** | MEDIUM |
| **Description** | Quality penalty is binary: `< 40` → −10, `< 60` → −5. A score of 39 vs 41 is a 10-point jump; 59 vs 61 is a 5-point jump. |
| **Impact on accuracy** | Discontinuities at thresholds; noisy around 40 and 60. |
| **Fix** | Use a graduated penalty: e.g. `penalty = max(0, (60 - data_quality) * 0.25)` capped at ±10. |

---

### BUG: Portfolio Fit — Unset When Context Fails

| Field | Value |
|-------|-------|
| **File:Line(s)** | 2035–2037 |
| **Type** | GAP |
| **Severity** | LOW |
| **Description** | On portfolio context exception, only `portfolio_context_score` and `diversification_benefit` are set. `portfolio_fit` is not set. |
| **Impact on accuracy** | `portfolio_fit` is `'unknown'` via `get(..., 'unknown')`; portfolio fit bonus/penalty is skipped. |
| **Fix** | Add `stock_data['portfolio_fit'] = 'unknown'` in the except block. |

---

### BUG: `pre_adj_blended_score` Naming

| Field | Value |
|-------|-------|
| **File:Line(s)** | 2417 |
| **Type** | GAP |
| **Severity** | LOW |
| **Description** | `pre_adj_blended_score` is set after ml+sent+vol+pattern+crisis, but before quality/portfolio/sector. The name suggests “pre all adjustments.” |
| **Impact on accuracy** | Misleading for debugging; no functional impact. |
| **Fix** | Rename to `pre_quality_portfolio_sector_score` or `blended_before_quality` for clarity. |

---

### VERIFIED: Phase 1 Formula

| Component | Formula |
|-----------|---------|
| `quality_adjustment` | `(data_quality_score - 50) * 0.20` |
| `context_adjustment` | `(portfolio_context_score - 100) * 0.15` |
| `phase1_adjusted_score` | `base_score + quality_adjustment + context_adjustment` |

Base is `overall_score_with_value`. Regime adjustment uses `phase1_adjusted_score` as input. Correct.

---

### VERIFIED: Regime Adjustment Base

Regime adjustment is applied to `phase1_adjusted_score` (2069). Correct.

---

### VERIFIED: Volume Adjustment

Volume adjustment uses `sentiment_adjusted_score` as base. Correct.

---

### VERIFIED: ML Adjustment

- Confidence threshold: 40
- Cap: ±8
- Source check: `ml_model_source == 'trained_model'`
- Applied in `final_blended_score` (2411). Correct.

---

### VERIFIED: Pattern Adjustment

Pattern is not double-counted: `advanced_tech_score` feeds `overall_score_with_value` → phase1, but `final_blended_score` uses `hybrid_score` (not phase1). Pattern is added separately. Correct.

---

### VERIFIED: Crisis Adjustment

`get_stock_crisis_adjustment(symbol, sector, crisis_data)` is called with correct arguments. Correct.

---

### VERIFIED: Sector Double-Count Fix

Sector adj is applied only when `hybrid_score <= 0` (fallback path). Correct.

---

### VERIFIED: Final Clamping

`final_blended_score = max(0, min(100, final_blended_score))` at 2458. Correct.

---

## SECTION 2: Recommendation Engine (~lines 2470–2610)

### BUG: Regime Source for Thresholds

| Field | Value |
|-------|-------|
| **File:Line(s)** | 2488 |
| **Type** | BUG |
| **Severity** | MEDIUM |
| **Description** | `market_regime` is set in the regime block; `market_regime_detected` is set in the hybrid block. If hybrid fails, `market_regime_detected` is `'UNKNOWN'` but `market_regime` may be `'BEAR'`. Thresholds use `market_regime`, so they should be correct. But if `market_regime` is missing for some reason, fallback is `'SIDEWAYS'`. |
| **Impact on accuracy** | In edge cases, regime-based thresholds may be wrong. |
| **Fix** | Use `market_regime_detected or market_regime` for consistency. |

---

### VERIFIED: Undervaluation Logic

`is_undervalued = undervaluation_score >= _config.UNDERVALUED_THRESHOLD` (A-009). Correct.

---

### VERIFIED: Data Quality Gate

`data_quality < 30` → HOLD. Correct.

---

### VERIFIED: ML Confirmation/Conflict

ML confirmation/conflict is appended to recommendation (2543–2550). Correct.

---

### VERIFIED: Adaptive Regime Labels

Adaptive labels use `market_regime_detected`; BULL/BEAR/SIDEWAYS logic is correct. Correct.

---

## SECTION 3: Score Sub-Functions

### BUG: `calculate_undervaluation_score` — D/E Thresholds

| Field | Value |
|-------|-------|
| **File:Line(s)** | 4311–4324 |
| **Type** | BUG |
| **Severity** | CRITICAL |
| **Description** | Thresholds 30, 50, 70, 100 assume percentage. yfinance returns ratio. |
| **Impact on accuracy** | Debt component inverted. |
| **Fix** | See Section 1 fix above. |

---

### BUG: `calculate_momentum_growth_score` — `profit_growth` vs `earnings_growth`

| Field | Value |
|-------|-------|
| **File:Line(s)** | 4430 |
| **Type** | BUG |
| **Severity** | MEDIUM |
| **Description** | Uses `profit_growth` but many sources provide `earnings_growth`. If `profit_growth` is missing and `earnings_growth` exists, the component is skipped. |
| **Impact on accuracy** | Growth momentum underweighted when profit_growth is absent. |
| **Fix** | Use `stock_data.get('profit_growth') or stock_data.get('earnings_growth', 0)`. |

---

### VERIFIED: `calculate_risk_return_metrics`

Uses `final_blended_score` (GAP-RISK-SCORE fix). Correct.

---

### VERIFIED: `_calculate_data_quality_score` (1468)

Used in `enhanced_data_validation`; final score is overwritten by `calculate_data_quality_score`. Correct.

---

## UPGRADE RECOMMENDATIONS

### UPGRADE 1: Multiplicative Blending

| Component | Current | Change |
|-----------|---------|--------|
| **Description** | Additive adjustments: `score + adj1 + adj2 + ...` | Use multiplicative: `score * (1 + 0.05 * signal)` for signals |
| **Impact** | Reduces impact of extreme adjustments; avoids runaway scores |
| **Implementation** | Add a `blending_mode` flag; for multiplicative, apply `base * (1 + sum(adj_i/100))` for small adjustments |

---

### UPGRADE 2: Reduce ML Cap

| Component | Current | Change |
|-----------|---------|--------|
| **Description** | ML adjustment ±8 pts | Reduce to ±4 pts |
| **Impact** | ML CV 39.77%; cap should reflect model uncertainty |
| **Implementation** | Change line 2442–2443: `round(_scaled * 4, 1)` instead of 8 |

---

### UPGRADE 3: Market-Relative Return Factor

| Component | Current | Change |
|-----------|---------|--------|
| **Description** | No explicit market-relative return | Add `stock_return_1m - nifty_return_1m` as factor |
| **Impact** | Reduces bear-market inversion when high-momentum stocks underperform |
| **Implementation** | Add `market_relative_return` to hybrid scoring; weight by regime (higher in bear) |

---

### UPGRADE 4: Graduated Quality Penalty

| Component | Current | Change |
|-----------|---------|--------|
| **Description** | Binary: −10 if <40, −5 if <60 | Graduated: `penalty = (60 - quality) * 0.25` capped at 10 |
| **Impact** | Smoother behavior near thresholds |
| **Implementation** | Replace lines 2423–2428 with graduated formula |

---

### UPGRADE 5: Conviction Score

| Component | Current | Change |
|-----------|---------|--------|
| **Description** | No explicit signal agreement metric | Compute `conviction_score` = agreement among ML, pattern, sentiment, volume |
| **Impact** | Higher conviction when signals align; lower when they conflict |
| **Implementation** | Add `conviction_score = sum(1 for s in [ml, pattern, sent, vol] if s == dominant) / 4`; use as confidence multiplier |

---

### UPGRADE 6: Max-Drawdown / Trend-Reversal Penalty

| Component | Current | Change |
|-----------|---------|--------|
| **Description** | No drawdown penalty in blending | Add penalty for max_drawdown_6m > 20% |
| **Impact** | Reduces score for stocks with large recent drawdowns |
| **Implementation** | `if max_drawdown_6m > 20: final_blended_score -= min(5, (max_drawdown_6m - 20) / 4)` |

---

### UPGRADE 7: Wider Regime Threshold Spreads in Bear

| Component | Current | Change |
|-----------|---------|--------|
| **Description** | Bear: +5 to thresholds; Bull: −2 | Bear: +8 for STRONG_BUY, +6 for BUY |
| **Impact** | Reduces over-buying in bear markets |
| **Implementation** | `_regime_thr_delta = (8, 6) if _is_bear else (-2, -1) if _is_bull else (0, 0)` for strong_buy and buy |

---

## SUMMARY

| Type | Count |
|------|-------|
| BUG | 8 |
| GAP | 6 |
| UPGRADE | 7 |

**Critical fixes:**  
1. `volume_trend` → `volume_surge` conversion (string)  
2. `debt_to_equity` unit in undervaluation and hybrid scoring  

**High-priority fixes:**  
3. Regime source consistency (market_regime vs market_regime_detected)  
4. D/E in hybrid engine  

**Recommendation:** Prioritize the two critical bugs and the regime source fix before further backtesting.
