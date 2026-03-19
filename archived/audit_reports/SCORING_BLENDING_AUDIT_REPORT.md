# Scoring & Blending Section Audit Report

**File:** `analyze_top200_stocks_enhanced.py`  
**Lines:** 1900–2600 (scoring, blending, recommendation logic)  
**Date:** 2025-03-13

---

## Executive Summary

This audit covers the central orchestrator logic that blends scores from multiple engines and generates final recommendations. Findings are grouped by severity: CRITICAL, HIGH, MEDIUM, and LOW.

---

## 1. CRITICAL Findings

### C1. `regime_performance` lookup uses unmapped regime key — BULL/BEAR always fall back to SIDEWAYS

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2229–2232 | `regime_performance = self.adaptive_strategy.market_performance.get(regime_key, ...)` uses `regime_key` (BULL/BEAR/SIDEWAYS) directly. `market_performance` keys are `BULL_MODERATE`, `BEAR_MODERATE`, `SIDEWAYS`, `CALM`. BULL and BEAR are never found, so the fallback to SIDEWAYS is always used. | Map `regime_key` before lookup: `mapped_regime = self.adaptive_strategy._map_regime(regime_key)` then `regime_performance = self.adaptive_strategy.market_performance.get(mapped_regime, self.adaptive_strategy.market_performance['SIDEWAYS'])` |

**Impact:** In BULL and BEAR regimes, `best_quintile` and `strategy` come from SIDEWAYS instead of BULL_MODERATE/BEAR_MODERATE. Adaptive recommendations and quintile preferences are wrong.

---

### C2. Scoring engines not wrapped in try/except — crash on engine errors

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2172, 2186 | `corrected_results` and `improved_results` are computed without try/except. If `calculate_corrected_overall_score` or `calculate_improved_overall_score` raises or returns a malformed dict, the whole analysis fails. | Wrap both calls in try/except; on failure, use safe defaults (e.g. 50 for scores) and log the error. |

**Impact:** One bad engine result can stop analysis for all stocks.

---

### C3. `base_score` / `portfolio_context_score` can be None — arithmetic errors

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2025, 2027 | `base_score = stock_data.get('overall_score_with_value', 50)` and `context_adjustment = (stock_data.get('portfolio_context_score', 100) - 100) * context_weight`. If the key exists but the value is `None`, `.get()` returns `None`, not the default. | Use `stock_data.get('overall_score_with_value') or 50` and `(stock_data.get('portfolio_context_score') or 100) - 100`. |

**Impact:** `TypeError` when computing `phase1_adjusted_score` if upstream data has `None` values.

---

## 2. HIGH Findings

### H1. Phase1 recommendation uses hardcoded thresholds and omits WEAK SELL

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2492–2498 | `phase1_recommendation` uses 70, 60, 40 instead of `_config.STRONG_BUY_THRESHOLD`, `_config.BUY_THRESHOLD`, `_config.HOLD_THRESHOLD` (70, 60, 50). HOLD/SELL boundary is 40 vs config 50. No WEAK SELL tier (40–50). No `is_undervalued` for STRONG BUY vs BUY. | Use `_config` thresholds and add WEAK SELL: `'WEAK SELL' if _p1_score >= 40 else 'SELL'`. Optionally add `is_undervalued` for STRONG BUY/BUY differentiation. |

**Impact:** Phase1 recommendations differ from Phase2 and config; scores 40–50 are HOLD instead of WEAK SELL.

---

### H2. `data_quality` can be None — quality penalty fails

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2424–2428 | `data_quality = stock_data.get('data_quality_score', 100)`. If the value is `None`, `data_quality < 60` raises `TypeError`. | Use `data_quality = stock_data.get('data_quality_score') or 100`. |

**Impact:** Crash when applying quality penalty if `data_quality_score` is `None`.

---

### H3. Crisis adjustment not wrapped in try/except

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2388–2395 | `self.crisis_detector.get_stock_crisis_adjustment(...)` is called without try/except. Any exception propagates and stops analysis. | Wrap in try/except; on failure, set `_crisis_adj = 0` and log. |

**Impact:** One crisis-detector failure can stop analysis for all stocks.

---

### H4. `calculate_undervaluation_score` can return None or raise

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 1934, 1957 | `undervaluation_score = self.calculate_undervaluation_score(stock_data)` is used in `overall_score_with_value` and `is_undervalued`. If it returns `None` or raises, downstream logic can fail. | The function has a try/except; ensure it always returns a float (e.g. 50 on exception). Add `undervaluation_score = self.calculate_undervaluation_score(stock_data) or 50` and/or guard in `calculate_undervaluation_score`. |

**Impact:** `TypeError` or incorrect `is_undervalued` for malformed data.

---

## 3. MEDIUM Findings

### M1. Regime consistency — `market_regime` vs `market_regime_detected`

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2221, 2248, 2490, 2493 | `regime_key` comes from `self.current_market_regime`; `market_regime_detected` is stored in `stock_data`. `stock_data['market_regime']` is set earlier (1769). When hybrid fails, `market_regime_detected` is `UNKNOWN`; fallback uses `stock_data['market_regime']`. Logic is correct but could be clearer. | Add a short comment or helper that documents the preferred regime source and fallback chain. |

**Impact:** Low; logic is correct but harder to maintain.

---

### M2. Engine components with None values

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 1910–1938 | `enhanced_score`, `real_tech_score`, etc. use `.get(..., 50)`. If the key exists with value `None`, the default is not used. | Use `(stock_data.get('fundamental_score') or 50)`-style patterns for critical components. |

**Impact:** Possible `TypeError` when computing `advanced_tech_score` and related scores.

---

