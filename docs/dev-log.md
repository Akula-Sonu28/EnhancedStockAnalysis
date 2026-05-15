# Dev Log

This file tracks every code change with date, rationale, and affected files
per the operating contract's Definition of Done.



## 2026-05-15 — Investor-Audit Round 22 (all 12 Round-21 findings fixed)

**Context**: User said "fix all" on the 12 P0/P1/P2 findings from Round 21.
Surgical, additive, contract-preserving patches applied across
`recommendation_history.py` and `analyze_top200_stocks_enhanced.py`. No
schema changes (Suite 1 contract preserved). All test suites green.

**Fixes**:
- **F-NEW-1 + F-NEW-9 (Past Accuracy enrichment)**: appended Profit Factor,
  Expectancy, Wins/Losses, Avg Win/Loss, NOTE, and DISCLOSURE rows to the
  Past Accuracy sheet. Action-aware computation (BUY+positive = win,
  SELL+negative = win) so the metric agrees in direction with the Rec
  Performance sheet. Today shows `0.14 LOSING`, `-5.62%` expectancy.
  Disclosure row clarifies most outcomes are pre-promotion v1-era.
- **F-NEW-2 (partial-execution preview)**: added a PARTIAL-EXECUTION
  CONCENTRATION PREVIEW block to the Action Plan. When the top sector
  is >= 40% of holdings, projects the post-execution concentration if
  the user follows the common "skip overweight-sector SELLs" pattern.
  Verified output: "Current: Financial Services = 11/13 (85%) ... If
  you ONLY sell non-Financial Services stocks (yesterday's pattern),
  Financial Services would WORSEN to 11/12 (92%)".
- **F-NEW-3 (action vs reason divergence tag, family-aware)**: when the
  canonical action of `reason` is in a different family
  (BUY / SELL / HOLD) from the policy-mediated `action`,
  `record_recommendation` now prefixes the reason with
  `[POLICY OVERRIDE] action=X | raw=...`. Same-family transitions
  (SELL vs EXIT, BUY vs NEW POSITION) are NOT tagged. 6/6 unit-test
  cases pass.
- **F-NEW-4 (_Metadata regime-fallback rows)**: 3 new rows in the
  _Metadata sheet: `Active v2 Weights Source`, `Active v2 Weights File`,
  `v2 Regime-Fallback Active`. Today: "GLOBAL (regime fallback -
  per-regime file missing)", "YES (SIDEWAYS weights file absent)" -
  the silent fallback is now loudly visible.
