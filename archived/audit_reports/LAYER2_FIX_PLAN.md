# Layer 2 Fix Plan — Scoring and Signal Processing

**Created:** 2026-03-12  
**Branch:** `fix/system-accuracy-gaps`  
**Total items:** 26 Bugs + 14 Gaps + 16 Upgrades across 12 files  
**Phases:** 4 (fix bear-market collapse → reduce noise → improve precision → future-proof)

---

## Phase 1: Fix Bear-Market Collapse (B1-B6, U1-U6)
> These 12 changes directly address why the system picks losers in bear markets.  
> Expected: quintile spread from inverted (-3%) → positive (+3-5%)

---

### P1-01: Fix contrarian momentum — penalize downtrends (B1 + U1)
**File:** `improved_scoring_engine.py`  
**Lines:** 122-132  
**Severity:** CRITICAL

**Root cause:** `abs(price_change_20d)` treats a -10% crash the same as +10% rally. In bear markets, falling stocks get high momentum scores, directly causing inverted quintile spread.

**Current code (line 123-124):**
```python
if pd.notna(price_change_20d):
    abs_change = abs(price_change_20d)
```

**Fix:** Replace `abs()` with signed scoring — reward uptrends, penalize downtrends:
```python
if pd.notna(price_change_20d):
    if price_change_20d >= 15:
        trend_score = 25
    elif price_change_20d >= 8:
        trend_score = 20
    elif price_change_20d >= 3:
        trend_score = 15
    elif price_change_20d >= -3:
        trend_score = 10
    elif price_change_20d >= -8:
        trend_score = 5
    else:
        trend_score = 0
```

**Verification:** After fix, run backtest — Q5 should outperform Q1 in bear markets.

---

### P1-02: Fix volume_trend string → numeric (B2)
**File:** `analyze_top200_stocks_enhanced.py`  
**Lines:** 2100-2103  
**Severity:** CRITICAL

**Root cause:** `volume_trend` is a string like `'HIGH'`/`'AVERAGE'`/`'LOW'` but is passed as `volume_surge` which expects a numeric ratio. Causes TypeError in sentiment analyzer.

**Current code (line 2102):**
```python
'volume_surge': stock_data.get('volume_trend', 1.0)
```

**Fix:** Map string to numeric before passing:
```python
_vol_trend_map = {'VERY_HIGH': 3.0, 'HIGH': 2.5, 'ABOVE_AVERAGE': 1.5,
                  'AVERAGE': 1.0, 'BELOW_AVERAGE': 0.7, 'LOW': 0.5, 'VERY_LOW': 0.3}
_vol_trend_raw = stock_data.get('volume_trend', 'AVERAGE')
_vol_surge = _vol_trend_map.get(str(_vol_trend_raw).upper(), 1.0) if isinstance(_vol_trend_raw, str) else float(_vol_trend_raw or 1.0)
# Then use:
'volume_surge': _vol_surge
```

**Verification:** No more TypeError; sentiment adjustment runs without crash.

---

### P1-03: Fix regime key mismatch in adaptive strategy (B3 + U6)
**File:** `adaptive_market_strategy.py`  
**Lines:** 20-52 (dicts), 187-189 (get_position_sizing), 191-195 (generate_recs)  
**Severity:** CRITICAL

**Root cause:** `market_regime_detector` returns `BULL`/`BEAR`/`SIDEWAYS`. `adaptive_market_strategy` dicts use `BULL_MODERATE`/`BEAR_MODERATE`/`SIDEWAYS`/`CALM`. Lookups for `BULL`/`BEAR` fall through to `CALM` defaults. Bear-market position sizing never activates.

**Fix:** Add regime mapping at top of class (after `__init__` dicts):
```python
REGIME_MAP = {
    'BULL': 'BULL_MODERATE', 'BULL_STRONG': 'BULL_MODERATE', 'BULLISH': 'BULL_MODERATE',
    'BEAR': 'BEAR_MODERATE', 'BEAR_STRONG': 'BEAR_MODERATE', 'BEARISH': 'BEAR_MODERATE',
    'SIDEWAYS': 'SIDEWAYS', 'CALM': 'CALM', 'UNKNOWN': 'CALM', 'NEUTRAL': 'CALM'
}

def _map_regime(self, regime_key):
    return self.REGIME_MAP.get(str(regime_key).upper(), 'CALM')
```

