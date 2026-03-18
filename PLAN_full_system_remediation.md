# Full System Remediation Plan

## Objective
Fix all identified gaps, risks, and architectural issues to bring the stock analysis system to functional-grade, reliable, and auditable status. Organized into 6 phases by priority and dependency order.

---

## Phase 1: BLOCKING FIXES (Critical — Must Complete First)

These three issues directly cause incorrect scoring, misleading reports, or unmitigated concentration risk.

### 1.1 — Fix ML Weight Leakage in `adaptive_market_strategy.py`

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | CRITICAL |
| **Root Cause**  | `adaptive_market_strategy.py` assigns `ml_signal: 0.05–0.10` in all four regime dicts. `analyze_top200_stocks_enhanced.py` line 2350 always passes these adaptive weights to `calculate_hybrid_score`, which overrides `_REGIME_WEIGHTS_NO_ML` (ml=0.00) from `hybrid_optimized_scoring.py`. The explicitly disabled ML model (39% accuracy) leaks back in. |
| **File**        | `adaptive_market_strategy.py` |
| **Lines**       | 62, 70, 78, 86 |
| **Impact**      | Up to 5-point score swing per stock; 4–6 potential wrong recommendations |

**Change:** Set `ml_signal` to `0.00` in all four regime dictionaries and redistribute the removed weight to `momentum_technical` (consistent with `_REGIME_WEIGHTS_NO_ML` strategy in `hybrid_optimized_scoring.py`).

```
BULL_MODERATE:  ml_signal 0.05 → 0.00, momentum_technical 0.30 → 0.35
CALM:           ml_signal 0.10 → 0.00, momentum_technical 0.20 → 0.30
SIDEWAYS:       ml_signal 0.05 → 0.00, momentum_technical 0.15 → 0.20
BEAR_MODERATE:  ml_signal 0.05 → 0.00, momentum_technical 0.10 → 0.15
```

**Safety:** Weight normalization at `hybrid_optimized_scoring.py` lines 399–401 handles sub-1.0 sums. No downstream code asserts `ml_signal > 0` or divides by it. Confirmed safe.

**Edge case guard:** Also check `calibrated_weights.json` if it exists — it can re-inject ML weight via the calibrated weights path (line 395). Add a post-load zero-out for `ml_signal` if ML is disabled.

**Verification:**
- Run analysis; check `weights['ml_signal']` is 0 in log output
- Compare total score distribution pre/post: average shift should be < 3 points
- No stock should change recommendation category

---

### 1.2 — Remove Universal Portfolio Fit +5 Bonus

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | HIGH |
| **Root Cause**  | `analyze_top200_stocks_enhanced.py` line 1202 returns `portfolio_fit: 'excellent'` when no portfolio context is available (which is always the case during initial scoring). Line 2525 then adds +5 to every stock's `final_blended_score`. All 206 stocks get the same +5 — zero differentiation, systematic inflation. |
| **Files**       | `analyze_top200_stocks_enhanced.py` |
| **Lines**       | 1196–1207 (default return), 2525–2528 (bonus application) |
| **Impact**      | All scores inflated by 5 points. A stock scoring 45 (below average) displays as 50 (average). Misleads threshold-based decisions. |

**Change:** Remove the unconditional +5/−5 bonus. Replace with a no-op comment explaining the decision, so future developers don't re-add it.

```
# Lines 2525-2528: DELETE the portfolio_fit bonus block
# Portfolio fit bonus removed — was universally 'excellent' for all stocks,
# providing zero differentiation and inflating all scores by +5.
```

Also fix the root cause at lines 1196–1207: change the default `portfolio_fit` from `'excellent'` to `'neutral'`.

**Dependency:** Removing the +5 shifts all scores down by 5 points. Verify recommendation thresholds (`STRONG_BUY_THRESHOLD: 70`, `BUY_THRESHOLD: 60`, `HOLD_THRESHOLD: 50`) still produce reasonable category distributions. If not, lower each by 5 points in `config.py`/`config.json`.

