---
name: stock-analysis-system
description: Project knowledge for the Stock_Analysis NSE equity pipeline — scoring engines (v1 baseline + v2 live with regime-conditional weights), config contracts, recommendation history, v2 promotion workflow (forward + historical modes), hard-stop (sleeve/regime-aware) and rotation rules, v3 Layer 3 paper-trading toggles, regression suites. Use when the user works on analyze_top200, hybrid scoring, v2 calibration or promotion, config.json thresholds, portfolio allocation, early breakout detector, universe filter, market regime, recommendation history, or Excel/HTML report contracts.
---

# Stock Analysis System — Project Knowledge

A multi-module NSE equity analysis pipeline that scores stocks (fundamentals + technicals + sentiment + ML), generates Excel reports + HTML dashboards, recommends portfolio actions, and tracks recommendation outcomes for self-calibration. Two scoring engines coexist: **v1 (baseline / audit)** and **v2 (live since 2026-05-13, IC-calibrated, regime-conditional)**. v2 is driven by `cfg.V2_SHADOW_MODE` — currently `False` in `config.json` (live). v3 Layer 3 toggles (`HARD_STOP_PURE_PNL`, `UNIDIRECTIONAL_HYSTERESIS`, `PAPER_TRADING_MODE`) are shipped but default `False` (paper-trading opt-in only).

## When to Apply This Skill

- Any change to scoring, recommendations, allocation, or report format
- Any change to `config.json` / `config.py` thresholds, weights, or feature flags (including v3 toggles)
- Any work on `analyze_top200_stocks_enhanced.py`, `hybrid_*_scoring*.py`, `early_breakout_detector.py`, `recommendation_history.py`
- Anything touching `data/recommendation_history.csv`, `data/calibrated_weights_v2*.json`, `data/historical_outcomes.csv`, `data/booking_history.json`, `data/v2_promotion_status.json`
- v2 calibration / promotion (forward or historical mode) / per-regime weights / regression questions
- Adding scripts under `scripts/` or tests under `tests/`

For the full module map, scoring math, schema details, and v2 lifecycle, read [reference.md](reference.md).

## Repo Topology (Top-Level)

```
analyze_top200_stocks_enhanced.py  # main analyzer (entrypoint, ~15K lines)
main.py                            # CLI shim → enhanced_main
config.py / config.json            # AnalysisConfig + persisted overrides
hybrid_optimized_scoring.py        # v1 engine (baseline / audit, V5.2)
hybrid_scoring_v2.py               # v2 engine (LIVE, regime-conditional)
adaptive_market_strategy.py        # regime-adaptive weights / exposure
market_regime_detector.py          # bull/bear/sideways classification
crisis_detector.py                 # cross-asset gate (default OFF per Contract Rule 7)
ml_predictor.py / pattern_recognition.py / sentiment_analyzer.py / volume_analyzer.py
early_breakout_detector.py         # pre-breakout + exhaustion exits
recommendation_history.py          # outcome tracking, action canonicalisation, cooldown
backtest_engine.py / run_backtest_v2.py
src/                               # technical_analyzer, enhanced_fundamental_analyzer,
                                   # nse_scraper, top10_extractor, universe_filter
scripts/                           # calibrate_v2_weights, v2_promotion_check, promote_v2,
                                   # build_historical_outcomes, backfill_v2_components,
                                   # historical_ic_diagnostic, walkforward_v2_validation,
                                   # monthly_rebalance_backtest, random_universe_backtest,
                                   # top_n_picks_backtest, six_month_return_check, cleanup_history_etfs
tests/                             # test_v2_regression (12 suites), test_regression_fixes,
                                   # test_scraper, static_validator, unit/, integration/, fixtures/
data/                              # history CSV/JSON, regime cache, calibrated weights (global + per-regime),
                                   # historical_outcomes.csv, snapshots/, raw/
reports/                           # generated Excel
Portfolio_Allocation_Dashboard.html
```

## Non-Negotiable Conventions