Then update all three functions to map before lookup:
- `get_position_sizing_strategy`: `mapped = self._map_regime(current_regime); return self.position_sizing.get(mapped, ...)`
- `get_adaptive_scoring_weights`: same pattern
- `generate_regime_specific_recommendations`: `mapped = self._map_regime(current_regime); regime_data = self.market_performance.get(mapped, self.market_performance['CALM']); position_strategy = self.position_sizing.get(mapped, self.position_sizing['CALM'])`

**Verification:** Pass `'BEAR'` → get `BEAR_MODERATE` sizing (60% invested, 40% cash).

---

### P1-04: Unify regime source for thresholds and labels (B4)
**File:** `analyze_top200_stocks_enhanced.py`  
**Lines:** 2487 and 2519  
**Severity:** CRITICAL

**Root cause:** Line 2487 uses `stock_data.get('market_regime', 'SIDEWAYS')` for thresholds. Line 2519 uses `stock_data.get('market_regime_detected', 'UNKNOWN')` for adaptive labels. They can disagree.

**Fix:** Use a single resolved regime variable before both sections:
```python
# Before line 2487, add:
_resolved_regime = (stock_data.get('market_regime_detected') or stock_data.get('market_regime', 'SIDEWAYS')).upper()
if _resolved_regime in ('UNKNOWN', ''):
    _resolved_regime = stock_data.get('market_regime', 'SIDEWAYS').upper()
```

Then use `_resolved_regime` in both the threshold block (line 2487) and the adaptive label block (line 2519).

**Verification:** Both threshold and label sections see the same regime.

---

### P1-05: Fix D/E thresholds in undervaluation score (B5)
**File:** `analyze_top200_stocks_enhanced.py`  
**Lines:** 4310-4324  
**Severity:** CRITICAL

**Root cause:** yfinance `debtToEquity` returns a percentage-like number (e.g. 150 for 1.5x). The Layer 1 fixes updated `hybrid_optimized_scoring.py` and `improved_scoring_engine.py` but missed `calculate_undervaluation_score`. Thresholds (30, 50, 70, 100) are already on the right scale IF yfinance returns percentages. **Verify** by checking what actual values flow in. If the Layer 1 `enhanced_fundamental_analyzer.py` stores D/E as percentage (it does — line 83 stores as-is from yfinance), then these thresholds are correct.

**Action:** Verify by adding a debug log or checking cached data. If D/E values in cache are like `150.0` (percentage), thresholds are correct. If they're like `1.5` (ratio), change to `0.3, 0.5, 0.7, 1.0`.

**Verification:** Check 3-5 cached stock files for `debt_to_equity` values.

---

### P1-06: Fix broken breadth signal in regime detector (B6 + U5)
**File:** `market_regime_detector.py`  
**Lines:** 215-243  
**Severity:** CRITICAL

**Root cause:** `_calculate_breadth_signal` counts how many of the last 20 days had `high == max(last 20 highs)`. Almost always returns 0 or 1. Breadth contributes 20% to regime score but is dead.

**Fix:** Replace with percentage of recent closes above 50-day SMA (proxy for advance-decline):
```python
def _calculate_breadth_signal(self, df: pd.DataFrame) -> float:
    if len(df) < 50:
        return 0.0
    close = df['Close']
    sma_50 = close.rolling(50).mean()
    recent = min(20, len(df) - 50)
    above_sma = (close.iloc[-recent:] > sma_50.iloc[-recent:]).sum()
    pct_above = above_sma / recent
    # Map 0-1 range to -1 to +1: 0% above → -1, 50% → 0, 100% → +1
    breadth = (pct_above - 0.5) * 2
    return np.clip(breadth, -1.0, 1.0)
```

**Verification:** In a bear market (Nifty below 50 DMA), breadth should return negative. In bull, positive.

---

### P1-07: Add relative strength vs Nifty (U2)
**File:** `hybrid_optimized_scoring.py` (new sub-score in momentum)  
**Severity:** HIGH (upgrade)

**What:** Currently scores use absolute momentum only. A stock falling 5% in a market falling 10% is actually outperforming but gets penalized.