**Verification:**
- Confirm no stock has `portfolio_fit = 'excellent'` by default
- Confirm average score drops by ~5 points
- Confirm recommendation distribution is still balanced (not all stocks downgraded)

---

### 1.3 — Enforce Sector Cap on Existing Holdings

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | CRITICAL |
| **Root Cause**  | The sector cap (`SECTOR_CAP: 5`) only constrains NEW BUY recommendations. Existing holdings bypass it with `keep_stock: True` / `action_type: 'HOLD CURRENT'`. Current report: 21 Financial Services stocks = 77.5% of capital. |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Location**    | After the holdings-to-allocation loop (after line ~5724), before new BUY allocation begins |
| **Impact**      | 77.5% single-sector concentration. A 20% sector drop = 15.5% portfolio loss. |

**Change:** Add a post-holdings sector enforcement pass:

1. After all holdings are added to `allocation_data`, count stocks per sector.
2. For sectors exceeding `_config.SECTOR_CAP`:
   - Sort the sector's holdings by `risk_adjusted_score` ascending (weakest first).
   - Mark the lowest-scoring excess stocks as `REDUCE (SECTOR OVERWEIGHT)` with `priority: 'MEDIUM'`.
   - Log each marked stock with a warning.
3. The Action Plan generator must handle the new `REDUCE (SECTOR OVERWEIGHT)` action type — generate instructions to "reduce position by 25–50% to bring sector within cap".

**New config parameter:** Add `SECTOR_CAP_ENFORCE_HOLDINGS: bool = True` to `config.py` and `config.json` so this behavior can be toggled.

**Verification:**
- With 21 Financial Services stocks and cap=5, verify 16 are marked REDUCE
- Verify remaining 5 are the highest-scoring Financial Services stocks
- Verify Action Plan includes reduction instructions for each REDUCE stock

---

## Phase 2: DATA QUALITY & INTEGRITY

### 2.1 — Fix NaN Propagation in `enhanced_technical_analyzer.py`

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Files**       | `enhanced_technical_analyzer.py` |
| **Lines**       | 115 (`avg_daily_range`), 163–168 (SMA values), 377 (`price_volume_correlation`) |

**Fix A — `avg_daily_range` (line 115):**
The expression `... .mean() or 0` does NOT catch NaN because `NaN` is truthy in Python.
```
# BEFORE:
'avg_daily_range': ((df['High'] - df['Low']) / df['Close'].replace(0, np.nan) * 100).tail(20).mean() or 0,

# AFTER:
'avg_daily_range': float(((df['High'] - df['Low']) / df['Close'].replace(0, np.nan) * 100).tail(20).mean()) if not np.isnan(((df['High'] - df['Low']) / df['Close'].replace(0, np.nan) * 100).tail(20).mean()) else 0.0,
```
Better approach — extract to a helper:
```python
_adr = ((df['High'] - df['Low']) / df['Close'].replace(0, np.nan) * 100).tail(20).mean()
'avg_daily_range': 0.0 if (pd.isna(_adr)) else float(_adr),
```

**Fix B — SMA values (lines 163–168):**
Add `.fillna(0)` or a NaN guard to each `.iloc[-1]` extraction. When DataFrame has fewer than 20 rows, `sma_20` will be NaN.
```python
_sma5 = df['Close'].rolling(5).mean()
_sma10 = df['Close'].rolling(10).mean()
_sma20 = df['Close'].rolling(20).mean()
indicators.update({
    'sma_5': float(_sma5.iloc[-1]) if not pd.isna(_sma5.iloc[-1]) else float(df['Close'].iloc[-1]),
    'sma_10': float(_sma10.iloc[-1]) if not pd.isna(_sma10.iloc[-1]) else float(df['Close'].iloc[-1]),
    'sma_20': float(_sma20.iloc[-1]) if not pd.isna(_sma20.iloc[-1]) else float(df['Close'].iloc[-1]),
    # EMA: ewm doesn't produce NaN for the last row
    'ema_5': df['Close'].ewm(span=5).mean().iloc[-1],
    'ema_10': df['Close'].ewm(span=10).mean().iloc[-1],
    'ema_20': df['Close'].ewm(span=20).mean().iloc[-1],
})
```