1. **Single global config**: always use `from config import get_config; cfg = get_config()`. Never instantiate `AnalysisConfig()` locally (rule MI-05). Use `update_config(**kwargs)` for thread-safe mutations — it validates and rolls back on failure.
2. **v1 must remain unchanged when editing v2.** v2 lives in `hybrid_scoring_v2.py` only and writes to `data/calibrated_weights_v2.json` (global) and `data/calibrated_weights_v2_{BULL,BEAR,SIDEWAYS}.json` (regime-conditional). Never let v2 paths/state leak into v1.
3. **Shadow vs live**: `cfg.V2_SHADOW_MODE` controls whether v2 drives actions. **Currently `False` in `config.json` (live since 2026-05-13)**. Promotion is *only* via `scripts/promote_v2.py` after `v2_promotion_check.py` reports `promotion_ready=True` — 30 consecutive eligible days in **forward** mode, or a single passing run in **historical** mode (`--mode historical`, no consecutive-day gate). `--force` reserved for emergencies.
4. **Threshold ordering invariant**: `STRONG_BUY > BUY > HOLD > SELL`; weights `FUNDAMENTAL+TECHNICAL+UNDERVALUATION` must sum to 1.0. Validation is enforced in `config._validate_config`.
5. **Universe filter is mandatory** for action surfaces. Use `src.universe_filter.is_tradeable / filter_universe` to drop ETFs/InvITs and illiquid names. Be permissive with missing data (returns `True` when `avg_volume`/`current_price` are None).
6. **Action enum is a contract**: must preserve the seven baseline actions (`HOLD, SELL, INCREASE, NEW POSITION, WATCHLIST, EXIT NOW - Heavy exhaustion, HIGH MOMENTUM NEW POSITION`) checked by Suite 1. `_normalize_action` additionally produces `STRONG BUY, BUY, WEAK SELL, REDUCE, SCALE_OUT_20, SWAP, EXIT` — adding new canonical labels is fine; renaming/removing the seven baseline labels is breaking.
7. **History schema is a contract**: `data/recommendation_history.csv` must contain at least `date, symbol, action, score, price, pe_ratio, roe, debt_to_equity, reason, rank, sector, price_7d/30d/90d, return_7d/30d/90d`. Current writer also appends `hybrid_fundamental_quality, hybrid_momentum_technical, hybrid_volume_strength, hybrid_multi_timeframe, hybrid_ml_signal, hybrid_risk_adjustment, score_v2, regime, hybrid_growth, hybrid_value, sleeve` — only append at the right edge.
8. **Excel sheets are a contract**: `Dashboard, Portfolio Allocation, Past Accuracy, Complete Data, Top Picks` must exist (Suite 1 checks subset).
9. **No emojis in code or commits.** No comments that just narrate code. Follow existing naming (`_evaluate_hard_stop`, `_should_rotate`, `is_tradeable`, etc.).
10. **Confirm before changing system-wide thresholds, scoring weights, exit logic, or report format** (per `.cursor/rules/core-interaction.mdc`). These are breaking changes.

## Common Workflows

### Run an analysis

```bash
python main.py --interactive                                  # guided
python main.py --risk-profile aggressive -n 10                # quick smoke
python main.py --risk-profile aggressive --focus-growth       # full
python main.py --portfolio-amount 500000 --risk-profile aggressive
python main.py -s RELIANCE --risk-profile aggressive          # single stock
```

### v2 calibration → promotion check → promotion

```bash
# Calibrate (global + optional per-regime weights)
python3 scripts/calibrate_v2_weights.py                                  # default: recommendation_history (forward)
python3 scripts/calibrate_v2_weights.py --source historical_outcomes     # uses historical_outcomes.csv (built by build_historical_outcomes.py)
python3 scripts/calibrate_v2_weights.py --per-regime                     # also writes data/calibrated_weights_v2_{BULL,BEAR,SIDEWAYS}.json

# Build historical outcomes when forward window is too short for 30d returns
python3 scripts/build_historical_outcomes.py                             # writes data/historical_outcomes.csv

# Promotion check (forward = strict + 30-day gate; historical = single-shot, no consecutive gate)
python3 scripts/v2_promotion_check.py                                     # forward mode (default), window 60d
python3 scripts/v2_promotion_check.py --mode historical                   # bypass consecutive-day gate
python3 scripts/v2_promotion_check.py --evaluate                          # read-only diagnostics (no state mutation)

# Flip live (already done 2026-05-13; safe re-runs are idempotent)
python3 scripts/promote_v2.py --dry-run
python3 scripts/promote_v2.py
python3 scripts/promote_v2.py --force                                     # emergency override
```