### M3. Volume exception fallback logic

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2168 | `base_score_for_volume if 'base_score_for_volume' in locals()` — if the exception occurs on line 2135, `base_score_for_volume` may not exist. Fallback to `stock_data.get('sentiment_adjusted_score', base_score_for_sentiment)` is correct. | Logic is fine; consider a short comment explaining the fallback order. |

**Impact:** None; behavior is correct.

---

## 4. LOW Findings

### L1. `_hold_thr` not regime-adjusted

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2500 | `_hold_thr = _config.HOLD_THRESHOLD` — HOLD threshold is not adjusted by regime, unlike STRONG_BUY and BUY. | If intentional, add a comment. If not, consider regime-based adjustment for HOLD. |

**Impact:** Low; may be by design.

---

### L2. `adaptive_strategy.market_performance['SIDEWAYS']` fallback

| Line(s) | Description | Suggested Fix |
|---------|-------------|---------------|
| 2231 | Fallback assumes `'SIDEWAYS'` exists in `market_performance`. It does in the current implementation. | Add a defensive check or use `.get('SIDEWAYS', {...})` with a minimal default dict if the structure changes. |

**Impact:** Low; current code is safe.

---

## 5. Verified Correct

### V1. ENABLE_SENTIMENT_ADJUSTMENT flag

- **Lines 2071–2126:** The `if not self.ENABLE_SENTIMENT_ADJUSTMENT` branch correctly sets `sentiment_adjusted_score` from `regime_adjusted_score`. The `else` branch correctly wraps the try/except. When disabled, sentiment adjustment is skipped as intended.

### V2. Phase1 recommendation derivation from `phase1_adjusted_score`

- **Lines 2492–2498:** `phase1_recommendation` is derived from `stock_data.get('phase1_adjusted_score', best_score)`, which is the correct Phase1 score. The issue is only the threshold logic (see H1).

### V3. Signal conviction scaling

- **Lines 2397–2413:** `_agreement = max(_bullish_n, _bearish_n) / _active` is safe because it runs only when `_active > 0`. `_conviction_scale = 0.5 + 0.5 * _agreement` ranges from 0.5 (split) to 1.0 (unanimous). The formula is consistent and mathematically sound.

### V4. Graduated quality penalty

- **Lines 2427–2431:** `_quality_penalty = max(0, (60 - data_quality) * 0.25) if data_quality < 60 else 0` is linear, with a maximum of 15 when `data_quality = 0`. The comment matches the implementation.

### V5. Regime mapping for adaptive weights and position sizing

- **Lines 2222–2228:** `get_adaptive_scoring_weights(regime_key)` and `get_position_sizing_strategy(regime_key)` use `_map_regime` internally, so BULL→BULL_MODERATE and BEAR→BEAR_MODERATE are handled correctly. Only the `regime_performance` lookup (C1) is wrong.

### V6. Sector double-count fix

- **Lines 2441–2457:** Sector adjustment is applied only when `hybrid_score <= 0` (fallback path). The primary hybrid path correctly skips the direct sector add.

### V7. GAP-Q1 final score storage

- **Lines 2466–2468:** `final_blended_score` is stored after all adjustments (quality, portfolio fit, sector, cap). Correct.

---

## 6. Edge Cases — Engines Return Errors/None

| Scenario | Current Behavior | Recommendation |
|----------|------------------|----------------|
| `corrected_scoring_engine` raises | Unhandled; analysis fails | Wrap in try/except (C2) |
| `improved_scoring_engine` raises | Unhandled; analysis fails | Wrap in try/except (C2) |
| `hybrid_scoring_engine` raises | Caught; fallback to `improved_results` | OK |
| Engine returns dict with missing keys | `KeyError` on access | Add `.get()` with defaults or validate structure |
| Engine returns `None` for score | Propagates; possible `TypeError` | Add `or 50`-style fallbacks |
| `regime_detector.adjust_stock_score_by_regime` raises | Caught; uses `phase1_adjusted_score` | OK |
| `sentiment_analyzer.adjust_score_by_sentiment` raises | Caught; uses `base_score_for_sentiment` | OK |
| `volume_analyzer.adjust_score_by_volume` raises | Caught; uses `base_score_for_volume` or fallback | OK |
| `crisis_detector.get_stock_crisis_adjustment` raises | Unhandled; analysis fails | Add try/except (H3) |

---

## 7. Summary Table

| ID | Severity | Line(s) | Category |
|----|----------|---------|----------|
| C1 | CRITICAL | 2229–2232 | Logic flaw |
| C2 | CRITICAL | 2172, 2186 | Edge case / robustness |
| C3 | CRITICAL | 2025, 2027 | Data flow |
| H1 | HIGH | 2492–2498 | Logic flaw |
| H2 | HIGH | 2424–2428 | Edge case |
| H3 | HIGH | 2388–2395 | Edge case |
| H4 | HIGH | 1934, 1957 | Edge case |
| M1 | MEDIUM | 2221, 2490 | Regime consistency |
| M2 | MEDIUM | 1910–1938 | Data flow |
| M3 | MEDIUM | 2168 | Documentation |
| L1 | LOW | 2500 | Logic |
| L2 | LOW | 2231 | Defensive coding |

---

## 8. Recommended Fix Order

1. **C1** — Map regime before `market_performance` lookup.
2. **C2** — Wrap corrected and improved scoring engines in try/except.
3. **C3** — Use `or` defaults for `base_score` and `portfolio_context_score`.
4. **H1** — Align Phase1 thresholds with config and add WEAK SELL.
5. **H2** — Use `or 100` for `data_quality`.
6. **H3** — Wrap crisis adjustment in try/except.
7. **H4** — Ensure `calculate_undervaluation_score` always returns a float.