**Fix C — `price_volume_correlation` (line 377):**
`.corr()` returns NaN when standard deviation is zero (constant price for 10 days).
```python
correlation = recent_price_change.corr(recent_volume_change)
volume_analysis['price_volume_correlation'] = 0.0 if pd.isna(correlation) else float(correlation)
```

**Verification:** Run analysis on a stock with < 20 days of data; confirm no NaN in output dict.

---

### 2.2 — Add Cache File Locking

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Root Cause**  | `load_from_cache` (line 416) and `save_to_cache` (line 471) use plain `open()` with no file locking. Concurrent runs can corrupt cache JSON. |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Lines**       | 406–478 |

**Change:** Use `filelock` library for cache I/O. Install via `pip install filelock`.

```python
from filelock import FileLock, Timeout

def load_from_cache(self, symbol, analysis_type="comprehensive"):
    if not self.cache_enabled:
        return None
    cache_path = self.get_cache_path(symbol, analysis_type)
    lock_path = cache_path + ".lock"
    if self.is_cache_valid(cache_path):
        try:
            with FileLock(lock_path, timeout=5):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            self.performance_metrics['cache_hits'] += 1
            return data
        except Timeout:
            logging.warning(f"Cache lock timeout for {symbol}")
        except Exception as e:
            logging.warning(f"Failed to load cache for {symbol}: {e}")
    return None

def save_to_cache(self, symbol, data, analysis_type="comprehensive"):
    if not self.cache_enabled:
        return
    cache_path = self.get_cache_path(symbol, analysis_type)
    lock_path = cache_path + ".lock"
    try:
        serializable_data = {k: self._make_json_safe(v) for k, v in data.items()}
        with FileLock(lock_path, timeout=10):
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)
    except Timeout:
        logging.warning(f"Cache write lock timeout for {symbol}")
    except Exception as e:
        logging.warning(f"Failed to cache data for {symbol}: {e}")
```

**Verification:** Run two analysis instances simultaneously; confirm no JSON parse errors.

---

### 2.3 — Add Minimum Volume Floor (Illiquid Stock Filter)

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | HIGH |
| **Root Cause**  | No minimum absolute volume check. A stock trading 100 shares/day passes all analysis identically to one trading 5M shares/day. BUY recommendations for illiquid stocks are impossible to execute. |
| **File**        | `analyze_top200_stocks_enhanced.py` and `config.py` |

**New config parameters:**
```python
MIN_AVG_DAILY_VOLUME: int = 50000    # Minimum 50K shares/day average
ILLIQUID_SCORE_PENALTY: float = 15.0  # Score penalty for illiquid stocks
```

**Change in `analyze_top200_stocks_enhanced.py`:** After technical analysis, check average daily volume. If below threshold:
- Add `quality_warning: 'low_liquidity'`
- Apply score penalty
- Mark recommendation as `'BUY (LOW LIQUIDITY WARNING)'` if was BUY
- Log the flag

**Verification:** Manually check stocks with lowest volume; confirm they receive the warning.

---

### 2.4 — Fix Partial API Failure (Empty `info` + Valid History)

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Root Cause**  | When `ticker.info` returns empty dict but `ticker.history` returns valid data, `marketCap` is 0, so the large-cap bypass (`mcap > 2e11`) always fails. Stock is fully skipped despite having perfect price data. |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Lines**       | 169–216 (`StockDataBundle._validate`) |

**Change:** Add a secondary bypass: if `info` is empty/stub but `hist_5y` has >= 200 rows (roughly 1 year of data), allow the stock through with a quality warning.

```python
if not ok:
    mcap = self.info.get('marketCap', 0) if self.info else 0
    has_some_price = len(self.hist_5y) >= 30
    has_solid_price = len(self.hist_5y) >= 200
    if mcap and mcap > 2e11 and has_some_price:
        logging.warning(f"Large-cap {self.symbol} — allowing with partial data")
        return True
    if has_solid_price and (not self.info or not self.info.get('regularMarketPrice')):
        self.quality_warnings.append("empty_info_bypass")
        logging.warning(f"{self.symbol}: empty info but {len(self.hist_5y)} price rows — allowing with price-only analysis")
        return True
return ok
```

