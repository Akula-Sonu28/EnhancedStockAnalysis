---
name: turbo-mtf-weekly-trader
description: >-
  Weekly NSE trading playbook for Turbo MTF (15-30 day holds, ROI-first,
  active rotation). Use when planning weekly rebalance, choosing dry-run vs
  live, interpreting dual-strategy output, sizing positions, or deciding
  weekly vs biweekly execution. Complements stock-analysis-system and
  post-analysis-audit.
---

# Turbo MTF Weekly Trader

Operational playbook for a **medium-aggressive NSE investor** running
**Turbo MTF** as primary strategy with **weekly analysis** and optional
**biweekly execution** (urgent SELLs always immediate).

This skill does **not** replace scoring code or auto-trade. It enforces
**process discipline** that turns pipeline output into repeatable edge.

## When to Apply

- User asks about weekly rebalance, Turbo MTF, 15-30 day holds, or cadence
- Before committing a live run (history writes)
- After backtest or walk-forward changes to Turbo MTF weights
- When same-day flip-flop appears (HOLD→SELL→HOLD)
- When sizing deploy cash (~₹1L) across NEW/INCREASE names

## Strategy Contract (Turbo MTF)

From `config.py` → `DUAL_STRATEGY_PROFILES['turbo_mtf']`:

| Field | Value |
|-------|-------|
| Label | TURBO MTF [PRIMARY] |
| Rebalance cadence | weekly (analysis) |
| Hold horizon | 15-30 days |
| Weight emphasis | multi_timeframe 35%, momentum_technical 25% |
| Risk | risk_adjustment -18% |
| Regime weights | `data/calibrated_weights_v2_{BULL,BEAR,SIDEWAYS}.json` |

Secondary profile: `monthly_stable_balanced` — compare in dual output;
do not switch primary without explicit user approval and backtest proof.

## Cadence Decision (backtest-backed)

Read `data/turbo_mtf_cadence_comparison.json` before changing execution:

| Mode | Total return | Sharpe | Trades | Use when |
|------|-------------|--------|--------|----------|
| **Weekly execute** | ~59% | ~1.95 | ~333 | Max ROI, accept churn |
| **Biweekly execute** | ~47% | ~2.50 | ~246 | Lower turnover, smoother |

**Default for this user:** analyze weekly; execute weekly unless user opts
into hybrid (analyze weekly, trade biweekly except urgent SELL / EXIT NOW).

## Weekly Workflow (Mon–Fri)

### Phase A — Preview (any day, market open or closed)

```bash
cd /Users/akulakavyashree/TestNetstock/Stock_Analysis
python3 analyze_top200_stocks_enhanced.py --dry-run --fast
```

Then: user says **`ANALYSE`** → follow `post-analysis-audit` skill.

Dry-run skips: `recommendation_history.csv` writes, `booking_history.json`,
smart profit booking persistence. Safe for same-day re-runs.

### Phase B — Live commit (once per week, post-close preferred)

```bash
python3 analyze_top200_stocks_enhanced.py
```

Requirements before live run:

1. Fresh holdings export in `Holding/holdings*.csv`
2. Prior dry-run reviewed; no open FAIL checks from audit
3. User explicitly ready to commit (never auto-live)

Then **`ANALYSE`** again on live output.

### Phase C — Execution checklist (manual)

| Step | Rule |
|------|------|
| SELL / EXIT NOW | Execute same session if audit PASS |
| NEW / INCREASE | Pack within deploy cash; respect max single-name weight |
| HIGH CONVICTION | Must not list symbols also in SELL list (dual-strategy check) |
| CONSIDER / WATCHLIST | No auto-trade; queue for next week |
| Cooldown suppressions | Do not override without user ack |

## Position Sizing Guardrails

Approximate book: **₹10L** holdings + **~₹1L** deploy cash.

| Check | Threshold | Action |
|-------|-----------|--------|
| Single-name weight | >10% | WARN — trim or block NEW unless user confirms |
| Sector cluster | >35% one sector | Review concentration before adding |
| Deploy cash | >100% packed | Reduce lowest-conviction NEW first |
| Urgent exit | EXIT NOW / Q131 | Size exit before new buys |

For sizing math methodology, invoke external skill `@position-sizing` and
`@risk-management` (adapt to INR / NSE, ignore crypto-specific APIs).

## v2 / Walk-Forward Context

- v2 drives live actions when `V2_SHADOW_MODE=False` in config
- Walk-forward file: `data/walkforward_v2_validation_fixed_turbo.json`
- IC_30d gate FAIL is **informational** during ANALYSE — not a block on
  trading unless user demotes v2 to shadow
- Weight changes require regression: `python3 tests/test_v2_regression.py`

## External Skill Routing

Use external skills in `.cursor/skills/` (see `external-skills-README.md`):

| Task | Skill |
|------|-------|
| Backtest new cadence or weight tweak | `@backtesting-frameworks`, `@walk-forward-validation` |
| Compare weekly vs biweekly formally | `@ab-test-setup` + project backtest scripts |
| IC / factor health on v2 components | `@alpha-evaluate`, `@alpha-monitor` |
| Portfolio metrics on backtest JSON | `@portfolio-analytics` |
| Excel action plan deep-read | `@xlsx-official` |
| Code change after audit finding | `@python-testing-patterns`, `@debugging-strategies` |
| Post-mortem on bad week | `@trade-journal` |

Always prefer **in-repo** `@stock-analysis-system` and `@post-analysis-audit`
for contracts, thresholds, and history schema.

## Flip-Flop Prevention

Same-day contradictory actions (e.g. SOLARINDS HOLD then SELL) usually from:

1. Re-running **live** multiple times per day (history feedback loop)
2. Code/config edits between runs
3. Budget packing order changes in SIDEWAYS regime

**Fix:** `--dry-run` for previews; **one live run per week**; do not clear
cache expecting stability.

## Enhancement Loop (next-level upgrades)

When improving the system (not just trading the week):

1. Hypothesis — one sentence (e.g. "biweekly hold flag reduces churn")
2. Backtest — `scripts/backtest_*.py` or production engine; save JSON to `data/`
3. Regression — `python3 tests/test_v2_regression.py` (224 suites)
4. Dry-run — verify report shape unchanged unless intentional
5. Dev log — append dated entry to `docs/dev-log.md`
6. Live — only after user approves system-wide threshold/weight changes

Invoke `@alpha-backtest` framing for steps 2-3; `@fix-review` before merge.

## Do Not

- Auto-trade or recommend broker orders without user confirmation
- Promote v2 live on historical `promotion_ready` alone
- Switch primary from Turbo MTF to Monthly Stable without backtest + user ack
- Install or invoke crypto/DEFI execution skills for NSE equity
- Skip ANALYSE after any live run

## Related Skills

- `.cursor/skills/stock-analysis-system/SKILL.md` — code contracts
- `.cursor/skills/post-analysis-audit/SKILL.md` — ANALYSE workflow
- `.cursor/skills/external-skills-README.md` — external skill index
