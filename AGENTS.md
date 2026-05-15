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

## On-demand domain skill

`.cursor/skills/stock-analysis-system/SKILL.md` (with the deeper
`reference.md`) is the single source of truth for the project
architecture: the v1 + v2 scoring engines, config thresholds,
recommendation lifecycle, hard-stop tier table, regression suite
map, and v2 promotion state machine. Read it before any change to
scoring, allocation, exits, history schema, or report contracts.

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
python3 tests/test_v2_regression.py                        # 192 suites
python3 tests/test_regression_fixes.py                     # broader regression
python3 -m pytest backtest/tests/ -v                       # backtest layer
```

## Dev log convention

Every non-trivial change appends a dated entry to `docs/dev-log.md`
with: Context, Findings (one bullet per fix with severity),
Files touched, Tests, and any Open / deferred items.
Investor-audit rounds are numbered (`Round N`) and each finding gets
a stable ID (`F-NEW-N`) so prior rounds can be cross-referenced.

## Cursorflow tooling (additive, project-specific rules above always win)

This workspace also has cursorflow registered as an MCP server
(`.cursor/mcp.json`) and as a set of generic role skills
(`.cursor/skills/cursorflow-*.md`). Use it only as a coordination /
memory layer — it does NOT replace any rule above.

### When to reach for cursorflow tools

- Before re-deriving a known fix or threshold, run `memory_search`
  in namespaces `patterns`, `edits`, or `decisions` to see if a prior
  session already solved it.
- After a non-trivial fix lands and tests pass, `memory_store` a
  pattern record in the `patterns` namespace (e.g. key
  `pattern-v2-weight-cap-2026-05`, value = one-line lesson).
- For multi-step changes that span scoring + history + report, use
  `swarm_init` then `agent_spawn` to coordinate, and
  `task_create` / `task_complete` to track sub-steps.
- For long debug sessions, `session_*` tools persist context so a
  `LOAD MEMORY` / `SUMMARIZE SESSION` cycle survives chat resets.

### Generic cursorflow role skills

`.cursor/skills/cursorflow-{architect,coder,tester,reviewer,researcher}.md`
are generic role hints. The project-specific
`.cursor/skills/stock-analysis-system/SKILL.md` is the source of
truth for this codebase and overrides them on any conflict.

### Hooks

`.cursor/hooks.json` runs `memory_search` before `python3` / `pytest`
shell commands and stores an edit trail after every file edit. Both
hooks are `optional: true` and fail open — they never block work.
Tighten the matcher there if they get noisy.

### Local installation note

`@cursorflow/cli` is not on npm; the MCP and hook commands reference
the local checkout at `/Users/akulakavyashree/cursorflow/packages/cli`.
If that path moves, update `.cursor/mcp.json` and `.cursor/hooks.json`.