Rollback: restore `config.json.pre_v2_promotion_<ts>.bak` written by `promote_v2.py` (the 2026-05-13 backup at `config.json.pre_v2_promotion_20260513_005851.bak` is the pre-v2 state).

### Regression suite (run after any scoring/exit/universe/history change)

```bash
python3 tests/test_v2_regression.py            # 11 suites: contract, universe, exhaustion, hard-stop,
                                               # v2 isolation, rotation, cache compat, DQ-NATALUM,
                                               # P0 stop-tier, v3 Layer 3, v3 calibration, historical calibration
python3 tests/test_regression_fixes.py
```

### Update a config knob safely

Edit `config.json` (persisted overrides, auto-loaded at import). Never edit `config.py` defaults unless adding new fields. After editing, run the regression suite — `_validate_config` will reject bad values at load time.

## Decision Boundaries (escalate before changing)

| Area | File(s) | Why it's load-bearing |
|---|---|---|
| Recommendation thresholds | `config.json` (`STRONG_BUY/BUY/HOLD/SELL_THRESHOLD`) | Drives every action |
| Scoring weights | `config.py` (`FUNDAMENTAL/TECHNICAL/UNDERVALUATION_WEIGHT`) + hybrid engines | Validated to sum to 1.0 |
| Hard-stop tiers | `config.HARD_STOP_PCT/SOFT_STOP_PCT/HARD_STOP_OVERRIDE_SCORE` + `_evaluate_hard_stop` | Determines forced sells; now sleeve- and regime-aware |
| v3 Layer 3 toggles | `HARD_STOP_PURE_PNL`, `UNIDIRECTIONAL_HYSTERESIS`, `PAPER_TRADING_MODE` | Default `False`; flip only via paper-trading review |
| Trailing / scale-out | `TRAILING_STOP_PCT`, `SCALE_OUT_*` | Contract Rules 5 & 6b — profit-booking + peak trail |
| Sector caps | `config.SECTOR_CAP/CATEGORY_SECTOR_CAP` | Portfolio construction |
| Action enum / sheet names / history columns | analyzer + exporters | Contract — Suite 1 enforces |
| v2 path/state | `hybrid_scoring_v2.py`, `data/calibrated_weights_v2*.json` | Suite 5 enforces isolation |
| Crisis detector | `ENABLE_CRISIS_DETECTOR` (default `False` per Contract Rule 7) | Cross-asset overlay kept for ablation only |

## Anti-Patterns in This Codebase (Don't Do These)

1. **Don't bypass `src.universe_filter`** when assigning actions or writing to history — pollutes outcomes with un-tradeable instruments and breaks Suite 2.
2. **Don't write v1 paths from v2 code** (`data/calibrated_weights.json` is v1-only; v2 uses `_v2.json` + per-regime variants). Suite 5 fails if these get crossed.
3. **Don't instantiate `AnalysisConfig()` locally.** Always `get_config()` (rule MI-05). Local instances drift from `config.json`.
4. **Don't add emoji or emoji-bearing actions to the action enum.** `_strip_annotation` / `_normalize_action` strip them; new emoji actions become invisible to downstream code.
5. **Don't change `MAX_SINGLE_STOCK_WEIGHT` / `MAX_ALLOCATION_PCT` and expect behaviour change** — both are DEPRECATED. The allocator uses per-cap-tier limits.
6. **Don't tighten thresholds without re-running the full regression suite** — Suites 1, 4, 9, 10 lock concrete values.
7. **Don't promote v2 with `--force` casually.** It bypasses the eligibility window. Reserve for emergencies and document the reason.
8. **Don't add new top-level entry-point scripts.** Use `scripts/` (one-off) or `tools/` (interactive). `main.py` is the single CLI shim.
9. **Don't edit `data/recommendation_history.csv` schema in-place.** Add columns at the right edge; Suite 1 checks `required_cols.issubset(baseline_cols)`. Removing or renaming is breaking.
10. **Don't trust ML tags in user-facing output.** `cfg.ML_TAG_IN_RECOMMENDATION` defaults `False` until model accuracy > 60%.
11. **Don't flip `PAPER_TRADING_MODE` or v3 Layer 3 toggles in `config.json` without an explicit paper-trading window.** They disable the score-based override on hard-stops and switch hysteresis to unidirectional.
12. **Don't enable `ENABLE_CRISIS_DETECTOR`** — disabled by Contract Rule 7. Kept on disk for ablation only.

