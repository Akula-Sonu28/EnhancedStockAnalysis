# Agent Instructions

Project: Stock_Analysis — NSE equity scoring + portfolio recommendation
pipeline.

## Always-applied rules

The following workspace rules are loaded for every interaction (see
`.cursor/rules/`):

- `core-interaction.mdc` — CO-STAR prompt analysis, communication modes
  (`HIGH LEVEL DESIGN`, `JUST CODE`, `REASONING VISIBLE`),
  `SUMMARIZE SESSION` / `LOAD MEMORY` workflow.
- `coding-standards.mdc` — clean code, SOLID, repository awareness,
  decision tracking.
- `stock-analysis-system.mdc` — project-specific architecture rules
  (orchestrator, regime detector, scoring engine, history schema,
  investor-safety guardrails, known bug patterns, post-change
  testing protocol).

## On-demand domain skills

`.cursor/skills/stock-analysis-system/SKILL.md` (with the deeper
`reference.md`) is the single source of truth for the project
architecture: the v1 + v2 scoring engines, config thresholds,
recommendation lifecycle, hard-stop tier table, regression suite
map, and v2 promotion state machine. Read it before any change to
scoring, allocation, exits, history schema, or report contracts.

**Operational strategy:** [docs/strategy-qmst.md](docs/strategy-qmst.md)
(QMST — pick/entry/exit layer doctrine). Pick rank = `fq_score`;
entry = turbo; exit = VMQ. SCORE is audit-only when
`ORACLE_STACK_ALIGN=true`. Master backlog:
[docs/QMST-MASTER-PLAN.md](docs/QMST-MASTER-PLAN.md).

`.cursor/skills/frontend-design/SKILL.md` governs HTML/UI work:
distinctive production-grade interfaces (no generic AI aesthetics).
Before restyling `Portfolio_Allocation_Dashboard.html` or
`portfolio_guide.html`, open `frontend/design-playbook.html` and
reuse its **Tape & Ledger** tokens (`--tape-*` CSS variables).
Presentation only — data contracts remain in `stock-analysis-system`.

`.cursor/skills/post-analysis-audit/SKILL.md` — after each
`analyze_top200_stocks_enhanced.py` run, the user may type **`ANALYSE`**
to run `scripts/post_analysis_audit.py` and get a PASS/WARN/FAIL report
(Excel contracts, log, history, IC telemetry, dual-strategy hints).

`.cursor/skills/five-agent-council/SKILL.md` — five-expert council
(Architect, Quant, Risk, Contract Auditor, Devil's Advocate) for
multi-round debate and peer acknowledgment before system changes. Trigger
with **`COUNCIL`**, **`DEBATE`**, or **`PEER REVIEW`**.

## Behavioural rules

- Read before editing.
- File size < 500 lines where reasonable.
- No secrets in code.
- Tests for behaviour changes.
- Confirm system-wide threshold / scoring-weight / exit-logic /
  report-format changes before implementing.
- Always `from config import get_config` — never instantiate
  `AnalysisConfig()` locally.
- v1 path remains untouched when editing v2; v2 is isolated to
  `hybrid_scoring_v2.py` + `data/calibrated_weights_v2*.json`.
- Universe filter (`src/universe_filter`) is mandatory for action
  surfaces.
- Action enum, Excel sheet names, and recommendation history columns
  are contracts (Suite 1 enforces).

## Testing protocol

After any code change touching scoring / allocation / history /
report:

```bash
python3 -c "import ast; ast.parse(open('FILE').read())"   # syntax
python3 tests/test_v2_regression.py                        # 222 suites
python3 tests/test_regression_fixes.py                     # broader regression
python3 -m pytest backtest/tests/ -v                       # backtest layer
```

## Dev log convention

Every non-trivial change appends a dated entry to `docs/dev-log.md`
with: Context, Findings (one bullet per fix with severity),
Files touched, Tests, and any Open / deferred items.
Investor-audit rounds are numbered (`Round N`) and each finding gets
a stable ID (`F-NEW-N`) so prior rounds can be cross-referenced.

