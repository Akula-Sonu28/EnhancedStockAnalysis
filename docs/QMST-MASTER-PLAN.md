# QMST Master Plan — Full In-System Implementation

> **QMST** = Quality-Momentum Swing Turbo (not OMST, not U7).  
> Council: **5× ACK** on this plan. Badge until proof: **QMST-BETA**.

**Companion:** [qmst-implementation-plan.md](./qmst-implementation-plan.md) (task IDs, tests, gates).

---

## 1. What “fully inside the system” means

QMST is **wired end-to-end** when:

1. **Config** locks pick / entry / exit drivers (no accidental SCORE-as-pick).
2. **Pipeline** runs layers in order with tests enforcing priority.
3. **Reports** show Pick rank, Turbo, SCORE (audit) — REASON never mislabels.
4. **History** stores `picking_rank` + `fq_score` + `turbo_score` for forward IC.
5. **Validation** script + Dashboard badge track path to **QMST-VALIDATED**.

No new composite score. Stage 1 unchanged. v1 engine untouched.

---

## 2. Gap analysis (today)

| Component | Status | Location |
|-----------|--------|----------|
| Stage 1 seven marks | ✅ Done | `hybrid_optimized_scoring.py` |
| Flow-quality pick (`fq_score`) | ✅ Done | `src/flow_quality_oracle.py` |
| Turbo entry + confirm | ✅ Done | `src/turbo_entry.py` |
| VMQ P&L exits | ✅ Done | `src/vmq_strategy.py` |
| Oracle stack enrich | ✅ Done | `picking_metrics.enrich_results_df_oracle_stack()` |
| Holdings rank → `picking_rank` | ✅ Done | `ORACLE_STACK_ALIGN=true` |
| Rank-SELL disabled | ✅ Done | `ORACLE_DISABLE_RANK_SELL_ALL` |
| Turbo gate on **NEW** only | ✅ Done | `apply_vmq_to_allocation_df()` |
| Turbo gate on **INCREASE** | ❌ TODO | Phase 2 |
| REASON `Pick rank:` not `Score:` | ❌ TODO | Phase 1 |
| Central quality-floor helper | ⚠️ Partial | rules scattered turbo/VMQ |
| `picking_rank` in history CSV | ❌ TODO | Phase 3 |
| `qmst_validation_gate.py` | ❌ TODO | Phase 3 |
| Dashboard QMST badge | ❌ TODO | Phase 3 |
| `docs/strategy-qmst.md` | ❌ TODO | Phase 0 |
| `test_qmst_layer_priority.py` | ❌ TODO | Phase 1–2 |
| `src/qmst_gates.py` (optional) | ❌ Optional | Phase 2b |

**~70% built.** Remaining work is **contracts, INCREASE parity, telemetry, proof**.

---

## 3. Locked config contract (add to `config.json`)

After implementation, these must be set (do not drift without council review):

```json
{
  "QMST_ENABLED": true,
  "QMST_STATUS_BADGE": "QMST-BETA",
  "PICKING_RANK_DRIVER": "flow_quality",
  "ENTRY_DRIVER": "turbo_mtf",
  "ORACLE_STACK_ALIGN": true,
  "ORACLE_DISABLE_RANK_SELL_ALL": true,
  "ORACLE_PAUSE_NEW_IN_BEAR": true,
  "ORACLE_WATCHLIST_PCT": 0.20,
  "ORACLE_ENTRY_LIVE": true,
  "VMQ_ENABLED": true,
  "V2_SHADOW_MODE": true,
  "TURBO_ENTRY_VS_MIN": 0
}
```

| Key | Role |
|-----|------|
| `QMST_ENABLED` | Master switch; when true, enforce layer labels + history fields |
| `PICKING_RANK_DRIVER` | Layer 2 = `flow_quality` only |
| `ENTRY_DRIVER` | Layer 3 = `turbo_mtf` |
| `V2_SHADOW_MODE` | Keep v1/v2 SCORE audit-only (do not use for pick) |
| `TURBO_ENTRY_VS_MIN` | 0 = off; 30 = thin-volume block on NEW/INCREASE (Phase 4) |

Add `QMST_ENABLED`, `QMST_STATUS_BADGE`, `TURBO_ENTRY_VS_MIN` to `config.py` with validation.

---