## Worked Examples

**Example 1 — User: "Lower BUY_THRESHOLD to 55."**

System-wide threshold change → confirm before acting per `.cursor/rules/core-interaction.mdc`. Steps:
1. Verify ordering invariant still holds: `STRONG_BUY(70) > BUY(55) > HOLD(50) > SELL(40)` ✓.
2. Edit `config.json` (not `config.py`).
3. Run `python3 tests/test_v2_regression.py` — Suites 1 and 11 must pass.
4. Note that hysteresis (`HYSTERESIS_BUFFER=3.0`) means edge cases at 52–58 may now flip; in `UNIDIRECTIONAL_HYSTERESIS=True` mode downgrades are immediate.

**Example 2 — User: "Add a new scoring component called `news_velocity`."**

1. Extend history schema: append `hybrid_news_velocity` and (optionally) `news_velocity_score` columns in `recommendation_history.py` (don't reorder existing).
2. Add component to v1 (`hybrid_optimized_scoring.py`) AND v2 `component_map` (in `hybrid_scoring_v2.calibrate_weights_from_outcomes`). Both engines must compute it. Mirror the `('news_velocity', 'hybrid_news_velocity', 'news_velocity_score')` triple in `scripts/calibrate_v2_weights.py`.
3. Backfill: either log forward via live runs (≥50 rows) or run `scripts/backfill_v2_components.py` against historical reports. `MIN_SAMPLES=50` for global calibration; `MIN_SAMPLES_PER_REGIME=30` for per-regime.
4. Run `python3 scripts/calibrate_v2_weights.py` — confirm new component appears in `ics_blended`. Optionally `--per-regime`.
5. Update `tests/test_v2_regression.Suite5` and Suite 11 if the component changes the v2-vs-v1 isolation surface or calibration math.

**Example 3 — User: "Why did RELIANCE flip from BUY to HOLD yesterday?"**

1. Read `data/recommendation_history.csv`: tail rows for symbol; check `score`, `score_v2`, `action`, `reason`, `regime`, `sleeve` columns.
2. Check hysteresis: was previous score within `HYSTERESIS_BUFFER=3.0` pp of `BUY_THRESHOLD`? Check `UNIDIRECTIONAL_HYSTERESIS` — if `True`, downgrades fall through immediately.
3. Check score smoothing: `SCORE_SMOOTHING_WEIGHT_DOWN=0.75` means downward moves are damped — flips usually need persistent score drop. Bear regime uses `SCORE_SMOOTHING_WEIGHT_BEAR=0.50`.
4. Check regime change: `data/last_known_regime.json` — bear/sideways shifts narrow exposure (`BEAR_EXPOSURE=0.50`). Per-regime v2 weights at `data/calibrated_weights_v2_{regime}.json` may also have switched.
5. Check hard-stop: `_evaluate_hard_stop(profit_pct, score, rsi, pattern_signal, cfg, sleeve, market_regime)` — bear-regime tightening or `HARD_STOP_PURE_PNL` may have forced SELL/REDUCE; CORE sleeve disables price stops entirely.
6. Check trailing stop: `TRAILING_STOP_PCT=0.15` (bear `0.10`) using peak price from `data/booking_history.json`.

## Additional Resources

For module-by-module deep dives, scoring math, recommendation lifecycle, data file schemas, and the v2 promotion state machine, see [reference.md](reference.md).