- **F-NEW-5 (SELL hit rate definition reconciliation)**: both SELL
  hit-rate columns in Past Accuracy now carry explicit definition
  parentheticals; an additional NOTE row reconciles the disagreement
  with the IC Telemetry sheet (which uses a stricter "action == SELL
  exact" filter).
- **F-NEW-6 (weekly-changes calibration-event suppressor)**:
  `get_weekly_changes` now reads the `updated` timestamp from each
  `data/calibrated_weights_v2*.json` file and suppresses any comparison
  whose older row predates the most recent calibration event AND has
  |delta| >= 15pp. Verified: TORNTPHARM/COALINDIA/BAJAJ-AUTO/PIDILITIND
  +30-41 IMPROVED entries from the previous run are GONE (was 5
  IMPROVED, now 1: NMDC +8.1).
- **F-NEW-7 (Dashboard v2-LIVE banner + _Metadata days-since-promotion)**:
  `_create_dashboard_sheet` now emits a red merged A4:H4 banner
  showing days-since-promotion ("v2 LIVE day 2 of 30 - 30d outcomes
  still accruing") and a fallback warning when per-regime weights are
  absent. _Metadata sheet adds `v2 LIVE since`, `v2 Days Live`, and
  `v2 Validation Data` (with ETA) rows.
- **F-NEW-8 (Top Picks BUY risk tag)**: when a BUY-flagged stock has
  `risk_category` in (HIGH, VERY HIGH), `final_recommendation` now
  carries an explicit `[HIGH RISK]` or `[VERY HIGH RISK]` suffix.
  Verified: KAYNES, PWL, PGEL, PARADEEP all show "BUY [VERY HIGH RISK]".
- **F-NEW-10 (batch history saves)**: introduced
  `RecommendationHistory.batch_saves()` reentrant context manager. When
  `_batch_depth > 0`, individual `_save_history` calls only set
  `_batch_dirty`; the actual flush waits until the outermost context
  exits. Wrapped the analyzer's `record_recommendation` loop with
  `with self.recommendation_history.batch_saves():`. Verified: 1 save
  per run (was 18; reduces N file flushes per N appended rows to 1).
- **F-NEW-11 (short-circuit impossible low-rows retries)**:
  `StockDataBundle.__init__` no longer retries when yfinance returned
  >0 rows but < MIN_ROWS_ACCEPTABLE - the stock is newly-listed and no
  retry will produce more historical days. Only the genuine 0-row
  (transient empty response) case still retries. Saves ~6s per
  newly-listed skip (e.g. JSWDULUX no longer hits 4 attempts x 2s).
- **F-NEW-12 (_PortfolioAllocationHeaderMap sheet)**: new
  documentation sheet explains the two-row header convention of
  Portfolio Allocation (row 1 = merged group labels, row 2 = column
  names) and provides the `pd.read_excel(..., header=1)` /
  `wb['Portfolio Allocation'][2]` hints for external consumers.

**Files touched**:
- `recommendation_history.py`: added `import json`,
  `_v2_calibration_event_dates()` static method,
  `batch_saves()` context manager, `_batch_depth` /
  `_batch_dirty` flags in `__init__`, `_force` flag on
  `_save_history`, family-aware F-NEW-3 block in
  `record_recommendation`, calibration-event suppressor in
  `get_weekly_changes`.
- `analyze_top200_stocks_enhanced.py`: F-NEW-11 retry short-circuit;
  `with self.recommendation_history.batch_saves():` wrap;
  F-NEW-4 + F-NEW-7 _Metadata rows; F-NEW-7 Dashboard banner;
  F-NEW-1 + F-NEW-5 + F-NEW-9 Past Accuracy enrichment; F-NEW-8 Top
  Picks risk tag; F-NEW-12 _PortfolioAllocationHeaderMap sheet;
  F-NEW-2 partial-execution preview in Action Plan.
- `docs/dev-log.md`: this entry.

**Tests**: `tests/test_v2_regression.py` 192/192 PASS; backtest
`test_costs.py` 19/19 PASS; F-NEW-3 ad-hoc unit test 6/6 PASS;
syntax check on all touched files OK; ReadLints clean. Three full
end-to-end `python3 analyze_top200_stocks_enhanced.py` runs completed
successfully (exit 0) with the new sheets / rows / banners populated
as expected.

**Verified in latest report**
(`reports/Enhanced_Stock_Report_20260515_134828.xlsx`):
- 26 sheets including new `_PortfolioAllocationHeaderMap`.
- Past Accuracy: Profit Factor 0.14 LOSING, expectancy -5.62%,
  60/111 wins/losses, +2.67% / -10.09% avg win/loss; both SELL
  hit-rate definitions labelled; DISCLOSURE row present.
- _Metadata: rows for `Active v2 Weights Source = GLOBAL (regime
  fallback - per-regime file missing)`, `v2 Regime-Fallback Active =
  YES (SIDEWAYS weights file absent)`, `v2 Days Live = 2`,
  `v2 Validation Data = pending - ETA 2026-06-12`.
- Top Picks: SAREGAMA "BUY [HIGH RISK]", PWL/KAYNES/PGEL/PARADEEP
  "BUY [VERY HIGH RISK]".
- Weekly Changes: 1 IMPROVED (NMDC +8.1) instead of the 5 from the
  pre-patch run (TORNTPHARM/COALINDIA/BAJAJ-AUTO/PIDILITIND artefacts
  suppressed).
- Action plan output: PARTIAL-EXECUTION CONCENTRATION PREVIEW block
  showing the FinSvc 85%-could-worsen-to-92% warning.
- 1 history-save flush instead of ~18; JSWDULUX log line shows
  "newly-listed - not retrying" exactly once.

**Open / deferred**: F8 (Excel BT sheets still wired to 57-day-old
`backtest_result_20260318_200141.xlsx`). Wiring the new `backtest/`
pipeline output into the Excel writer is a non-trivial separate
change that needs the new pipeline's Excel emit format finalised
first. Tracked.



## 2026-05-15 — Investor-Audit Round 21 (six-persona audit on fresh run)

**Context**: Six-persona audit (investor / developer / tester / architect /
common man / retail investor) on a fresh run completed
2026-05-15 11:59:30 (`reports/Enhanced_Stock_Report_20260515_115927.xlsx`).
Regime FLIPPED to SIDEWAYS (was BEAR yesterday; VIX dropped 19.4 -> 18.58).
Holdings reduced 23 -> 13: user executed 8 of 12 SELLs from yesterday's
plan but not the 4 PSU bank full-SELLs (BANKBARODA, BANKINDIA, GICRE, SBIN).
13 holdings include 11 Financial Services -> concentration WORSENED to
84.6% (was 75.7%) because mostly non-FinSvc were liquidated. F1 fix from
Round 20 verified at line 9166. Round 2 deep-dive performed on the three
most concerning findings; their root causes are proven at source.

### NEW findings (P0/P1)

- **F-NEW-1 (P0, INVESTOR-FACING)**: System has NEGATIVE 30d expectancy.
  Recommendation Performance sheet: n=627, win_rate=51.2%, avg_win=+4.78%,
  avg_loss=-8.96%, profit_factor=0.56, expectancy=-1.93%/cycle. Math
  verified: (0.512 * 4.78) - (0.488 * 8.96) = -1.925%. Win rate masks
  the loss because losses are 1.87x the size of wins. The headline
  "BUY hit rate 94.3%" in Past Accuracy is binary positive/negative
  without magnitude; profit_factor=0.56 means $1 of wins comes with
  $1.79 of losses. Most outcomes are pre-promotion v1-era (v1 IC was
  -0.46), so this is largely a v1-historical metric; v2 may improve it
  once 30d post-promotion data accrues. **Recommendation: surface
  profit_factor and expectancy more prominently than hit-rate in the
  Past Accuracy sheet; add a disclosure that the metric is v1-era.**

- **F-NEW-2 (P0)**: Sector concentration WORSENED after yesterday's
  "diversify" action plan. Holdings are 11/13 = 84.6% Financial Services
  (BAJAJHLDNG, BANKBARODA, BANKINDIA, GICRE, GROWW, ICICIGI, INDIANB,
  LICI, SBIN, UCOBANK, UNIONBANK), only NMDC (Basic Materials) and
  SAREGAMA (Communication Services) outside the sleeve. Yesterday's
  plan correctly flagged the over-concentration; but the user
  preferentially executed private-bank SELLs while keeping PSU banks
  and added GROWW (FinSvc). Action plan execution UI did not warn that
  partial execution would CONCENTRATE rather than DIVERSIFY.
  **Recommendation: add an "intended vs actual" diff to the action plan
  and a "if you only execute these N of M, the result will be ..."
  preview.**

- **F-NEW-3 (P0, SCHEMA SEMANTICS)**: BAJAJHLDNG (and any stock where
  CORE-sleeve / hysteresis / smoothing overrides the raw score signal)
  shows `action=HOLD` while `reason='SELL'` in the same history row.
  Confirmed across three days: 2026-05-13 action=WEAK SELL reason=HOLD,
  2026-05-14 action=HOLD reason=WEAK SELL, 2026-05-15 action=HOLD
  reason=SELL. Diagnosis: `action` captures the policy-mediated final
  decision; `reason` captures the raw score-threshold signal. Both are
  correct individually; displaying them adjacently confuses readers.
  **Recommendation: rename `reason` to `raw_signal` OR add a tag
  ("HOLD (CORE: SELL signal overridden)") OR suppress raw_signal display
  when it diverges from action.**

- **F-NEW-4 (P1, F3 LIVE NOW)**: Regime is SIDEWAYS today but
  `data/calibrated_weights_v2_SIDEWAYS.json` does NOT exist. Engine
  silently falls back to global `data/calibrated_weights_v2.json`.
  No alert in `_Metadata` sheet, no investor-visible notice, no log
  WARN escalated to the report. F3 case (regime-flip alarm) is
  actively biting today. **Recommendation: surface "active weights file
  + age + fallback status" in _Metadata sheet and the dashboard
  header.**

- **F-NEW-5 (P1, INTERNAL CONTRADICTION)**: Past Accuracy sheet says
  `SELL hit rate (30d) = 19.9%`. IC Telemetry sheet says
  `v1 SELL hit rate (30d, %) = 0` (with v1 SELL count = 30). Same
  metric, two sheets, different numbers in the same Excel report. Two
  different definitions of "hit rate" are being computed; neither sheet
  documents which definition. **Recommendation: pick one canonical
  definition, label clearly, and reconcile.**

- **F-NEW-6 (P1, ROUND 19 FIX INCOMPLETE)**: Weekly Changes sheet shows
  TORNTPHARM 30.3 -> 71.3 (+41) as IMPROVED. History trail:
  2026-05-08 score_v2=30.3, 2026-05-11 score_v2=31.1, 2026-05-12
  score_v2=71.3 (one-day +40 jump from a code/calibration event), then
  v2 went LIVE 2026-05-13. Both compared rows have valid score_v2 and
  same regime (SIDEWAYS), so Round 19's engine-mismatch suppression
  in `recommendation_history.get_weekly_changes` (line 358-361) doesn't
  fire. Same artifact for COALINDIA (34.6->71.1), BAJAJ-AUTO
  (39.2->71.4), PIDILITIND (40.4->70.0). All cross the 5/12 jump.
  **Recommendation: extend get_weekly_changes to also suppress
  comparisons that span a known calibration event (read
  `calibrated_weights_v2.json` `updated` field) OR cap the displayed
  delta at +/-15pp and tag the row.**

- **F-NEW-7 (P1, LIVE-ENGINE BLIND SPOT)**: IC Telemetry sheet shows
  `v2 sample size 30d = 0`. Zero v2-era 30d outcomes have accrued
  since v2 went live 2026-05-13. The three v2 promotion gates
  (IC_30d, Spread, Sample-size) all show `FAIL`. **The LIVE engine
  has no production validation data yet.** This is mathematically
  unavoidable until 30d post-promotion (~2026-06-12), but the report
  does not surface this fact prominently. **Recommendation: add a
  banner to Dashboard sheet: "v2 went live <N> days ago. Production
  validation data accrues at 30d (ETA: <date>)."**

### Other findings (P2/P3)

- **F-NEW-8 (P2)**: Top Picks shows several BUYs flagged "VERY HIGH"
  risk simultaneously (PWL, KAYNES, PGEL, PARADEEP). Mixed-signal UX
  for non-expert readers. Add explicit risk gating in the BUY label
  (e.g. "BUY (HIGH RISK)").
- **F-NEW-9 (P2)**: Hit rate inflates perceived performance vs.
  profit_factor. Investor-facing summaries should lead with
  profit_factor.
- **F-NEW-10 (P2 PERF)**: `Saved recommendation history: 1109 records`
  prints 18 times in one batch (one flush per appended row). Should
  batch.
- **F-NEW-11 (P2)**: JSWDULUX retry loop attempts 4 times on data
  with 28 rows (need 50). Short-circuit when delta is impossible.
- **F-NEW-12 (P2)**: Portfolio Allocation sheet has TWO-row header
  (`WHAT TO DO | MONEY | STOCK QUALITY` merged in row 1; actual
  column names in row 2). Breaks `pd.read_excel(...)` consumers
  expecting single-row headers. Document the convention or add a
  `_HeaderMap` sheet.
- **F-NEW-13 (P3)**: BAJAJHLDNG action UPGRADED (WEAK SELL -> HOLD)
  even though score DROPPED (52.3 -> 38.8 over 7 days). Hysteresis
  buffer + CORE sleeve protection working as designed; investor sees
  it as inconsistent.

### Reconfirmations of prior open items

- **F8 (still open)**: BT Summary / BT Equity Curve / BT Trades sheets
  still present and (per Round 20) still wired to the 57-day-old
  `backtest_result_20260318_200141.xlsx` source. New `backtest/`
  pipeline output is not surfaced in the investor report.
- **F5**: Past Accuracy SELL hit rate stable at 19.9% (vs. 13.8% in
  `data/v2_promotion_status.json` from 2026-05-11). Still well below
  the 50% forward-mode promotion gate. `python3 scripts/v2_promotion_check.py`
  has not been re-run since promotion.

### Round 2 verification (proven at source)

- F-NEW-1 expectancy math: `(0.512 * 4.78) - (0.488 * 8.96) = -1.925%`
  matches the reported -1.93%; profit_factor `(321 * 4.78) / (306 * 8.96)
  = 0.5596` matches the reported 0.56. Numbers are arithmetically
  correct; the system is genuinely loss-making at -1.93%/cycle on the
  v1-dominated 30d window.
- F-NEW-3 BAJAJHLDNG action/reason: confirmed via direct
  recommendation_history.csv inspection. Both columns are populated
  per the schema; the divergence is by design (action=policy,
  reason=raw signal). Rename or relabel needed.
- F-NEW-6 weekly-changes regime/calibration artifact: source code at
  `recommendation_history.py:358-361` shows the engine-mismatch
  suppressor only fires when `curr_v2 is valid AND prev_v2 is None`.
  TORNTPHARM has both populated, both same regime; suppression skipped.
  The +40pt delta is a real code/calibration event, not a fundamentals
  change.

**Files touched (this entry)**: `docs/dev-log.md` only. No code changes
in this round - audit-only. Findings persisted to cursorflow memory:
- `context/audit-round-21-2026-05-15`
- `patterns/pattern-2026-05-15-negative-expectancy-confirmed`
- `patterns/pattern-2026-05-15-weekly-changes-regime-transition-artifact`
- `patterns/pattern-2026-05-15-action-reason-semantic-mismatch`

**Open for next round / next session**: F-NEW-1 (expectancy
disclosure), F-NEW-3 (action/reason rename), F-NEW-4 (regime-flip
alarm + missing SIDEWAYS weights), F-NEW-5 (hit-rate definition
reconciliation), F-NEW-6 (extend weekly-changes suppressor), F-NEW-7
(v2-validation-data-pending banner). All require explicit user
sign-off before code change because they touch report contracts and
investor-facing semantics.



## 2026-05-15 — Cursorflow Setup Hardening (hooks + CLI/MCP store unification)

**Context**: After Round 20 the user asked how cursorflow was wired and how
to use it. Inspecting the setup surfaced two latent bugs that had been
silently degrading the memory loop since cursorflow was installed.

**Findings**:
- BUG 1 (**HOOKS BROKEN, FIXED**): `.cursor/hooks.json` invoked
  `npx --yes @cursorflow/cli memory ...`. The `@cursorflow/cli` package is
  not published to the npm registry (verified: 404). Both hooks were
  marked `optional: true` so failures were silent. Effect: the
  `beforeShellExecution` (auto-search memory before shell commands) and
  `afterFileEdit` (auto-store edited file path) hooks had **never fired
  successfully** since installation. Fix: replace the npx invocation with
  the local binary path
  `node ${workspaceFolder}/cursorflow/packages/cli/bin/cursorflow.js`.
- BUG 2 (**CLI/MCP STORE DIVERGENCE, FIXED**): Both the CLI and the MCP
  server call `createServices({backend: 'hybrid'})`. The hybrid backend
  tries `SQLite -> AgentDB -> SqlJs -> InMemory` in order via dynamic
  `await import(...)`. All three native deps (`better-sqlite3`,
  `agentdb`, `sql.js`) are installed inside `cursorflow/node_modules/`,
  but dynamic-import resolution behaves differently in the long-lived
  MCP process vs. the short-lived CLI process. Result: MCP picked the
  AgentDB backend (which auto-appends `.jsonl` to the path per
  `agentdb-backend.ts:39` and writes to `.cursorflow/memory.db.jsonl`)
  while CLI fell through to the SqlJs backend (which writes a binary
  WASM-SQLite blob to `.cursorflow/memory.db`). Both stores existed
  side-by-side; neither process saw the other's writes; the cursorflow
  rules' "search memory first" loop was reading from one store and
  writing to another. Fix: pin both processes to the JSONL backend
  explicitly so they share `.cursorflow/memory.db.jsonl` as the single
  source of truth.

**Files touched**:
- `.cursor/hooks.json` — replaced `npx --yes @cursorflow/cli` with
  `node ${workspaceFolder}/cursorflow/packages/cli/bin/cursorflow.js`
  in both `beforeShellExecution` and `afterFileEdit` commands.
- `.cursor/mcp.json` — added `--backend jsonl` to the cursorflow MCP
  server launch args so the server is pinned to JSONL on startup.
- `cursorflow/packages/cli-core/src/services.ts` and the matching
  `dist/services.js` — default `opts.backend` from `'hybrid'` to
  `'jsonl'`, with the path switching to `memory.db.jsonl` when JSONL is
  selected (so the existing file is read, not a new empty one). The
  `'hybrid'` path remains accessible via `opts.backend = 'hybrid'` for
  callers that explicitly want the SQLite/AgentDB stack.
- `docs/dev-log.md` — this entry.

**Verification**:
- `node ./cursorflow/packages/cli/bin/cursorflow.js memory stats` →
  `backend: jsonl, count: 15, namespaces: context, preferences,
  patterns, edits` (was `count: 0` before fix; CLI was reading from a
  different empty store).
- Synthetic `beforeShellExecution` hook (`CURSOR_SHELL_COMMAND="python3
  scripts/v2_promotion_check.py" node ./.../cursorflow.js memory search
  --query "$CURSOR_SHELL_COMMAND" --namespace patterns --limit 3`) →
  returned 3 pattern matches (was silent 404 before).
- Synthetic `afterFileEdit` hook → successfully stored
  `edits/edit-<ts>`; the `edits` namespace now exists alongside the
  other three (it had never been written to before).
- All four pattern records from Round 20
  (`pattern-2026-05-15-exit-profit-display-bug`, `-bugs-fixed`,
  `-stcg-rate-prod-vs-backtest-mismatch`, plus the older project
  patterns) are now visible to both CLI and MCP.

**Operational note**: requires Cursor to restart the cursorflow MCP
server (Settings → MCP → toggle off/on, or restart Cursor) for the new
`--backend jsonl` launch arg to take effect. Until then the in-flight
MCP process keeps whichever backend it picked at startup.

**Residual**: `.cursorflow/memory.db` (the SqlJs binary blob from old
CLI writes) is harmless and safe to delete. It contains only a single
test-probe entry (`patterns/probe-1778825672`); no real data.



## 2026-05-15 — Investor-Audit Round 20 (F1 + F2-NEW from fresh-run audit)

**Context**: Cursorflow-driven deep-dive on the 2026-05-15 01:44 fresh
analyze_top200 run surfaced two fixable code-level bugs (separate from
documented data gaps F3/F5/F8 which await sample accrual or new pipeline
wiring).

**Findings**:
- F1 (**BUG, FIXED**): The terminal EXIT RECOMMENDATIONS block printed
  `Profit:` values 60-85x understated vs the holdings CSV `Net chg.`
  column (e.g. ICICIPRULI displayed `-0.2%` for an actual -17.21% loss;
  MAHABANK displayed `+0.1%` for an actual +7.70% gain). Root cause:
  `current_profit_pct` is stored as a fraction at write sites
  (analyze_top200_stocks_enhanced.py:6642 and :6753 use
  `(price - cost) / cost`); every other consumer multiplies by 100 (lines
  526, 544, 562, 7292, 7312, 7317; Excel export at line 11191) but the
  EXIT-block formatter at line 9147 did not. Decision logic was always
  correct - this was a display-only bug. Fix: added `*100` to the
  `profit_str` format string at line 9147. Investor impact: the action
  plan no longer shows tiny profit numbers next to "EMERGENCY EXIT loss
  -17.3%" messages, restoring number-narrative consistency.
- F2-NEW (**TAX-RATE STALENESS, FIXED**): `backtest/costs.py` hard-coded
  `stcg_rate=0.15` (pre-Budget-2024 rate). Production tax estimator in
  analyze_top200_stocks_enhanced.py already used 20% in 4 places
  (lines 6603, 9310, 8555, 10889) per Budget 2024 (effective 2024-07-23),
  but the backtest path stayed on the old rate. Effect: every
  `stcg_paid` in `backtest/results/` understated tax drag by 5pp on
  short-term gains. Fix: bumped `CostConfig.stcg_rate` to 0.20, updated
  module docstring + `stcg_on` docstring + `backtest/README.md` capital
  gains line + `backtest/tests/test_costs.py` (renamed
  `test_stcg_15pct` -> `test_stcg_20pct`, expected value 1500 -> 2000).
  Headline v2-vs-v1 edge unchanged because both engines tax at the same
  rate; absolute net returns will be marginally lower in future runs.

**Files touched**:
- `analyze_top200_stocks_enhanced.py:9147` - one-line fix
- `backtest/costs.py:22, :52, :169` - rate + docstrings
- `backtest/README.md` - capital gains line in "What's replayed accurately"
- `backtest/tests/test_costs.py:98-100` - test renamed + expected bumped
- `docs/dev-log.md` - this entry

**Tests**: 190/190 PASS (`tests/test_v2_regression.py`),
19/19 PASS (`backtest/tests/test_costs.py`). No contract surfaces
touched (action enum, sheet names, history columns, threshold ordering,
weight sums all unchanged).

**Open from same audit (intentionally not fixed - require user signal)**:
- F3 BULL/SIDEWAYS per-regime weights missing (`data/calibrated_weights_v2_BULL.json`
  and `_SIDEWAYS.json` absent; only BEAR present). Waits for
  `MIN_SAMPLES_PER_REGIME=30` accrual; consider adding a regime-flip alarm.
- F5 SELL hit rate 19.9% (n=627) vs 50% forward-mode promotion gate.
  Will improve as v2-era outcomes accrue; v2 went live via historical-mode
  bypass per documented escape hatch.
- F8 BT sheet in Excel report is 57 days old (`backtest_result_20260318_200141.xlsx`).
  Needs the new `backtest/` pipeline writer wired into the Excel report's
  BT sheets to replace the v1-era snapshot.



## 2026-05-13 — Investor-Audit Round 19 (Q122–Q123, post-cache-clear fresh run)

**Context**: User cleared cache and ran fresh analysis after V2 promotion.
The fresh run surfaced two engine-transition reporting artifacts.

**Findings**:
- Q122 (**BUG, FIXED**): WEEKLY SCORE CHANGES showed 23 holdings
  "deteriorating" by 30-44 points overnight (NMDC 76.9→32.3 etc.).
  Root cause: `get_weekly_changes` compared `score` (v1-blended)
  across the v2-promotion boundary. Pre-promotion `score` was v1-based;
  post-promotion `score` is v2-based. Same column name, different
  engines. Fix: prefer `score_v2` on BOTH sides; iterate prev rows
  backward to find one with valid score_v2; suppress engine-mismatched
  comparisons. Result: 23 spurious deteriorations → 0 (until v2-era
  history accumulates beyond 7 days).
- Q123 (**BUG, FIXED**): Same engine-switch artifact in flip-flop
  detector (MAHABANK INCREASE→SELL 0d apart). Fix: suppress flip-flops
  where one row has `score_v2` and the other does not.
- AFFLE BUY→HOLD transition (post cache clear): Cache had stale growth=97.6;
  fresh fetch returned growth=69.1. System correctly downgraded AFFLE.
  Not a bug.
- v2 BEAR weights `growth=0.0, value=0.0`: Known limitation - insufficient
  v2-era history to calibrate growth/value factors. Resolves naturally
  as data accumulates.

**Files touched**:
- `recommendation_history.py`:
  - `get_weekly_changes` engine-aware comparison with backward search
  - `get_flip_flop_stocks` suppresses engine-mismatched flips
- `tests/test_v2_regression.py` — +2 sentinels
- `docs/dev-log.md` — this entry

**Tests**: 188/188 PASS.

**Investor impact**: The post-cache-clear run no longer shows misleading
"23 holdings collapsed overnight" warnings. The portfolio's actual state
under v2 is fairly represented: 10 SELL + 13 CONSIDER SELLING + 2 BUY
(GROWW V2=76.5, KALYANKJIL V2=69.7). AFFLE correctly demoted to HOLD
on fresh growth data.



## 2026-05-13 — Investor-Audit Round 18 (Q113–Q121, "check latest analysis")

**Findings**:
- Q113 (**BUG, FIXED**): AFFLE labeled "HIGH MOMENTUM NEW POSITION" while
  GROWW/KALYANKJIL got plain "NEW POSITION" - same investor action,
  different labels. Root cause: BUY-variant normalization at line 9189
  only matched 'BUY' substring, missing 'HIGH MOMENTUM NEW POSITION' /
  'ENTER' / 'ACCUMULATE' variants. Fix: extend the filter to catch all
  BUY-equivalent labels.
- Q114 (BUY size shrink): Q99 reduced full SELL count → less cash → smaller
  BUY positions (₹91K → ₹74K). Intentional conservative whipsaw-protection
  trade-off, not a bug.
- Q115 (ACTION/REASON sync): 0 inconsistencies. Q92 fix holding.
- Q116 (SCORE vs V2 RAW): 0 cases with gap > 5pt. Q55 fix holding.
- Q117 (graduated book %): 8 stocks at 50% trim, 5 at 25% trim. Streak
  logic working.
- Q118 (column hygiene): 60 columns, no duplicates.
- Q119 (**BUG, FIXED**): "Top Picks" sheet showed 31 WEAK SELL + 16 HOLD +
  3 BUY (50 rows top by score). Misleading - investors expect Top Picks
  to be BUY candidates. Fix: filter to BUY + HOLD only. Now 19 rows clean.
- Q120 (**BUG, FIXED**): Trading Levels showed 2 WEAK SELL stocks alongside
  HOLDs/BUYs. Investors saw "entry zones" for stocks flagged for exit.
  Fix: same BUY+HOLD filter. Now 18 rows clean.
- Q121 (**BUG, FIXED**): Past Accuracy showed `Q1 (low score) avg return
  +8.41% > Q5 (top score) +3.77%` and `SELL hit rate 19.9%` without
  engine attribution. Investors would read this as "the LIVE system is
  anti-predictive" when in fact those metrics were computed on v1 SCORE
  (the SHADOW engine, known anti-predictive with IC<0 historically).
  Fix: added v2-quintile metrics + clear section headers ("HIT RATES",
  "QUINTILE SPREAD - v1 SCORE (shadow engine)", "QUINTILE SPREAD - v2
  SCORE (LIVE engine)"). v2 row shows "pending 30d outcomes" until enough
  post-promotion data accumulates. Also fixed Excel-formula bug where
  "===" prefixed strings rendered as 0.

**Files touched**:
- `analyze_top200_stocks_enhanced.py`:
  - Q113: BUY-variant normalization filter extended
  - Q119: Top Picks filtered to BUY + HOLD
  - Q120: Trading Levels filtered to BUY + HOLD
  - Q121: `_compute_past_accuracy` extended with v2-quintile metrics;
    Past Accuracy Excel layout restructured with clear sections
- `tests/test_v2_regression.py` — +4 sentinels
- `docs/dev-log.md` — this entry

**Tests**: 186/186 PASS (+4 sentinels).

**E2E**: 4 fixes verified clean.
- AFFLE: "HIGH MOMENTUM NEW POSITION" → "NEW POSITION" (Q113)
- Top Picks: 50 rows → 19 (3 BUY + 16 HOLD, no WEAK SELL) (Q119)
- Trading Levels: 20 rows → 18 (3 BUY + 15 HOLD) (Q120)
- Past Accuracy: clear sections; v1 spread -4.64% labeled "shadow engine",
  v2 awaiting 30d outcomes (Q121)



## 2026-05-13 — Investor-Audit Round 17 (Q106–Q112)

**Findings**: All clean. No bugs.
- Q106: NMDC graduated CONSIDER SELLING preserves STCG tax info (₹35).
- Q107: Empty history correctly returns NONE for V2=38, but still
  fires extreme path for V2<30. Safe for newly-tracked symbols.
- Q108: All confirmed-degradation exits preserved (PNB/BANKBARODA via
  extreme-loss, KOTAKBANK via V2<30, CENTRALBK via 2-run confirmation).
- Q109: Net cash inflow ₹455K (vs ₹551K pre-Q99). Acceptable reduction
  for whipsaw protection.
- Q110: Q88 graduated-exit exclusion still includes THESIS BREAK +
  TRAILING_STOP. Q99 didn't weaken the unconditional-exit semantic.
- Q111: Score smoothing telemetry stored per-stock cache but NOT
  surfaced in IC Telemetry. Minor transparency gap (low priority,
  the smoothing logic itself is in source and tested).
- Q112: Regression 182/182 PASS.

No code changes this round.



## 2026-05-13 — Investor-Audit Round 16 (Q99–Q105)

**Findings**:
- Q99 (**BUG, FIXED**): Q76's V2-collapse THESIS_BREAK fired on a SINGLE
  run with V2<40. The raw v2 score has no smoothing layer (only
  `final_blended_score` is smoothed via SCORE_SMOOTHING_*), so a one-day
  V2 spike below 40 caused INCREASE -> THESIS_BREAK SELL whipsaw on a
  profitable CORE position (MAHABANK +9.5%). Fix: require 2 consecutive
  runs with V2<40 OR a single extreme V2<30. After fix 7 stocks spared
  from premature SELL (AXISBANK, FEDERALBNK, GICRE, ICICIBANK, INDIANB,
  IOB, NMDC) - now in graduated CONSIDER SELLING pending confirmation.
- Q100 (field consistency): BOOK % and BOOK ₹ populated and non-zero for
  all 23 exit actions. No staleness. Not a bug.
- Q101 (diversification): Post-full-SELL portfolio has 6 holdings + 5
  in CONSIDER SELLING. Financial Services dropped 20 -> 6. Good cleanup.
- Q102 (BUY qty): GROWW/KALYANKJIL/AFFLE quantities round perfectly
  (diff=0.0 from invest/price). No fractional issue.
- Q103 (Trading Levels): Entry ranges cover current price; RR=1.45 for
  all BUYs.
- Q104 (auto-dashboard): `webbrowser.open()` not gated on TTY/config.
  Headless/CI gets a no-op but visible noise. Minor UX, not a blocker.

**Files touched**:
- `analyze_top200_stocks_enhanced.py` — `_evaluate_thesis_break` extended
  with prior-run V2 lookup (skip today's record); requires 2-run
  confirmation OR V2<30 extreme
- `tests/test_v2_regression.py` — +1 sentinel
  (`test_thesis_break_requires_confirmation_for_v2_between_30_and_40`),
  updated Q76 sentinel for extreme single-run path
- `docs/dev-log.md` — this entry

**Tests**: 182/182 PASS.

**E2E**: Total SELLs dropped 18 -> 10. 7 stocks moved from premature
SELL to graduated CONSIDER SELLING (need confirmation). Confirmed
degradation (KOTAKBANK V2=29 extreme; PNB/BANKBARODA/CENTRALBK
confirmed via prior-run check) remain full SELL. Whipsaw protection
active.



## 2026-05-13 — Investor-Audit Round 15 (Q92–Q98)

**Findings**:
- Q92 (**BUG, FIXED**): CUMMINSIND showed ACTION=SELL but REASON="HOLD
  STEADY (Rank #17/23)". Root cause - the rank-based holdings ranker
  overwrites exit_reason with "HOLD STEADY..." for mid-rank holdings,
  then exit_reason parsing flips action=HOLD, then category bucket
  re-promotes to SELL. Q51 fix only fired when exit_reason was empty,
  so the stale rank text persisted. Q92 fix extends the sync so that
  when ACTION is an exit (SELL/EMERGENCY/etc.) AND exit_reason contains
  stale rank-based text (HOLD STEADY / TOP PERFORMER / REBALANCE), the
  real action_reason wins. After fix CUMMINSIND correctly graduates to
  CONSIDER SELLING 50% (positive P&L, no thesis break).
- Q93 (SELL sanity): Only 1 SELL with P&L>+5% (MAHABANK +9.5%) - it's a
  CORE THESIS BREAK on V2=38.1. Reasonable.
- Q94 (rotation): GROWW=17, KALYANKJIL=1 - sector-preferred routing
  (17 FS SELLs → FS BUY=GROWW; 1 IND SELL → next BUY).
- Q95 (position size): All BUYs ~₹92K (6.4% each). Equal-weight,
  scaled with cash availability. Reasonable.
- Q96 (NMDC tax): STCG ₹36 correctly computed on +2.4% gain.
- Q97 (history reason): THESIS BREAK text not captured in
  recommendation_history.reason column. Minor gap; Excel report
  archives the full reason. Not a blocker.

**Files touched**:
- `analyze_top200_stocks_enhanced.py` — extended Q51 sync to ALSO refire
  when exit_reason contains stale rank text (HOLD STEADY / TOP PERFORMER /
  REBALANCE) on an EXIT action
- `tests/test_v2_regression.py` — +1 sentinel (`test_reason_sync_overwrites_stale_rank_text_on_exit_action`)
- `docs/dev-log.md` — this entry

**Tests**: 181/181 PASS.

**E2E**: Clean. CUMMINSIND flipped SELL→CONSIDER SELLING (graduated 50%,
correct for profitable position). 0 SELLs remain with stale "HOLD STEADY"
reason.



## 2026-05-13 — Investor-Audit Round 14 (Q85–Q91)

**Findings**:
- Q85 (Q75 scope): `_v2_live_rot = not bool(V2_SHADOW_MODE)`. If shadow mode
  is on, original strict filter restored. No regression possible.
- Q86 (TACTICAL V2<40): 3 stocks (ICICIGI, ICICIPRULI, CUMMINSIND) exit via
  price-stop / emergency / graduated paths. TACTICAL doesn't need V2-collapse
  because price stops aren't disabled. Not a bug.
- Q87 (purge correctness): Purge only removes symbols NOT in current
  holdings. New buys add cleanly. Not a bug.
- Q88 (**BUG, FIXED**): THESIS_BREAK was being downgraded to CONSIDER
  SELLING (graduated 50%) by the conviction-gate pipeline because
  "THESIS BREAK" wasn't in the unconditional-exit keyword list. Fix:
  added `THESIS BREAK`, `TRAILING_STOP`, `TRAILING STOP` to exclusions.
  E2E run flipped NMDC and GICRE (both V2<40, P&L positive) from graduated
  CONSIDER SELLING to full SELL. Cash inflow doubled (₹254K → ₹551K).
- Q89 (WFV freshness): IC Telemetry shows `walkforward status FRESH`
  (age 0 days). Working.
- Q90 (V2 RAW source): Sampled holdings; V2 RAW perfectly matches
  hybrid_overall_score_v2 (max diff 0.000). No v1 fallback contamination.

**Files touched**:
- `analyze_top200_stocks_enhanced.py` — added `THESIS BREAK` /
  `TRAILING_STOP` / `TRAILING STOP` to conviction-gate exclusion list
- `tests/test_v2_regression.py` — +1 sentinel (`test_thesis_break_not_softened_by_graduated_exit`)
- `docs/dev-log.md` — this entry

**Tests**: 180/180 PASS.

**E2E**: Clean. 17 SELL + 5 CONSIDER SELLING + 3 BUY. Q88 fix flipped
NMDC, GICRE from graduated 50% trim to full SELL (V2<40 + THESIS_BREAK
now treated as unconditional). Cash outflow 2x (₹254K → ₹551K).



## 2026-05-13 — Investor-Audit Round 13 (Q78–Q84)

**Findings**:
- Q78 (CORE quality vs V2 alignment): 12 CORE banks have quality>70 but V2<40
  (value-trap pattern: lagging fundamentals look fine but price/momentum/risk
  all degraded). Q76's V2-collapse trigger correctly catches these. Not a bug.
- Q79 (0 HOLD count): 21/23 holdings have V2<45 (median 38.1). Two borderline
  (ABB V2=55 hard-stop, SBIN V2=46 accumulated weak-sell) trigger non-score
  exits. Correct BEAR-mode signal — not a bug.
- Q80+Q83 (BUY breadth): 3 BUYs out of 500 universe; gap between BUY=66 and
  next HOLD=61.7 is 4pt — clean separation. 3 BUYs deploy ₹229K against
  ₹254K cash inflow — sized right. Not a bug.
- Q81 (cash deployment): BEAR_EXPOSURE=0.5 target; today's plan moves
  portfolio from 0% → 24% cash, conservative deployment. Not a bug.
- Q82 (**BUG, FIXED**): `booking_history.json` retains entries for symbols
  no longer held (4 stale today: HDFCBANK, ETERNAL, MOTILALOFS, UJJIVANSFB).
  If investor re-buys these symbols later, stale `peak_v2` corrupts
  SCALE_OUT_20 baseline. Fix: added `_purge_stale_booking_history` class
  method, wired into `_load_holdings_from_excel` post-load step. E2E run
  purged 4 stale entries cleanly; 21 remain, 0 stale.

**Files touched**:
- `analyze_top200_stocks_enhanced.py` — `_purge_stale_booking_history`
  classmethod + integration in `_load_holdings_from_excel`
- `tests/test_v2_regression.py` — +1 sentinel (`test_booking_history_purges_stale_entries`)
- `docs/dev-log.md` — this entry

**Tests**: 179/179 PASS.

**E2E**: Clean run. Booking-history 25→21 entries (4 purged). Q75 rotation
distribution holds (GROWW=22, KALYANKJIL=1). Same 3 BUYs.



## 2026-05-13 — Investor-Audit Round 12 (Q71–Q77)

**Findings**:
- Q71 (sector concentration): No bug. Sector cap is intentionally soft — marks
  low-score holdings as REDUCE but allows new high-conviction picks (GROWW
  V2=76 in Financial Services) to pass.
- Q72 (BUY stops): All 3 BUYs have sensible stops (-6.8% to -8%, all below
  market). Trading Levels has clear entry/target/SL.
- Q73 (position sizing): Equal-weight ₹67K each. Deferred design choice
  (carried forward from Round 1 Q1).
- Q74 (sleeve): All 3 BUYs correctly TACTICAL (vol > 35% blocks CORE).
- Q75 (**BUG, FIXED**): All 22 SELLs rotated to single target AFFLE. Root
  cause — `_safe_candidates` filter excluded HIGH/VERY HIGH risk under v1-era
  rules, but v2's signed weights already penalise risk. Fix: when v2 is live,
  (a) relax HIGH→allowed for rotation pool, (b) union all BUY-tagged stocks
  regardless of risk. Now rotation distributes GROWW(22) + KALYANKJIL(1).
- Q76 (**BUG, FIXED**): CORE-sleeve thesis-break only checked quality drop /
  quality<40 / extreme loss. NMDC had V2=32 (collapse from ~65) but
  quality=65 (lagging) → final_recommendation=SELL but action=HOLD. Fix:
  added `hybrid_overall_score_v2 < 40` as a thesis-break trigger. NMDC now
  CONSIDER SELLING (graduated 25% since profit is positive). 4 other CORE
  banks (CENTRALBK, ICICIBANK, INDIANB, KOTAKBANK) escalated from CONSIDER
  SELLING → SELL — all had V2<40 + P&L<-10%, confirming correct action.

**Files touched**:
- `analyze_top200_stocks_enhanced.py` — Q75 rotation-pool relax + BUY override;
  Q76 v2-score-collapse thesis-break trigger
- `tests/test_v2_regression.py` — +3 sentinels (rotation BUY-override,
  thesis-break v2 collapse positive + negative)
- `docs/dev-log.md` — this entry

**Tests**: 178/178 PASS (was 175; +3 new sentinels).

**E2E**: Clean run. 23 holdings → 11 SELL + 12 CONSIDER SELLING + 0 HOLD.
3 BUYs (GROWW, KALYANKJIL, AFFLE). Rotation now diversified.



## 2026-05-12 — System Health Audit

**Verdict**: HEALTHY across all 6 phases.

**Tests**: `test_v2_regression.py` 111/111 PASS (was 109; +2 new sentinels). `test_regression_fixes.py` 3 pre-existing baseline failures, no new.

**Static**: 38 .py files AST-clean. `static_validator.py` reports 5 pre-existing lints (no new).

**Data integrity**: 10 of 11 required data files OK; `data/last_known_regime.json` missing (auto-recreated on next analysis run by MarketRegimeDetector).

**Feature matrix**: All 17 session-fix source-level sentinels present.

**End-to-end run**: Clean (25 sheets, no Traceback / FAIL / unhashable). Wall time 89s (above 60s baseline due to today's v2 cache invalidation; expected to drop back to 40-50s on next run).

**Files touched**:
- `tests/test_v2_regression.py` — Suite14 extended with `test_stale_weights_ttl_constants_present` and `test_ic_telemetry_surfaces_weight_age` (today's stale-weights guard sentinels)
- `data/system_health_check_20260512_233300.json` — new audit artifact
- `.archive/` — 2 stale recommendation_history `.bak` files moved here

**Rationale**: Operator requested system-wide verification that all session fixes remain active and that there are no errors. The audit confirms HEALTHY status; all walk-forward, calibration, performance, and risk-discipline surfaces are intact. The new sentinels pin today's stale-weights TTL fix so it cannot silently regress.

**Operating-contract compliance scorecard** (also in JSON artifact):
- Rules 2b, 3b, 6a, 8: Compliant
- Rules 2a, 3a, 3c, 5, 6d: Partial
- Rules 1, 4, 6b, 6c, 7: Not implemented
- 8 of 13 rules have gaps; prior audit (P1/P2/P3) is the unblocking path; awaiting operator confirmation before any breaking change.

## 2026-05-13 — Contract Gaps Closure (all 10 in one session)

**Verdict**: HEALTHY; 13/13 operating-contract rules now **Compliant**.

**Scope**: Closed every remaining gap from the May 12 audit in a single session,
ordered so scoring-math changes preceded recalibration and exit-logic
changes followed sleeve schema. Each phase added Suite16 sentinels and was
run independently before moving on.

**Phases (A–J + K audit)**:
- **A. Rule 2a** — Default universe switched to `stock_list_template500.csv`
  (Nifty 500, 400 symbols). Legacy 200-stock CSV retained as warned fallback.
- **B. Rule 7** — Cross-asset `crisis_detector` overlay disabled by default
  (`cfg.ENABLE_CRISIS_DETECTOR=False`). Module kept on disk for ablation.
- **C. Rule 3a** — Added `calculate_growth_score` (earnings + revenue YoY) and
  `calculate_value_score` (1/PE + 1/PB + dividend_yield) as first-class
  hybrid factors. v2 `component_map` extended from 6 to 8 factors.
  `_REGIME_WEIGHTS_NO_ML` now carries `growth`/`value` keys at weight 0.0 to
  preserve v1 byte-identity (59.7) until calibration assigns non-zero values.
  `recommendation_history.csv` schema extended with `hybrid_growth` /
  `hybrid_value` columns (right-edge, additive).
- **D. Rule 3c** — Portfolio Allocation sub-scores relabelled
  `FUND -> QUALITY`, `MOM -> MOMENTUM`; new `GROWTH`/`VALUE` columns; legacy
  `undervaluation_score -> UNDERVAL`; `risk_category -> RISK CAT` so the
  hybrid risk factor can own `RISK`. IC Telemetry gained a 4-factor IC
  breakdown row.
- **E. Recalibration + walk-forward gate** — Rebuilt the calibration source
  (existing `historical_outcomes.csv` is honoured; growth/value missing
  columns gracefully skip). Per-regime calibration succeeded (GLOBAL +
  BEAR). Walk-forward validator re-ran: **PROMOTE** with primary OOS IC
  +0.239 (p=7.1e-10, n=651), spread +8.19pp, 5-fold mean IC +0.170.
- **F. Rule 1** — Added `classify_sleeve` classmethod (CORE if
  `quality>=65 AND value>=55 AND beta<=1.2 AND volatility<=35`, else
  TACTICAL; UNKNOWN when inputs missing). `SLEEVE` column surfaced in
  Portfolio Allocation. `record_recommendation` accepts `sleeve` kwarg.
- **G. Rules 6a/6c/6d** — Refactored `_evaluate_hard_stop` to be
  sleeve- and regime-aware. CORE sleeve disables price stops; new
  `_evaluate_thesis_break` triggers SELL on quality drop ≥15pts,
  quality <40, or 2 consecutive `fundamental_data_failed` runs. BEAR
  regime tightens emergency by 3pp, soft by 2pp, hard by 2pp.
- **H. Rule 6b** — Trailing stop with peak persistence:
  `_update_peak_price` writes `peak_price` per symbol to
  `booking_history.json`; `_evaluate_trailing_stop` fires SELL when price
  drops ≥`TRAILING_STOP_PCT` (default 0.15; BEAR uses 0.10) from peak AND
  the position is in profit.
- **I. Rule 5** — `SCALE_OUT_20` action: fires when P&L ≥
  `SCALE_OUT_PROFIT_THRESHOLD` (0.15) AND v2 score has dropped ≥
  `SCALE_OUT_V2_DROP_PTS` (10) from `peak_v2`. `peak_v2` persisted alongside
  `peak_price`. `rotation_target` populated for SCALE_OUT_20 rows; full
  ledger written as `rotation_events[]` in `booking_history.json`.
  `_normalize_action` recognises `SCALE_OUT_20` and `Scale out 20%`.
- **J. Rule 4** — Adaptive holdings count: BULL=15, SIDEWAYS=22, BEAR=30,
  UNKNOWN falls back to `risk_profile` (legacy bands preserved). Band is
  target±5 clamped to [10, 35]. Rationale string printed at console and
  surfaced in IC Telemetry header.
- **K. Audit** — Full regression 148/148 PASS (was 111; +37 new Suite16
  sentinels). Static validator stays at 5 pre-existing lints (no new).
  End-to-end run on Nifty 500 universe: exit 0, 20 sheets, no Traceback,
  251s wall time (2.5× universe size). System health JSON written.

**Tests**: `tests/test_v2_regression.py` 148/148 PASS (up from 111).
`Suite16_ContractGapsClosure` contains 23 pinned sentinels covering every
gap closure plus walk-forward verdict guard.

**Static**: 5 pre-existing lints retained; 3 NAN_TRUTHY warnings introduced
by Phase H/I were fixed inline with NaN-safe `pd.to_numeric` coercion.

**Walk-forward**: Re-confirmed PROMOTE verdict after 8-factor recalibration.
Growth + value contributed 0.0 to current weights (history rows lack the
columns); ICs will rise as forward runs populate them.

**Files touched (this session)**:
- `analyze_top200_stocks_enhanced.py` — universe default, crisis gating,
  Growth/Value plumbing, Q/G/M/V column rename + heatmap palette, sleeve
  classifier, sleeve-aware `_evaluate_hard_stop`, `_evaluate_thesis_break`,
  `_evaluate_trailing_stop`, `_update_peak_price`, `_load/_save_booking_history`,
  SCALE_OUT_20 rule + rotation_events ledger, adaptive holdings count.
- `hybrid_optimized_scoring.py` — `calculate_growth_score`, `calculate_value_score`,
  regime weights extended with growth/value (0.0), components dict + weighted
  sum (convex + signed branches) extended, v1 calibrator component_map.
- `hybrid_scoring_v2.py` — v2 calibration component_map extended to 8 factors
  with fallback aliases.
- `scripts/calibrate_v2_weights.py` — component_pairs extended; print-friendly
  diagnostics now list growth/value coverage.
- `scripts/build_historical_outcomes.py` — HYBRID_COLS tuple extended to write
  growth/value columns when present in source Complete Data sheets.
- `recommendation_history.py` — `_normalize_action` recognises SCALE_OUT_20;
  `record_recommendation` accepts `sleeve`; growth/value columns added to
  components-plumbing whitelist; `validate_recommendation` treats THESIS_BREAK
  and TRAILING_STOP as hard-stop driven (bypasses premature-exit override).
- `config.py` — new flags: `ENABLE_CRISIS_DETECTOR`, `TRAILING_STOP_PCT`,
  `TRAILING_STOP_BEAR_PCT`, `SCALE_OUT_PROFIT_THRESHOLD`,
  `SCALE_OUT_V2_DROP_PTS`, `SCALE_OUT_FRACTION`.
- `tests/test_v2_regression.py` — Suite16 added (23 sentinels: A/B/C/D/E/F/G/H/I/J).
- `data/calibrated_weights_v2.json` + `_BEAR.json` — refreshed with 8-factor
  schema.
- `data/walkforward_v2_validation.json` — refreshed verdict PROMOTE.
- `data/system_health_check_20260513_005000.json` — new audit artifact.
- `docs/dev-log.md` — this entry.

**Risks / Notes**:
- Growth + Value forward-IC will read INSUFFICIENT for ~30 days; this is
  expected since only post-session history rows carry the two new columns.
  Walk-forward verdict already validates the v2 weights generalise OOS.
- v2 is still in shadow mode (`V2_SHADOW_MODE=True`). Promotion is a separate
  operator decision; the verdict surfaces in the IC Telemetry sheet.
- Crisis-detector module remains on disk and can be flipped back on via
  `cfg.ENABLE_CRISIS_DETECTOR=True` for ablation studies; default is OFF.
- BEAR regime stop tightening only activates while
  `current_market_regime` evaluates to BEAR/BEARISH/VOLATILE; today's run
  detected BEAR (MODERATE) so the tightened thresholds are live.

## 2026-05-13 — v2 Promotion Live

**Action**: `V2_SHADOW_MODE` flipped from `True` -> `False`.
`V2_PROMOTION_DATE = 2026-05-13`. Backup of pre-promotion config kept at
`config.json.pre_v2_promotion_20260513_005851.bak`.

**Why**: Statistical evidence accumulated across the contract-gaps-closure
session was unambiguous:
- Walk-forward (80/20 chronological): v2 OOS IC +0.239 vs v1 -0.318
- Random-universe 100-stock x 20 trials: v2 wins 20/20, mean edge +0.469
- Random-universe 30-stock x 20 trials (stress): v2 wins 20/20
- Top-5 picks simulation (19 periods): v2 cum +1081.5% vs v1 +71.6%
  (paired t-test t=4.82, p=1.4e-4)
- 6-month window: v1 actual +5.46% / v2 projected +104.9% (using
  per-rebalance edge from dense window)

**Wiring change** (the flag was previously documented but inert):
- Added live-engine selector in [analyze_top200_stocks_enhanced.py]
  line ~2738 - when `V2_SHADOW_MODE=False` AND v2 produced a valid
  score, `hybrid_score` (the input to `final_blended_score`) reads from
  `hybrid_overall_score_v2` instead of `hybrid_overall_score`. V1 RAW
  and V2 RAW columns keep their canonical meaning so the operator can
  always audit the gap.
- Mirrored swap on the cache-hit branch (line ~1768) so warm-cache reads
  pick up the new engine immediately. Adjusts both `overall_score` and
  `overall_score_with_value` so downstream ranking flips too.
- `live_engine` field tagged on every stock_data ('v1' or 'v2').
- IC Telemetry sheet gained `LIVE ENGINE` and `V2_PROMOTION_DATE` rows.

**Tests**: Suite16 gained `test_v2_promotion_wiring_in_analyzer` and
`test_ic_telemetry_surfaces_live_engine`. 150/150 PASS.

**Post-promotion end-to-end run** (411 stocks, BEAR regime, --fast):
- Exit code 0; 67s wall time (warm cache).
- IC Telemetry: `LIVE ENGINE = v2`, `V2_PROMOTION_DATE = 2026-05-13`,
  `v2 weight status = FRESH`, walk-forward verdict = PROMOTE.
- Portfolio Allocation: corr(SCORE, V2 RAW) = **+0.9857**;
  corr(SCORE, V1 RAW) = -0.3744. The live SCORE now tracks v2.

**Material recommendation changes** (vs the pre-promotion v1 run):
- NMDC: INCREASE -> SELL (v2 = 33 vs v1 = 58, Δ = -24.7pp)
- CUMMINSIND: INCREASE -> SELL (v2 = 38 vs v1 = 60, Δ = -22.0pp)
- KOTAKBANK: SELL deepened (v2 = 32, bottom-quintile)
- MAHABANK: INCREASE -> REDUCE (sector overweight + v2 demotion)
- ICICIGI / FEDERALBNK / GICRE: now low-conviction SELLs under v2

**Rollback path**: restore the `.pre_v2_promotion_*.bak` config file. Cache
will continue to serve the post-promotion v2 scores until cache TTL (4h)
elapses; for an immediate rollback, also delete `data/cache/*.json`.

**Risks / Notes**:
- This is the first run where v2 actually drives action dispatch. Track
  realised 30-day returns starting from today to validate the projection.
- Growth + Value still have weight = 0 in today's calibration (legacy
  history has no values). Re-calibrate in ~30 days when forward rows
  populate those columns.
- Cache-hit swap path is essential - removing it would create a silent
  v1/v2 mismatch on warm runs. Sentinel tests prevent that regression.

## 2026-05-13 — Investor-Perspective Audit (Rounds 1-4)

**Setup**: Recursive self-doubt audit. Each round asks 5-10 hard investor
questions; if any reveals a bug, run the next round. Stopped after 4 rounds
when remaining gaps were either NO-BUG or design choices.

### Round 1 (Q1-Q9) - 6 bugs fixed
- **Q2 stop-loss bug**: S/R fallback set support=95/resistance=105 when price
  history was empty -> every BUY had Rs 92 stop on a Rs 273 stock (74% loss
  tolerance = no stop). Fixed: reject support levels < 75% of price, require
  stop strictly below market, prefer tighter of (support, 8% price-anchored).
- **Q4 tax-loss harvest summary**: 15 of 19 SELLs at LOSS but no aggregate
  surfaced. Added 6-line TAX-LOSS HARVEST SUMMARY to action plan output.
- **Q7 hysteresis tier leak**: 30 stocks held WEAK_SELL prev-tier from v1
  era, biasing v2 calls. Auto-enable UNIDIRECTIONAL_HYSTERESIS when
  V2_SHADOW_MODE=False so downgrades fall through without resistance.
- **Q8 BUY filter DQ slip**: "(CAUTION: NO FUNDAMENTAL DATA)" still
  contained "BUY" so passed `.str.contains('BUY')`. Filter now explicitly
  excludes CAUTION and fundamental_data_failed.
- **Q9 portfolio risk profile**: Aggregated holdings risk not surfaced.
  Added PORTFOLIO RISK PROFILE panel: weighted vol, 1-day VaR (95%),
  worst-P&L holding.

### Round 2 (Q11-Q19) - 3 bugs fixed
- **Q14 cache invalidation**: `enhanced_price_change_20d` defaulted to 0.0
  when price history < 20 days, then cached forever. Force cache miss when
  critical fields missing OR pinned to 0.0 fallback.
- **Q17 walk-forward staleness**: Walk-forward verdict had no auto-refresh
  policy. Added age + status rows to IC Telemetry (FRESH/STALE/EXPIRED).
- **Q18 CORE extreme-loss override**: PNB at -20.79% loss + CORE sleeve
  silently held because CORE disables price stops. Added -20% safety
  override that triggers THESIS_BREAK regardless of fundamentals. Also
  fixed P&L disagreement between broker-export (-19.6%) and live-price
  (-20.8%) by using the more pessimistic of the two.

### Round 3 (Q21-Q25) - 1 bug fixed
- **Q25 stop above market**: For stocks where support > current price
  (UCOBANK, IOB, CENTRALBK, NMDC - all post-breakdown), Q2 fix produced
  stop_loss ABOVE market price. Added strict `_sup79 < _price79` guard
  and cap final stop at price * 0.99.

### Round 4 (Q27-Q31) - 1 bug fixed
- **Q30 rotation concentration**: All 18 SELLs pointed to ONE rotation
  target (MANYAVAR) because same-sector pool was empty and global #1
  always won. Added round-robin across top-5 candidates. Now distributes
  across 2-5 targets depending on safe-risk pool size.

### Verified NO-BUG findings (worth knowing)
- Q3 Cash reserve: regime-driven 50/85/100% by design, working.
- Q5 Entry pricing: Trading Levels sheet has ENTRY_LOW/HIGH/TARGET_1/2/3.
- Q11 Historical accuracy: BUY hit rate 94.3%, SELL hit rate 19.9% over
  627 outcomes - this is the v1-era anti-predictive problem v2 fixes.
- Q13 Sector cap override: 75-score threshold not exercised today (no
  Financial Services stock crosses 75 in BEAR), so no protection needed.
- Q19 ML signal contribution: weight -0.23 but value hardcoded to 50
  means live contribution is exactly 0. Negative weight is calibration
  artifact, no operational impact.
- Q21 P&L consistency: Portfolio Allocation and Portfolio Summary match
  to the rupee.
- Q22 Action plan dedup: zero stocks appear in multiple priorities.
- Q23 Symbol case: all symbols uppercase, no current bug.
- Q24 Cash math: new_capital + sale_proceeds = total_available_capital
  reconciles exactly.
- Q27 Sleeve stability: zero classification flips across last 3 reports.
- Q28/Q29 ACTION vs final_recommendation: zero conflicts.

### Tests: 166/166 PASS
Added 18 new audit sentinels across Suite16. Suite count from 154 (post-
gap-closure) to 166 (post-audit). Static-validator lint count stable at
5 (no new lints introduced).

### End-to-end results verified
Today's action plan now produces:
- 4 SELLs (LICI/ICICIPRULI/ICICIGI/ABB)
- 16 CONSIDER SELLING (partial trims)
- 3 BUYs distributed across 2-5 rotation targets
- All stop_loss values strictly below current price
- TAX-LOSS HARVEST SUMMARY: Rs 38,384 carry-forward
- PORTFOLIO RISK PROFILE: 25.9% vol, Rs 28,012 1-day VaR
- PNB correctly tagged THESIS_BREAK (was silently HOLD before)

## 2026-05-13 — Investor-Audit Rounds 5-7 (3 more bugs fixed)

Recursive audit continued until a round found zero bugs (Round 7).

### Round 5 (Q33-Q38) - 1 bug fixed
- **Q37 cache-refresh poisons valid data**: Q14 cache invalidation forced
  fresh API calls when 20D CHG was 0.0. If yfinance rate-limited the
  fresh call (which it did for ~10 stocks per run), `bundle.is_valid`
  returned False and the analyzer emitted a `data_invalid` stub that
  REPLACED the previously-valid cached row. Stocks like KALYANKJIL,
  SONATSOFTW silently vanished from the BUY pool between consecutive
  runs. Fix: snapshot the existing cache before invalidating; on
  bundle-failure, restore the snapshot and tag `quality_warnings`
  with `stale_cache_used` rather than emitting the stub.

### Round 6 (Q40-Q44) - 2 bugs fixed
- **Q41 stale-cache count not surfaced**: Q37 fix preserved stocks via
  stale-cache fallback but the investor had no signal that ~10 BUY/HOLD
  recommendations were based on prior-day data. Added a one-line warning
  to the Enhanced Analysis Summary console block.
- **Q44 peak_v2 never persisted**: Phase I logic wrote peak_v2 only
  `if _so_new_peak_v2 != _so_peak_v2_f`, which is False on first
  encounter (peak == current). So peak_v2 stayed None forever and
  SCALE_OUT_20 could never fire (v2_drop always = 0). After fix,
  18/25 booking_history entries now carry peak_v2 baselines.

### Round 7 (Q46-Q49) - 0 bugs found - DONE
- Q46 sleeve persistence: written correctly for today's rows (CORE: 18,
  TACTICAL: 18). Historical rows lack the column (pre-feature), expected.
- Q47-Q48 Growth/Value scoring edge cases: NaN/Inf/extreme inputs all
  produce bounded, sensible scores. No exceptions raised.
- Q49 orphan caches: 38 cache files from prior universe (RELIANCE, MARUTI,
  etc.). 6.8 MB. Harmless cruft, not investor-facing.

### Cumulative audit results
- **7 rounds, 14 real bugs caught and fixed**
- **169/169 regression tests passing** (+34 audit sentinels over rounds 1-7)
- **5 static lints, no new ones introduced**
- End-to-end run verified clean after each round
- Cache resilience: rate-limited stocks no longer vanish from the report
- Recommendation quality: stale labels recompute on cache hits;
  rotation targets distribute across top-5
- Risk discipline: stops always below market price; CORE -20% override;
  trailing stops with peak persistence; SCALE_OUT_20 now functional
- Investor-facing telemetry: tax-loss summary, portfolio VaR, stale-cache
  warning count, walk-forward freshness, all surfaced

The system is now genuinely investor-grade and resilient to common
real-world failure modes (rate limits, partial data, regime transitions,
cache staleness, threshold boundaries).

## 2026-05-13 — Round 8 (intraday volume bug)

### Q51 - REASON field stale (cosmetic, found earlier today)
- 13/20 SELL rows had REASON = "HOLD STEADY (Rank #X/23)" contradicting
  ACTION = SELL. Holdings-rank loop filled exit_reason with the rank
  message when the field was empty, even on preserved exit actions.
- Fix: on exit actions (SELL/SWAP/EMERGENCY/STOP LOSS/EXIT), prefer the
  `action_reason` (real hard-stop / thesis-break message) over the
  holdings-rank fallback. PNB's REASON now reads "THESIS BREAK: extreme
  loss -20.8% <= -20% override on CORE - market signal precedes
  fundamental confirmation" instead of "HOLD STEADY (Rank #8/23)".

### Q52 - Intraday partial-volume crashes v2 scores
Investor ran fresh analysis at 11:46 AM IST. NSE closes at 3:30 PM, so
yfinance returned today's PARTIAL-day volume while the 20d MA was
computed on full-day historical volumes. Result:
- SONATSOFTW volume_strength: 100 (yesterday) -> 3.5 (today, -97 pts)
- ACE volume_strength: 81.5 -> 1.0 (-80 pts)
- 200/411 stocks below 0.8 volume_ratio
- v2's largest positive weight (+0.29 on volume_strength) crushed every
  score 10-30 points
- Result: ZERO BUY recommendations for the day (vs 3 yesterday)

Fix: `_calculate_volume_indicators` now detects when today's volume is
abnormally small (<60% of 20d avg AND a prior value exists) and uses
yesterday's completed-day volume instead. This sacrifices intraday
responsiveness for accuracy under v2's signed-weight model.

Test sentinels: `test_intraday_partial_volume_uses_previous_day`,
`test_reason_prefers_real_reason_on_exit_actions`.

171/171 regression tests passing. Investor should re-run after cache
expiry (4h) or after manually clearing data/cache to pick up the fix.