**Verification:** Mock `ticker.info` returning `{}` for a stock with valid history; confirm it passes validation.

---

## Phase 3: AUDITABILITY & REPRODUCIBILITY

### 3.1 — Add `_Metadata` Sheet to Excel Report

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | HIGH |
| **Root Cause**  | No config, scoring version, or report timestamp inside the Excel workbook. Cannot reproduce or audit a report. |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Location**    | Inside the `with pd.ExcelWriter(...)` block, after all sheets are written, before `workbook.close()` |

**Change:** Add a `_Metadata` sheet with the following rows:

| Key | Value |
|-----|-------|
| Report Generated | `datetime.now()` formatted |
| Scoring Engine Version | `self.hybrid_scoring_engine.version` |
| Market Regime | `self.current_market_regime` |
| Regime Confidence | From regime detection |
| Stocks Analyzed | `len(self.results)` |
| Stocks Failed | `len(self.failed_stocks)` |
| Stocks Skipped | count of `status == 'data_invalid'` |
| Cache Hit Rate | `cache_hits / total_stocks` |
| Config Source | `config.json` or `config.py defaults` |
| All config.* keys | One row per config parameter |

**Verification:** Open generated Excel; confirm `_Metadata` sheet exists with all fields populated.

---

### 3.2 — Add Deterministic Sort

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Root Cause**  | `sort_values` uses quicksort (unstable). Tied scores produce non-deterministic row order. |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Lines**       | 8320 (main sort), 8934–8936 (allocation sort) |

**Change — Line 8320:**
```python
df = df.sort_values(['risk_adjusted_score', 'symbol'], ascending=[False, True], kind='mergesort')
```

**Change — Lines 8934–8936:**
```python
alloc_df_simple = alloc_df_simple.sort_values(
    ['_sort_ord', 'overall_score', 'symbol'],
    ascending=[True, False, True],
    kind='mergesort'
).drop(columns='_sort_ord').reset_index(drop=True)
```

**Verification:** Run analysis twice with cached data; confirm identical row order in Excel.

---

### 3.3 — Snapshot Config + Stock List + Holdings Per Run

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | HIGH |
| **Root Cause**  | Config is not logged. Stock list template can change. Holdings file is overwritten. After 7 days, cache is purged. No way to reproduce a report. |
| **File**        | `analyze_top200_stocks_enhanced.py` |

**Changes:**

**A) Config dump at analysis start (near line 11680):**
```python
import shutil
_run_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
_snapshot_dir = os.path.join('data', 'snapshots', _run_ts)
os.makedirs(_snapshot_dir, exist_ok=True)
save_config_to_file(os.path.join(_snapshot_dir, 'config_snapshot.json'))
```

**B) Stock list backup:**
```python
if os.path.exists('stock_list_template.csv'):
    shutil.copy2('stock_list_template.csv', os.path.join(_snapshot_dir, 'stock_list.csv'))
```

**C) Holdings backup:**
```python
for hf in glob.glob('Holding/holdings*.csv') + glob.glob('Holding/Stocks_Holdings_Statement_*.xlsx'):
    shutil.copy2(hf, _snapshot_dir)
```

**New config parameter:** `CACHE_MAX_AGE_DAYS: int = 7` (move from hardcoded in `cleanup_cache` call at line 11714).

**Verification:** Run analysis; confirm `data/snapshots/{timestamp}/` contains config, stock list, and holdings files.

---

### 3.4 — Add Report Timestamp to Dashboard Sheet

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | LOW |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Location**    | Dashboard sheet creation section (around line 9352) |

**Change:** After writing the Dashboard title, add a "Generated at" cell:
```python
worksheet.write(row, col, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", subtitle_format)
```

---

## Phase 4: TRANSPARENCY & REPORTING

### 4.1 — Surface Flip-Flop Details in Report

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Root Cause**  | `generate_stability_report()` (line 7679) calls `get_flip_flop_stocks()` but only extracts the COUNT. Actual flip-flop details (which stocks, which transitions, days between) are discarded. |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Lines**       | 7678–7689 |