## 4. Target pipeline (after full implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│ analyze_top200_stocks_enhanced.py                               │
├─────────────────────────────────────────────────────────────────┤
│ 1. Universe filter                                              │
│ 2. Stage 1 → hybrid_* (7 marks)                                 │
│ 3. enrich_results_df_oracle_stack()                             │
│      fq_score, picking_rank, turbo_score, on_oracle_watchlist  │
│ 4. Portfolio allocation                                       │
│      holdings rank = picking_rank (not SCORE)                  │
│      30/50/20 → INCREASE / HOLD / trim candidates               │
│      NEW from watchlist + deploy cash                           │
│ 5. apply_vmq_to_allocation_df()  [FINAL AUTHORITY]              │
│      turbo gate: NEW + INCREASE (invest > 0)                    │
│      VMQ exit: holdings P&L                                     │
│ 6. format REASON with Pick rank / Turbo / VMQ layer             │
│ 7. Excel + record_recommendation (picking_rank, fq, turbo)      │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
  evaluate_stock_picking.py  +  qmst_validation_gate.py
```

**Priority (enforced in tests):** `VMQ > Turbo > Pick rank > SCORE audit`

---

## 5. Workstreams (curated backlog)

### WS-A — Governance & docs (Phase 0) · ~4h · **non-breaking**

| ID | Task | Output |
|----|------|--------|
| A1 | Write `docs/strategy-qmst.md` | Charter + 3 examples + weekly playbook |
| A2 | Link in `AGENTS.md` | “Operational strategy = QMST” |
| A3 | Append this master plan link to `stock-analysis-system` skill | 1 paragraph |
| A4 | Post-analysis audit: check QMST columns present | skill patch |
| A5 | `docs/dev-log.md` entry | Phase 0 complete |

**Done when:** engineer reads docs only → explains AIAENG / ACUTAAS / NATCOPHARM.

---

### WS-B — Report & label contract (Phase 1) · ~8h · **non-breaking**

| ID | Task | File |
|----|------|------|
| B1 | `format_holdings_reason(rank, total, pick_rank, oracle_aligned)` | `src/picking_metrics.py` |
| B2 | Replace holdings `Score:` → `Pick rank:` when oracle aligned | `analyze_top200_stocks_enhanced.py` |
| B3 | Console prints: `Pick rank` vs `SCORE (audit)` | same |
| B4 | Excel Complete Data: export oracle columns | export path in analyzer |
| B5 | Portfolio Allocation footer note | export |
| B6 | Dashboard subtitle: strategy badge | export |
| B7 | Tests for formatter | `tests/test_picking_metrics.py` |

**Done when:** dry-run ACUTAAS REASON shows `Pick rank: -32.8`, not `Score:`.

---

### WS-C — Layer integrity (Phase 2) · ~12h · **BREAKING**

| ID | Task | File |
|----|------|------|
| C1 | Detect `INCREASE` + `investment_amount > 0` as entry-add | `src/vmq_strategy.py` |
| C2 | Run `evaluate_turbo_entry_gate` on entry-add | same |
| C3 | Fail INCREASE → **HOLD**, invest=0, reason prefixed | same |
| C4 | Stat `increase_blocked` in VMQ stats + analyzer log | analyzer |
| C5 | Add `TURBO_ENTRY_VS_MIN` (default 0) | `config.py`, `config.json` |
| C6 | VS floor in turbo gate when config > 0 | `src/turbo_entry.py` |
| C7 | **Optional:** `src/qmst_gates.py` — `evaluate_quality_floor()` centralize FQ/RK/dead-trend/value-trap | new |
| C8 | Call quality floor from turbo gate (single source) | `turbo_entry.py` |

**Done when:** ENRIN INCREASE blocked on RSI hard block; NATCOPHARM VMQ SELL unchanged.

**User must confirm** before merge (fewer INCREASEs).

---

### WS-D — Tests & regression (Phase 1–2) · ~6h

| ID | Test | Asserts |
|----|------|---------|
| D1 | `test_vmq_overrides_hold_on_hard_stop` | P&L −12% → SELL |
| D2 | `test_turbo_blocks_new` | low turbo → WATCHLIST |
| D3 | `test_turbo_blocks_increase_to_hold` | RSI block → HOLD, invest 0 |
| D4 | `test_rank_sell_disabled_profitable` | rank bottom + P&L +3% → not rank-SELL |
| D5 | `test_format_holdings_reason_pick_rank_label` | string contract |

File: **`tests/test_qmst_layer_priority.py`** (new).

**Gate command:**

```bash
python3 tests/test_qmst_layer_priority.py
python3 tests/test_v2_regression.py
python3 tests/test_picking_metrics.py
python3 tests/test_flow_quality_oracle.py
python3 tests/test_turbo_entry.py
python3 tests/test_vmq_strategy.py
```

---

### WS-E — Telemetry & validation (Phase 3) · ~10h + 8 weeks runtime

| ID | Task | File |
|----|------|------|
| E1 | Persist `picking_rank` on `record_recommendation` | `recommendation_history.py` + analyzer |
| E2 | History `score` = `resolve_validation_score()` when oracle aligned | analyzer |
| E3 | `scripts/qmst_validation_gate.py` — read trends + walkforward + backtest JSON | new |
| E4 | Emit `data/qmst_validation_status.json` | new |
| E5 | `evaluate_stock_picking.py` — QMST section + badge | script |
| E6 | Dashboard reads badge from config or validation JSON | analyzer export |
| E7 | Weekly operator section in `strategy-qmst.md` | doc |

**Validation gates (60 consecutive days):**

| Gate | Threshold |
|------|-----------|
| Forward `picking_rank` IC (30d) | ≥ 0.05 |
| Q5−Q1 spread | ≥ +3 pp |
| Walk-forward OOS IC | ≥ 0.05 |
| Backtest excess vs benchmark | > 0 |
| Backtest Sharpe | > 0.15 |

**Done when:** badge flips to **QMST-VALIDATED** via `qmst_validation_gate.py`.

---

### WS-F — Optional tune (Phase 4) · only if Phase 3 fails

One knob at a time + walk-forward + regression. See implementation plan §8.

---

## 6. PR sequence (recommended)

| PR | Workstreams | Risk |
|----|-------------|------|
| **PR1** | WS-A | None |
| **PR2** | WS-B + D5 | Low |
| **PR3** | WS-C + WS-D | **Medium** — INCREASE behavior |
| **PR4** | WS-E | Low |

Do **not** merge PR3 with config weight changes.

---

## 7. Implementation checklist (copy to track)

### Milestone M1 — Operational QMST (Week 1)

- [ ] A1–A5 docs complete
- [ ] B1–B7 labels complete
- [ ] C1–C4 INCREASE turbo gate
- [ ] D1–D5 tests green
- [ ] Full regression green
- [ ] Dry-run: no `Score:` for pick rank in holdings REASON
- [ ] `config.json` QMST block applied
- [ ] Dev-log entry
- [ ] Badge: **QMST-BETA**

### Milestone M2 — Instrumented QMST (Week 2)

- [ ] E1–E2 history columns live
- [ ] E3–E4 validation script runs
- [ ] E5–E6 report badge
- [ ] First `evaluate_stock_picking.py` with non-null picking_rank IC path

### Milestone M3 — Validated QMST (Week 8+)

- [ ] 60-day gates pass
- [ ] Council re-ACK
- [ ] Badge: **QMST-VALIDATED**

---

## 8. Weekly operator playbook (post M1)

| Step | Command / action |
|------|------------------|
| 1 Preview | `python3 analyze_top200_stocks_enhanced.py --dry-run --fast` |
| 2 Audit | Type **ANALYSE** |
| 3 Live | One `python3 analyze_top200_stocks_enhanced.py` / week |
| 4 Audit live | **ANALYSE** again |
| 5 Metrics | `python3 scripts/evaluate_stock_picking.py` |
| 6 Gates | `python3 scripts/qmst_validation_gate.py` |
| 7 Execute | SELL (VMQ) → INCREASE/NEW (turbo PASS) → HOLD |

---

## 9. What we explicitly do not build

- U7 / council composite score
- v1 `hybrid_optimized_scoring.py` changes
- Using `final_blended_score` as pick driver
- Rank-SELL on profitable holdings
- Phase 4 tweaks before Phase 3 failure

---

## 10. Success metrics

| Metric | M1 target | M3 target |
|--------|-----------|-----------|
| Layer test suite | 5/5 pass | 5/5 pass |
| REASON label errors | 0 on dry-run | 0 |
| INCREASE without turbo PASS | 0 after P2 | 0 |
| Forward pick IC | measurable | ≥ 0.05 |
| False SELL from rank | 0 | 0 |

---

## 11. Start implementation

Tell the agent:

| Command | Scope |
|---------|--------|
| `implement QMST Phase 0-2` | WS-A + WS-B + WS-C + WS-D (M1) |
| `implement QMST Phase 0-3` | M1 + M2 (full code, start validation clock) |
| `implement QMST PR1 only` | Docs first |

**Confirm INCREASE turbo gate** before PR3.

---

*Council sign-off on plan: ARCH ✅ QUANT ✅ RISK ✅ AUDIT ✅ SKEPTIC ✅*