**Fix:** Add a relative strength component to `calculate_momentum_technical_score`:
```python
nifty_return_1m = stock_data.get('nifty_return_1m', 0)
relative_strength = price_change_1m - nifty_return_1m
if relative_strength > 5:
    rs_score = 20
elif relative_strength > 2:
    rs_score = 15
elif relative_strength > -2:
    rs_score = 10
elif relative_strength > -5:
    rs_score = 5
else:
    rs_score = 0
```

**Prerequisite:** The main analyzer must pass `nifty_return_1m` in `stock_data`. This comes from regime detector's Nifty data (already fetched).

**Verification:** In bear market, stocks falling less than Nifty get higher momentum scores.

---

### P1-08: Add max-drawdown penalty (U3)
**File:** `hybrid_optimized_scoring.py` (new factor in risk_adjustment)  
**Severity:** HIGH (upgrade)

**What:** Stocks in free-fall from 52-week highs are not penalized. System catches falling knives.

**Fix:** Add to `calculate_risk_adjustment_score`:
```python
high_52w = stock_data.get('52_week_high', current_price)
if high_52w > 0:
    drawdown = (high_52w - current_price) / high_52w * 100
else:
    drawdown = 0
if drawdown > 40:
    drawdown_penalty = 30
elif drawdown > 25:
    drawdown_penalty = 20
elif drawdown > 15:
    drawdown_penalty = 10
else:
    drawdown_penalty = 0
risk_score = max(0, risk_score - drawdown_penalty)
```

**Verification:** Stocks >25% off highs get lower risk scores.

---

### P1-09: Confidence-weighted signal adjustments (U4)
**File:** `analyze_top200_stocks_enhanced.py` (blending section, ~lines 2380-2440)  
**Severity:** HIGH (upgrade)

**What:** Currently, once above threshold, all signals move the score by their full cap regardless of confidence. A 41% confidence ML signal moves score by ±8, same as 95% confidence.

**Fix:** Scale all adjustments by confidence:
```python
# For ML:
ml_effective = ml_raw_adj * min(1.0, ml_confidence / 70.0)
# For sentiment:
sent_effective = sent_raw_adj * min(1.0, sent_confidence / 70.0)
# For volume:
vol_effective = vol_raw_adj * min(1.0, vol_confidence / 70.0)
# For pattern:
pat_effective = pat_raw_adj * min(1.0, pat_confidence / 70.0)
```

**Verification:** Low-confidence signals contribute less noise; high-confidence ones keep full impact.

---

### P1-10: Fix regime mapping in main analyzer (U6 cont.)
**File:** `analyze_top200_stocks_enhanced.py` (where adaptive strategy is called)  
**Severity:** HIGH

**What:** Ensure the regime key from detector is mapped before being passed to `adaptive_market_strategy` functions.

**Fix:** Where `get_position_sizing_strategy` is called, the mapping now happens inside the strategy class (from P1-03). Confirm no additional mapping needed in the caller.

**Verification:** End-to-end: detect BEAR → map to BEAR_MODERATE → 60% invested, SMALL positions.

---

### P1-11: Fix fallback regime_score from 50 to 0.0 (B11)
**File:** `analyze_top200_stocks_enhanced.py`  
**Lines:** 1774-1781 (two occurrences)  
**Severity:** HIGH

**Current:** `'regime_score': 50` in fallback dict.  
**Fix:** Change to `'regime_score': 0.0` (neutral on the [-1, 1] scale).

**Verification:** When regime detection fails, downstream logic treats it as neutral, not extremely bullish.

---

### P1-12: Fix hybrid exception to return None/0 (B13)
**File:** `hybrid_optimized_scoring.py`  
**Line:** 404  
**Severity:** HIGH

**Current:** `return {'hybrid_score': 50, 'components': {}, 'adjustments': {}}`  
**Fix:** `return {'hybrid_score': 0, 'components': {}, 'adjustments': {}, 'error': 'calculation_failed'}`

Then in `analyze_top200_stocks_enhanced.py` blending section, the existing logic `hybrid_score if hybrid_score > 0 else improved_score` will correctly fall back.

**Verification:** On hybrid failure, improved_score is used instead of arbitrary 50.

---

