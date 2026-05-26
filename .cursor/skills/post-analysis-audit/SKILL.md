---
name: post-analysis-audit
description: >-
  Post-run audit after analyze_top200_stocks_enhanced.py completes. Use when
  the user says ANALYSE, ANALYZE, or asks to verify/check/audit the latest
  analysis run, Excel report, log, recommendation history, IC telemetry,
  dual-strategy output, or action plan.
---

# Post-Analysis Audit (ANALYSE)

Run this skill **after every** `python3 analyze_top200_stocks_enhanced.py` (or
`python main.py` full run) when the user says **`ANALYSE`** or **`ANALYZE`**.

For **same-day preview / re-runs** (market closed, checking output without
mutating history), run analysis with **`--dry-run`** first; use a **live** run
( no flag ) once per week when committing recommendations to history.

Do **not** change scoring code unless the user asks to fix a finding.

## Trigger

| User says | Action |
|-----------|--------|
| `ANALYSE` / `ANALYZE` | Full post-run audit (this skill) |
| `ANALYSE <path>` | Audit that specific report/log |
| After analysis completes unprompted | Offer: "Say **ANALYSE** for the post-run audit." |

## Workflow (execute in order)

### 1. Automated checks

```bash
cd /Users/akulakavyashree/TestNetstock/Stock_Analysis
python3 scripts/post_analysis_audit.py
```

Preview re-run (no history writes — avoids same-day flip-flop churn):

```bash
python3 analyze_top200_stocks_enhanced.py --dry-run --fast
```

Optional — if terminal output from the run is available (e.g. Cursor terminal
file), pass it for dual-strategy validation:

```bash
python3 scripts/post_analysis_audit.py --terminal /path/to/terminal_capture.txt
```

Output is printed and saved to `data/post_analysis_audit_latest.md`.

Exit code `1` means at least one **FAIL** check.

### 2. Read domain contracts (only if FAIL/WARN needs context)

Open `.cursor/skills/stock-analysis-system/SKILL.md` when interpreting:

- action enum / history schema
- Excel sheet contracts
- v2 promotion / HOLD_SHADOW semantics

### 3. Graphify (optional, for root-cause on FAIL)

```bash
graphify query "validate_recommendation hard stop cooldown Q131"
graphify query "dual strategy HIGH CONVICTION portfolio allocation"
```

### 4. Agent synthesis (required)

Produce a report with these sections:

1. **Executive summary** — 2–4 sentences: safe to use or not, regime, top actions.
2. **Check table** — from script output (PASS / WARN / FAIL).
3. **Trading action plan** — extract from terminal or Portfolio Allocation:
   SELL / CONSIDER / NEW / HOLD counts; net cash deployment if shown.
4. **Investor-safety highlights** — cooldown suppressions, active Q131 exits.
5. **v2 / forward-test context** — walk-forward verdict, IC gates (informational).
6. **Follow-ups** — only concrete fixes or manual verifications (no generic fluff).

### 5. Known manual checks (script cannot fully automate)

| Check | How |
|-------|-----|
| Dual-strategy HIGH CONVICTION | Terminal only — sells must not appear in BUY conviction list |
| HONASA / ₹0 exit notionals | Cross-check `Holding/*.csv` qty vs merged portfolio |
| Label drift | CONSIDER SELLING vs WEAK SELL in history vs terminal |
| Execute trades | User decision — never auto-trade |

## Pass / warn / fail policy

| Status | Meaning |
|--------|---------|
| **FAIL** | Contract broken, crash markers, or sell listed as HIGH CONVICTION BUY — investigate before acting |
| **WARN** | Known weak signals (IC gates), missing optional data, zero MONEY rows, historical promotion_ready |
| **PASS** | Check satisfied |
| **INFO** | Context only (regime, row counts, sell symbols) |

## Do not

- Skip the script and guess from memory.
- Treat `promotion_ready=True` in **historical** mode as permission to promote live.
- Recommend code changes during ANALYSE unless user asks to fix findings.
- Run full regression suite unless a FAIL implies a code regression (user request).

## Reference

Full checklist and column details: [reference.md](reference.md).
