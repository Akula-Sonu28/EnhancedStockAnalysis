# Post-Analysis Audit — Reference Checklist

## Artifact discovery

| Artifact | Pattern | Location |
|----------|---------|----------|
| Excel report | `Enhanced_Stock_Report_YYYYMMDD_HHMMSS.xlsx` | `reports/` |
| Log | `top200_analysis_YYYYMMDD_HHMMSS.log` | `data/` |
| Merged holdings | `merged_portfolio_YYYYMMDD_HHMMSS.xlsx` | `reports/` |
| Dashboard | `Portfolio_Allocation_Dashboard.html` | repo root |
| Audit output | `post_analysis_audit_latest.md` | `data/` |

## Automated checks (`scripts/post_analysis_audit.py`)

### Run integrity

- Log: no `Traceback`, no unhandled `Exception`
- Log: `Batch analysis completed: N results, 0 failures`
- Log: `[v2] loaded <REGIME> calibrated weights` with file path and age

### Excel contracts (Suite 1 subset + telemetry)

Required sheets:

- Dashboard
- Portfolio Allocation
- Past Accuracy
- Complete Data
- Top Picks
- Trading Levels
- IC Telemetry

**Top Picks / Trading Levels:** no `SELL`, `WEAK SELL`, `REDUCE`, `EXIT` in recommendation column.

**IC Telemetry (informational / gates):**

| Row | Expect |
|-----|--------|
| `current market regime` / `active regime` | BULL / BEAR / SIDEWAYS |
| `LIVE ENGINE` | v2 (if live) |
| `v2 weight source` | REGIME-SPECIFIC when per-regime files used |
| `walkforward status` | FRESH if age ≤ 7d |
| `WALK-FORWARD VERDICT` | HOLD_SHADOW typical until OOS IC improves |
| `IC_30d gate` | Often FAIL — WARN only, not run blocker |

### Recommendation history

- Rows for run date match portfolio allocation count (~20–30)
- No same-day multiple actions per symbol
- `regime` column consistent with IC Telemetry
- Sell-side rows listed for action plan cross-check

### Sidecar JSON

- `data/v2_promotion_status.json` — note `promotion_ready` + `mode`
- `data/walkforward_v2_validation.json` — age via IC Telemetry embed

### Dual-strategy block (stdout only)

Printed at end of `analyze_top200_stocks_enhanced.py`:

- Table: Primary vs TURBO MTF vs MONTHLY
- `SPLIT` — strategies disagree (manual review)
- `HIGH CONVICTION (both strategies say BUY)` — must **exclude** symbols whose **primary** action is SELL / WEAK SELL / CONSIDER SELLING

Known bug pattern (FAIL if seen): `ECLERX` SELL + listed in HIGH CONVICTION.

## Graphify queries (optional)

```
graphify query "Q131 trace RECENT_BUY_COOLDOWN suppress"
graphify query "generate risk-based portfolio allocation sell recommendations"
graphify query "recorded recommendation SELL history"
```

## Agent output template

```markdown
## Executive summary
...

## Checks
| Check | Status | Detail |
...

## Action plan (today)
| Priority | Symbol | Action | Notional |
...

## v2 / validation context
...

## Follow-ups
- [ ] ...
```

## After fixing a FAIL in code

User must re-run analysis, then `ANALYSE` again. If code touched scoring/history:

```bash
python3 tests/test_v2_regression.py
```