## Phase 2: Reduce Noise (B7-B16, U7-U8, U11)
> Fix remaining high-severity bugs and reduce adjustment caps.  
> Expected: more stable rankings, less flip-flopping.

---

### P2-01: Fix ML fallback MACD signal check (B7)
**File:** `ml_predictor.py`  
**Lines:** 362-364  
**Severity:** HIGH

**Current:**
```python
if 'BUY' in str(macd_signal).upper():
    score += 2
elif 'SELL' in str(macd_signal).upper():
    score -= 2
```

**Fix:** Handle both naming conventions:
```python
_macd_upper = str(macd_signal).upper()
if _macd_upper in ('BUY', 'BULLISH'):
    score += 2
elif _macd_upper in ('SELL', 'BEARISH'):
    score -= 2
```

Also check `momentum_signal` on similar lines for the same issue.

---

### P2-02: Fix sentiment profit_margin unit (B8)
**File:** `sentiment_analyzer.py`  
**Line:** 313  
**Severity:** HIGH

**Current:** `profit_margin = stock_data.get('profit_margin', 0) * 100`

**Fix:** Guard against double-conversion:
```python
_pm_raw = stock_data.get('profit_margin', 0) or 0
profit_margin = _pm_raw * 100 if abs(_pm_raw) < 1.0 else _pm_raw
```

---

### P2-03: Fix hybrid SMA division by zero (B9)
**File:** `hybrid_optimized_scoring.py`  
**Line:** 181  
**Severity:** HIGH

**Current:** `price_vs_sma = ((current_price - sma_50) / sma_50) * 100`

**Fix:**
```python
price_vs_sma = ((current_price - sma_50) / sma_50) * 100 if sma_50 and sma_50 != 0 else 0
```

---

### P2-04: Add NaN/None guards to hybrid scoring inputs (B10)
**File:** `hybrid_optimized_scoring.py`  
**Lines:** Start of each calculate_* function  
**Severity:** HIGH

**Fix:** At the start of `calculate_hybrid_score`, sanitize all inputs:
```python
def _safe_float(val, default=0):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

pe_ratio = _safe_float(stock_data.get('pe_ratio'), 20)
roe = _safe_float(stock_data.get('roe'), 0)
debt_equity = _safe_float(stock_data.get('debt_to_equity'), 50)
# ... etc for all inputs
```

---

### P2-05: Fix profit_growth → earnings_growth routing (B12)
**File:** `analyze_top200_stocks_enhanced.py`  
**Line:** 4430  
**Severity:** HIGH

**Current:** `profit_growth = stock_data.get('profit_growth', 0)`

**Fix:**
```python
profit_growth = stock_data.get('profit_growth') or stock_data.get('earnings_growth', 0)
```

---

### P2-06: Fix base_score_for_sentiment NameError risk (B16)
**File:** `analyze_top200_stocks_enhanced.py`  
**Line:** Before ~2093  
**Severity:** HIGH

**Fix:** Initialize before the try block:
```python
base_score_for_sentiment = phase1_adjusted_score  # safe default
```

---

### P2-07: Fix RSI division by zero in regime detector (B15)
**File:** `market_regime_detector.py`  
**Lines:** 199-201  
**Severity:** HIGH

**Current:** `rs = gain / loss`

**Fix:**
```python
loss_safe = loss.replace(0, np.nan)
rs = gain / loss_safe
rsi = 100 - (100 / (1 + rs))
rsi = rsi.fillna(50)  # When loss is 0, RSI defaults to neutral
```

---

### P2-08: Fix bearish divergence logic (B14)
**File:** `early_breakout_detector.py`  
**Lines:** 420-435  
**Severity:** HIGH

**Current:** Returns True when `rsi < 70 and price_higher_high` — no actual divergence check.

**Fix:**
```python
def _check_bearish_divergence(self, df, stock_data):
    if len(df) < 20:
        return False
    close = df['Close']
    price_higher = close.iloc[-1] > close.iloc[-10]
    # Calculate RSI at two points
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    loss_safe = loss.replace(0, np.nan)
    rs = gain / loss_safe
    rsi_series = (100 - (100 / (1 + rs))).fillna(50)
    rsi_now = rsi_series.iloc[-1]
    rsi_prior = rsi_series.iloc[-10]
    # True divergence: price higher high BUT RSI lower high
    return price_higher and rsi_now < rsi_prior and rsi_now > 50
```