**Change:** Extract and print flip-flop details:
```python
stability_report = self.recommendation_history.generate_stability_report()
print(f"   📊 Recommendation History:")
print(f"      Total recommendations: {stability_report['total_recommendations']}")
# ... existing prints ...

# NEW: Surface flip-flop details
ff_7d = self.recommendation_history.get_flip_flop_stocks(days=7)
ff_14d = self.recommendation_history.get_flip_flop_stocks(days=14)
if ff_7d:
    print(f"\n   ⚠️  FLIP-FLOP WARNINGS (7 days):")
    for ff in ff_7d:
        print(f"      {ff['symbol']}: {ff['first_action']} → {ff['second_action']} ({ff['days_between']}d apart)")
if ff_14d and len(ff_14d) > len(ff_7d):
    _new_14d = [f for f in ff_14d if f not in ff_7d]
    if _new_14d:
        print(f"   ⚠️  ADDITIONAL FLIP-FLOPS (14 days):")
        for ff in _new_14d:
            print(f"      {ff['symbol']}: {ff['first_action']} → {ff['second_action']} ({ff['days_between']}d apart)")
```

Also add flip-flop warnings to the Portfolio Allocation sheet as a note column or conditional format for affected stocks.

---

### 4.2 — Add Score Decomposition to Portfolio Allocation

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Root Cause**  | Portfolio Allocation shows only the final score. Sub-score breakdown exists in Complete Data but is not linked. An investor cannot trace why a stock received its score. |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Location**    | Portfolio Allocation sheet columns definition |

**Change:** Add 6 sub-score columns (VOL, MOM, FUND, MULTI, ML, RISK) plus regime and weight columns to the Portfolio Allocation sheet. These already exist in the DataFrame as `hybrid_*` columns — just include them in the `essential_cols` list for the allocation sheet.

---

### 4.3 — Add Regime and Weight Context to Report

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |

**Change:** In the `_Metadata` sheet (Phase 3.1), add the current adaptive weights used:
```python
for component, weight in adaptive_weights.items():
    metadata[f'weight.{component}'] = weight
```

This makes the weight allocation transparent and auditable.

---

## Phase 5: SENTIMENT ANALYZER REFACTOR

### 5.1 — Eliminate Redundant API Calls

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Root Cause**  | `sentiment_analyzer.py` creates a new `yf.Ticker` (line 78) and calls `ticker.recommendations` (line 203) and `ticker.earnings` (line 279). These are 2–3 redundant API calls per stock that `StockDataBundle` has already fetched. |
| **File**        | `sentiment_analyzer.py` |

**Change:** Modify `analyze_sentiment()` to accept an optional `StockDataBundle` parameter:

```python
def analyze_sentiment(self, symbol: str, stock_data: Dict, bundle=None) -> Dict:
    # Reuse bundle data if available
    if bundle and hasattr(bundle, 'hist_3mo') and not bundle.hist_3mo.empty:
        hist = bundle.hist_3mo
    elif isinstance(stock_data.get('_hist_3mo'), pd.DataFrame):
        hist = stock_data['_hist_3mo']
    else:
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period="3mo")
    
    # For analyst_sentiment: use bundle.info if available
    # For earnings_sentiment: use bundle.info if available
    # Only create yf.Ticker as fallback
```

**Caller change in `analyze_top200_stocks_enhanced.py`:** Pass the `StockDataBundle` when calling `analyze_sentiment`:
```python
sentiment_data = self.sentiment_analyzer.analyze_sentiment(symbol, stock_data, bundle=bundle)
```

**Impact:** Eliminates 2–3 API calls per stock × 150 stocks = 300–450 fewer API calls per run. Reduces runtime and API rate-limit risk.

**Verification:** Run analysis; confirm no new `yf.Ticker` instantiation in sentiment analyzer logs when bundle is provided.

---

## Phase 6: ROBUSTNESS & EDGE CASES