---

### P2-09: Reduce adjustment caps (U8)
**File:** `analyze_top200_stocks_enhanced.py` (blending section)  
**Severity:** MEDIUM (upgrade)

**Current caps:** ML ±8, Sentiment ±5, Volume ±5, Pattern ±4 = max ±22  
**New caps:** ML ±4, Sentiment ±3, Volume ±3, Pattern ±2 = max ±12

Change the cap/clamp values in the blending section where each adjustment is computed.

---

### P2-10: Add signal agreement conviction score (U11)
**File:** `analyze_top200_stocks_enhanced.py` (blending section)  
**Severity:** MEDIUM (upgrade)

**Fix:** After computing all adjustments, count agreement:
```python
_signals = [
    1 if ml_adj > 0 else (-1 if ml_adj < 0 else 0),
    1 if sent_adj > 0 else (-1 if sent_adj < 0 else 0),
    1 if vol_adj > 0 else (-1 if vol_adj < 0 else 0),
    1 if pat_adj > 0 else (-1 if pat_adj < 0 else 0),
]
_bullish = sum(1 for s in _signals if s > 0)
_bearish = sum(1 for s in _signals if s < 0)
_agreement = max(_bullish, _bearish) / max(1, sum(1 for s in _signals if s != 0))
# Scale total adjustment by agreement (0.5 = split signals → half impact)
_conviction_scale = 0.5 + 0.5 * _agreement
total_adjustment = (ml_adj + sent_adj + vol_adj + pat_adj) * _conviction_scale
```

---

## Phase 3: Improve Precision (B17-B26, U9-U12)
> Medium bugs and scoring refinements.

---

### P3-01: Remove duplicate enhanced_mfi from ML features (B17)
**File:** `ml_predictor.py`  
**Lines:** 145 and 176  
**Fix:** Remove one of the two `enhanced_mfi` entries from the feature vector.

### P3-02: Clamp volume adjusted_score to [0, 100] (B18)
**File:** `volume_analyzer.py` — `adjust_score_by_volume`  
**Fix:** After computing `adjusted_score`: `adjusted_score = max(0, min(100, adjusted_score))`

### P3-03: Fix asymmetric MODERATE volume handling (B19)
**File:** `volume_analyzer.py`  
**Fix:** Add SELL case for MODERATE block activity: `adjustment -= 5`

### P3-04: Fix volume profile division by zero (B20)
**File:** `volume_analyzer.py`  
**Fix:** Guard `price_min == price_max` before computing bins.

### P3-05: Update crisis detector symbols (B21)
**File:** `crisis_detector.py` line 56  
**Fix:** Replace `CAIRN` with `VEDL`, remove `GIPCL` from `OIL_UPSTREAM_SYMBOLS`.

### P3-06: Fix improved engine ADX field name (B22)
**File:** `improved_scoring_engine.py`  
**Fix:** Use `stock_data.get('enhanced_adx', stock_data.get('adx_14', 0))`

### P3-07: Use stock_data['sector'] in improved engine (B23)
**File:** `improved_scoring_engine.py`  
**Fix:** Use `stock_data.get('sector', '')` instead of hardcoded symbol-based sector map.

### P3-08: Fix triangle slope normalization (B24)
**File:** `pattern_recognition.py` lines 315-316  
**Fix:** Divide by bar distance between peaks instead of peak count.

### P3-09: Fix corrected engine field names (B25)
**File:** `corrected_scoring_engine.py`  
**Fix:** Replace `year_high`/`year_low` with `52_week_high`/`52_week_low`.

### P3-10: Add file locking to recommendation history (B26)
**File:** `recommendation_history.py`  
**Fix:** Use `fcntl.flock` for CSV writes.

### P3-11: RSI regime-aware scoring (U9)
**File:** `hybrid_optimized_scoring.py` lines 144-163  
**Fix:** In BEAR regime, RSI > 70 → penalty (overbought = avoid). Accept `market_regime` parameter:
```python
if regime == 'BEAR':
    if rsi > 70: rsi_score = 5    # Overbought in bear = dangerous
    elif rsi > 50: rsi_score = 15
    elif rsi > 30: rsi_score = 25  # Oversold in bear = opportunity
    else: rsi_score = 30
```

### P3-12: Graduated quality penalty (U10)
**File:** `analyze_top200_stocks_enhanced.py` (blending section)  
**Fix:** Replace binary -5/-10 with: `penalty = max(0, (60 - data_quality) * 0.25)` (max penalty = 15 at quality 0).

### P3-13: Bear-market threshold widening (U12)
**File:** `analyze_top200_stocks_enhanced.py` lines 2487-2491  
**Fix:** In BEAR: `_regime_thr_delta = 8` (up from 5). STRONG_BUY → 78, BUY → 68.

---

## Phase 4: Future-Proof (G9-G14, U13-U16)
> Outcome tracking, better regime detection, walk-forward backtesting.

---

### P4-01: Multi-index regime detection (U13)
**File:** `market_regime_detector.py`  
**Fix:** Fetch Bank Nifty (^NSEBANK) and Midcap (NIFTY_MIDCAP_100.NS) in addition to Nifty 50. Use consensus: all three must agree for high-confidence regime.

### P4-02: VIX dynamic weighting (U14)
**File:** `market_regime_detector.py`  
**Fix:** When VIX > 25, increase volatility signal weight from 20% to 35%, decrease trend weight proportionally.

### P4-03: Outcome tracking in recommendation history (U15)
**File:** `recommendation_history.py`  
**Fix:** Add columns `price_7d`, `price_30d`, `price_90d`, `return_7d`, `return_30d`, `return_90d`. Add `update_outcomes()` method that fetches forward prices for past recommendations.

### P4-04: Consolidate data quality score (G7)
**File:** `analyze_top200_stocks_enhanced.py`  
**Fix:** Remove `_calculate_data_quality_score` (inner) and use `calculate_data_quality_score` (outer) everywhere.

### P4-05: Remove dead phase1_recommendation field (G12)
**File:** `analyze_top200_stocks_enhanced.py` line 2569  
**Fix:** Remove or compute a real Phase 1 recommendation from `phase1_adjusted_score`.

### P4-06: Handle UNKNOWN regime explicitly (G11)
**File:** `market_regime_detector.py`  
**Fix:** Add explicit `elif regime == 'UNKNOWN':` branch in `adjust_stock_score_by_regime` that applies no adjustment (return score unchanged).

### P4-07: Disable sentiment adjustment until real news API (G13)
**File:** `analyze_top200_stocks_enhanced.py` (blending section)  
**Fix:** Option A: Set sentiment cap to ±0 (disable). Option B: Add config flag `ENABLE_SENTIMENT_ADJUSTMENT = False`.

### P4-08: Wire adaptive scoring weights into hybrid engine (G8)
**File:** `hybrid_optimized_scoring.py` + `analyze_top200_stocks_enhanced.py`  
**Fix:** Call `adaptive_strategy.get_adaptive_scoring_weights(regime)` and pass weights to hybrid engine instead of using hardcoded regime weights.

### P4-09: Walk-forward backtesting framework (U16)
**File:** New or enhanced `run_backtest_v2.py`  
**Fix:** Implement rolling-window backtest: score at T, measure return at T+30, roll forward. No look-ahead bias for fundamentals (use T-1 quarter data).

---

## Implementation Notes

1. **Branch:** Continue on `fix/system-accuracy-gaps`
2. **Testing:** After each phase, run the Nifty 50 backtest to measure improvement
3. **Phase 1 is the priority** — it addresses the bear-market failure directly
4. **Phase 2 can be done incrementally** — each fix improves stability
5. **Phase 3 and 4 are polish** — do after Phases 1+2 show improved backtest numbers
6. **Commit after each phase** with detailed message

## Expected Backtest Improvement

| Metric | Current | After Phase 1 | After Phase 2 | After Phase 3 |
|--------|---------|---------------|---------------|---------------|
| Hybrid 90d Correlation | -0.21 | +0.10 to +0.20 | +0.15 to +0.25 | +0.20 to +0.35 |
| Q5-Q1 Spread | -3.26% | +2 to +5% | +3 to +6% | +5 to +8% |
| Top-20% Win Rate | 33% | 45-55% | 50-60% | 55-65% |