### 6.1 — Add Corporate Action Detection

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Root Cause**  | No detection of stock splits, bonus shares, or dividends. System relies on yfinance's default auto-adjustment, which may lag. |
| **File**        | `enhanced_technical_analyzer.py` |

**Change:** After computing price analysis, add a corporate action check:
```python
_daily_returns = df['Close'].pct_change()
_max_daily_drop = _daily_returns.tail(5).min()
_max_daily_jump = _daily_returns.tail(5).max()
if _max_daily_drop < -0.40 or _max_daily_jump > 0.60:
    indicators['corporate_action_warning'] = True
    indicators['corporate_action_detail'] = f"Extreme move: {_max_daily_drop*100:.1f}% to {_max_daily_jump*100:.1f}%"
    logging.warning(f"Possible corporate action for {df.name if hasattr(df, 'name') else 'unknown'}: extreme daily move detected")
else:
    indicators['corporate_action_warning'] = False
```

In `analyze_top200_stocks_enhanced.py`, check this flag before applying recommendation:
- If `corporate_action_warning == True`, set recommendation to `'HOLD (UNDER REVIEW — POSSIBLE CORPORATE ACTION)'`

---

### 6.2 — Add Extreme Volatility Safety Cap

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | LOW |
| **Root Cause**  | Risk penalty caps at 30% regardless of volatility (`min(vol/100, 0.30)`). A stock with 200% volatility gets the same penalty as one with 30%. |
| **File**        | `analyze_top200_stocks_enhanced.py` |

**New config parameter:** `MAX_SAFE_VOLATILITY: float = 80.0`

**Change:** After risk classification, if volatility > `MAX_SAFE_VOLATILITY`:
```python
if volatility > _config.MAX_SAFE_VOLATILITY:
    risk_category = "EXTREME"
    stock_data['extreme_volatility_flag'] = True
    logging.warning(f"{symbol}: extreme volatility {volatility:.1f}% > {_config.MAX_SAFE_VOLATILITY}%")
```

In recommendation logic, downgrade any BUY to HOLD for EXTREME risk stocks.

---

### 6.3 — Handle "NOT ANALYZED" Holdings Staleness

| Attribute       | Detail |
|-----------------|--------|
| **Severity**    | MEDIUM |
| **Root Cause**  | Holdings that fail analysis get `HOLD (NOT ANALYZED)` with score=0 permanently. They never receive SELL recommendations even if they should be sold. |
| **File**        | `analyze_top200_stocks_enhanced.py` |
| **Lines**       | 5656–5724 |

**Change:** Instead of permanent HOLD, check how long the stock has been NOT ANALYZED:
1. Look up the recommendation history for the stock
2. If the last successful analysis was > 7 days ago, mark as `REVIEW REQUIRED (STALE)` instead of HOLD
3. Add `priority: 'HIGH'` so it appears prominently in the Action Plan

---

## Config Changes Summary

New parameters to add to `config.py` and `config.json`:

| Parameter | Type | Default | Used In |
|-----------|------|---------|---------|
| `SECTOR_CAP_ENFORCE_HOLDINGS` | `bool` | `True` | Phase 1.3 |
| `MIN_AVG_DAILY_VOLUME` | `int` | `50000` | Phase 2.3 |
| `ILLIQUID_SCORE_PENALTY` | `float` | `15.0` | Phase 2.3 |
| `CACHE_MAX_AGE_DAYS` | `int` | `7` | Phase 3.3 |
| `MAX_SAFE_VOLATILITY` | `float` | `80.0` | Phase 6.2 |

---

## Dependency Graph

```
Phase 1.1 (ML weight)     → independent, do first
Phase 1.2 (portfolio fit)  → may need threshold adjustment after
Phase 1.3 (sector cap)     → needs Action Plan handler update

Phase 2.1 (NaN)     → independent
Phase 2.2 (cache)   → needs filelock dependency
Phase 2.3 (volume)  → needs config.py update
Phase 2.4 (API)     → independent

Phase 3.1 (metadata)  → depends on Phase 1 completion (correct config to dump)
Phase 3.2 (sort)       → independent
Phase 3.3 (snapshots)  → depends on config.py update from Phase 2
Phase 3.4 (timestamp)  → independent

Phase 4.1 (flip-flop)   → independent
Phase 4.2 (decomp)      → independent
Phase 4.3 (weights)      → depends on Phase 3.1

Phase 5.1 (sentiment)   → independent but touches caller in main file

Phase 6.1 (corporate)   → independent
Phase 6.2 (volatility)  → needs config.py update
Phase 6.3 (stale)       → independent
```

---

## Estimated Effort

| Phase | Items | Effort | Cumulative |
|-------|-------|--------|------------|
| Phase 1 | 3 blocking fixes | ~3 hours | 3 hours |
| Phase 2 | 4 data quality fixes | ~3 hours | 6 hours |
| Phase 3 | 4 auditability additions | ~2 hours | 8 hours |
| Phase 4 | 3 transparency improvements | ~2 hours | 10 hours |
| Phase 5 | 1 refactor | ~1.5 hours | 11.5 hours |
| Phase 6 | 3 edge case fixes | ~2 hours | 13.5 hours |

---

## Verification Strategy

After ALL phases complete, run:

1. **Full analysis** — `python3 analyze_top200_stocks_enhanced.py` — must complete without errors
2. **Score comparison** — compare pre-fix vs post-fix scores; document the delta distribution
3. **Sector check** — verify top sector is ≤ 5 stocks in Portfolio Allocation
4. **NaN scan** — grep report for NaN/None in score columns; must be zero
5. **Metadata check** — open Excel, verify `_Metadata` sheet is present and complete
6. **Determinism test** — run twice with cached data; compare Excel files (excluding timestamps)
7. **Snapshot check** — verify `data/snapshots/{timestamp}/` contains config, stock list, holdings

---

## Post-Implementation: Test Plan

### Unit Tests
- `test_ml_weight_zero`: All adaptive regime weights have `ml_signal == 0.0`
- `test_weight_normalization`: Weights sum to 1.0 after zeroing ML
- `test_portfolio_fit_neutral`: Default portfolio_fit is `'neutral'`, not `'excellent'`
- `test_no_universal_bonus`: Score does not include +5 for all stocks
- `test_sector_cap_enforcement`: Holdings sector cap is enforced, excess marked REDUCE
- `test_nan_guarded_sma`: SMA returns current price (not NaN) for short DataFrames
- `test_nan_guarded_correlation`: Correlation returns 0.0 (not NaN) for constant prices
- `test_cache_locking`: Concurrent cache reads/writes produce no JSON corruption
- `test_illiquid_flag`: Stock with avg volume < 50K gets `low_liquidity` warning
- `test_partial_api`: Stock with empty info but 200+ history rows passes validation
- `test_corporate_action_detection`: >40% single-day drop triggers warning flag
- `test_extreme_volatility_cap`: >80% volatility stock gets EXTREME risk and BUY→HOLD downgrade

### Integration Tests
- `test_end_to_end_10_stocks`: Full pipeline, 10 stocks, report generates, all sheets present
- `test_sector_reduce_in_action_plan`: REDUCE stocks appear in Action Plan with correct instructions
- `test_sentiment_uses_bundle`: No new yf.Ticker created in sentiment analyzer when bundle provided
- `test_metadata_sheet_complete`: _Metadata sheet has config, version, regime, timestamps
- `test_snapshot_created`: Run creates data/snapshots/ with required files

### Regression Tests
- `test_score_range_0_100`: All scores in [0, 100]
- `test_no_nan_in_portfolio`: No NaN in Portfolio Allocation sheet
- `test_all_expected_columns`: All column names present in each sheet
- `test_stop_loss_100_pct`: Every allocated stock has stop_loss_price > 0

### Stress Tests
- `test_200_stocks_no_oom`: Full 200-stock analysis completes < 45 min, no OOM
- `test_concurrent_cache`: Two simultaneous runs, no cache corruption
- `test_extreme_data_injection`: Stocks with 500% vol, PE=5000, volume=0 — all scored, no crash

### Determinism Test
- `test_identical_output`: Two runs with identical cache → byte-identical Excel (excluding timestamps)
