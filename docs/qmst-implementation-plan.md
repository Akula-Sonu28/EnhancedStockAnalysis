# QMST Strategy — Complete Implementation Plan

**Status:** APPROVED by Five-Agent Council (5× ACK on plan)  
**Strategy badge:** `QMST-BETA` until Phase 3 validation gates pass  
**Owner workflow:** Weekly analyze → ANALYSE → one live run  
**Last updated:** 2026-05-30

**Curated master plan (start here):** [QMST-MASTER-PLAN.md](./QMST-MASTER-PLAN.md)

---

## 1. Executive summary

**QMST** (Quality-Momentum Swing Turbo) is not a new scoring engine. It is the **operating doctrine** for the oracle stack already in the repo:

| Layer | Driver | Module |
|-------|--------|--------|
| 0 | Universe filter | `src/universe_filter` |
| 1 | Quality floor | scattered gates in turbo/VMQ |
| 2 | Pick rank | `src/flow_quality_oracle.py` (`fq_score`, top 20%) |
| 3 | Entry timing | `src/turbo_entry.py` (`turbo_score`, confirm) |
| 4 | Exits | `src/vmq_strategy.py` (P&L stops) |

**Priority:** `VMQ exit > Turbo block > Pick rank > Audit SCORE (v1/v2)`

This plan implements council conditions Phases 0–3 (+ optional Phase 4). No U7 composite. No v1 SCORE as pick driver.

---

## 2. Scope

### In scope

- Strategy charter doc + AGENTS pointer
- REASON / Excel label contract (`Pick rank` vs `SCORE`)
- Turbo gate on **NEW POSITION and INCREASE**
- Layer-priority regression tests
- History telemetry for forward IC (`picking_rank`, `fq_score`, `turbo_score`)
- Validation gate automation + status badge in reports
- Dev-log entry per phase

### Out of scope

- New composite score (U7-style)
- v1 engine changes (`hybrid_optimized_scoring.py`)
- v2 weight recalibration (unless Phase 4 triggered)
- `TURBO_ENTRY_VS_MIN` default ON (optional config, default OFF)

---

## 3. Architecture (unchanged modules)

```
Stage 1 (7 marks)     hybrid_optimized_scoring.py → stock_data hybrid_*
        ↓
Oracle enrich         picking_metrics.enrich_results_df_oracle_stack()
        ↓                  flow_quality_oracle + turbo_entry
Allocation            analyze_top200_stocks_enhanced.py
        ↓                  holdings rank, 30/50/20, sizing
VMQ seal              vmq_strategy.apply_vmq_to_allocation_df()
        ↓
History + Excel       recommendation_history + report export
```

---

## 4. Phase 0 — Strategy charter (Day 1)

**Goal:** ARCH ACK — documented layer map matches code.

### Tasks

| ID | Task | File(s) |
|----|------|---------|
| P0-1 | Write strategy charter (layers, marks map, examples, weekly playbook) | `docs/strategy-qmst.md` |
| P0-2 | Link from agent instructions | `AGENTS.md` |
| P0-3 | Add post-analysis audit check hint for QMST columns | `.cursor/skills/post-analysis-audit/SKILL.md` (1 paragraph) |

### `docs/strategy-qmst.md` required sections

1. Stage-1 seven marks (50 = neutral)
2. Layer 0–4 table + priority rule
3. Which marks feed which layer
4. Happy paths: AIAENG (NEW), ACUTAAS (HOLD), NATCOPHARM (VMQ SELL)
5. Weekly workflow (dry-run / live / ANALYSE)
6. Non-goals (U7, v1 SCORE decisions)
7. Status badges: QMST-BETA / QMST-VALIDATED / QMST-DEMOTE

### Acceptance criteria

- [ ] New engineer can explain BUY/HOLD/SELL without reading `analyze_top200` line-by-line
- [ ] Council ARCH signs off on doc accuracy vs `oracle_weights.json` weights

### Tests

None (docs only).

---

## 5. Phase 1 — Report contract (Days 2–3)

**Goal:** AUDIT ACK — no more “Score” confusion for pick rank.

### Tasks

| ID | Task | File(s) |
|----|------|---------|
| P1-1 | Holdings REASON: `Score:` → `Pick rank:` when `oracle_stack_align` | `analyze_top200_stocks_enhanced.py` (~8260–8346, ~8680, ~9065+) |
| P1-2 | Console / action-plan prints: distinguish `Pick rank` vs `SCORE (audit)` | same file (~8174, ~9960, ~10035) |
| P1-3 | Excel Complete Data: ensure columns exported | `fq_score`, `picking_rank`, `turbo_score`, `entry_confirm_ret`, `on_oracle_watchlist` |
| P1-4 | Portfolio Allocation sheet: footer note | “SCORE = audit only; Pick rank = flow-quality; Turbo = entry” |
| P1-5 | Helper to format holdings reason string | `src/picking_metrics.py` → `format_holdings_reason(rank, total, pick_rank)` |

### Label rules (contract)

| Column / text | Meaning |
|---------------|---------|
| `picking_rank` / `fq_score` | Layer 2 flow-quality (can be negative) |
| `turbo_score` | Layer 3 entry strength |
| `SCORE` / `final_blended_score` | Audit only — never in REASON as decision driver |
| REASON text | Must say **Pick rank: X** not **Score: X** when oracle aligned |

### Acceptance criteria

- [ ] ACUTAAS-style REASON reads `Pick rank: -10.5` not `Score: -10.5`
- [ ] Suite 1 history schema unchanged (no column renames)
- [ ] Excel still has Dashboard, Portfolio Allocation, Complete Data, Top Picks

### Tests

| Test | File |
|------|------|
| Reason formatter uses Pick rank | `tests/test_picking_metrics.py` |
| Oracle aligned label | `tests/test_qmst_layer_priority.py` (new, partial) |

---

## 6. Phase 2 — Layer integrity (Days 4–6) **BREAKING**

**Goal:** RISK ACK — INCREASE obeys same turbo gates as NEW.

**User confirmation required before merge.**

### Tasks

| ID | Task | File(s) |
|----|------|---------|
| P2-1 | Extend entry gate to INCREASE with `investment_amount > 0` | `src/vmq_strategy.py` |
| P2-2 | On turbo fail for INCREASE → downgrade to **HOLD** (keep position, zero invest) | same |
| P2-3 | Append block reason: `TURBO BLOCK (INCREASE): …` | same |
| P2-4 | Optional VS floor (default OFF) | `config.py` + `config.json`: `TURBO_ENTRY_VS_MIN = 0` (0 = disabled) |
| P2-5 | Wire VS floor in `evaluate_turbo_entry_gate` when > 0 | `src/turbo_entry.py` |
| P2-6 | Stats counter `increase_blocked` in VMQ stats log | `vmq_strategy.py`, analyzer print |

### Pseudocode (P2-1)

```python
is_entry_add = (
    ('NEW POSITION' in act or 'INCREASE' in act)
    and investment_amount > 0
)
if is_entry_add:
    result = evaluate_turbo_entry_gate(...)
    if not result.allowed and 'INCREASE' in act:
        action = 'HOLD'  # not WATCHLIST (already owned)
        investment_amount = 0
```

### Acceptance criteria

- [ ] ENRIN-class case: INCREASE blocked when RSI > hard block
- [ ] AIAENG-class NEW still PASS when turbo PASS
- [ ] VMQ hard stop still overrides HOLD (NATCOPHARM)
- [ ] `ORACLE_DISABLE_RANK_SELL_ALL` still prevents rank-only SELL

### Tests

| Test | File |
|------|------|
| VMQ overrides rank HOLD | `tests/test_qmst_layer_priority.py` |
| Turbo blocks NEW | `tests/test_qmst_layer_priority.py` |
| Turbo blocks INCREASE → HOLD | `tests/test_qmst_layer_priority.py` |
| Extend | `tests/test_vmq_strategy.py` |
| Extend | `tests/test_turbo_entry.py` |

### Regression

```bash
python3 tests/test_v2_regression.py
python3 tests/test_picking_metrics.py
python3 tests/test_flow_quality_oracle.py
python3 tests/test_turbo_entry.py
python3 tests/test_vmq_strategy.py
python3 tests/test_qmst_layer_priority.py
```

---

## 7. Phase 3 — Proof gates (Weeks 2–8, ongoing)

**Goal:** QUANT + SKEPTIC ACK — forward evidence for `picking_rank`.

### Tasks

| ID | Task | File(s) |
|----|------|---------|
| P3-1 | Persist `picking_rank` on history write | `recommendation_history.py` + call site in analyzer |
| P3-2 | Use `resolve_validation_score()` for history `score` field when oracle aligned | `picking_metrics.py`, analyzer |
| P3-3 | Add QMST status to eval report | `scripts/evaluate_stock_picking.py` |
| P3-4 | Gate checker script | `scripts/qmst_validation_gate.py` (new) |
| P3-5 | Report badge in Excel Dashboard | `analyze_top200_stocks_enhanced.py` export |
| P3-6 | Weekly cron doc (manual) | `docs/strategy-qmst.md` § Validation |

### Validation gates (all must pass **60 consecutive days**)

| Gate | Threshold | Source |
|------|-----------|--------|
| Forward `picking_rank` IC (30d) | ≥ 0.05 | `data/stock_picking_trends.md` |
| Q5−Q1 spread | ≥ +3 pp | same |
| Walk-forward OOS IC | ≥ 0.05 | `data/walkforward_v2_validation.json` |
| Backtest stack excess return | > 0 vs benchmark | `data/turbo_mtf_cadence_comparison_live.json` |
| Backtest Sharpe | > 0.15 | same (`live_regime_threshold_weekly__prod_5d`) |

### Status badges

| Badge | Condition |
|-------|-----------|
| `QMST-BETA` | Default until gates pass |
| `QMST-VALIDATED` | All gates pass 60 days |
| `QMST-DEMOTE` | fq IC < 0 for 60 days → review Phase 4 |

### Weekly operator commands

```bash
python3 analyze_top200_stocks_enhanced.py --dry-run --fast   # preview
# ANALYSE
python3 analyze_top200_stocks_enhanced.py                    # one live/week
python3 scripts/evaluate_stock_picking.py
python3 scripts/qmst_validation_gate.py
python3 tests/test_v2_regression.py
```

### Acceptance criteria

- [ ] `picking_rank` IC no longer null in `stock_picking_trends.md` after 30d of live rows
- [ ] Dashboard shows `QMST-BETA` or `QMST-VALIDATED`
- [ ] Council QUANT + SKEPTIC re-run COUNCIL ACK when VALIDATED

---

## 8. Phase 4 — Optional tune (only if Phase 3 fails)

**Trigger:** `picking_rank` IC < 0 for 60 days after Phase 2 live.

**Rule:** One change at a time + walk-forward + regression.

| Tweak | Config key | Default |
|-------|------------|---------|
| Stronger anti-chase | `FQ_LAMBDA_HIGH` | 0.8 → 0.9 |
| Tighter watchlist | `ORACLE_WATCHLIST_PCT` | 0.20 → 0.15 |
| Thin volume block (NEW only) | `TURBO_ENTRY_VS_MIN` | 0 → 30 |
| Pause NEW on walk-forward HOLD | `ORACLE_PAUSE_NEW_ON_HOLD_SHADOW` | review only |

No new composite. No U7 revival.

---

## 9. File touch list (summary)

| File | Phases |
|------|--------|
| `docs/strategy-qmst.md` | P0 (new) |
| `docs/qmst-implementation-plan.md` | this doc |
| `AGENTS.md` | P0 |
| `analyze_top200_stocks_enhanced.py` | P1, P3 |
| `src/vmq_strategy.py` | P2 |
| `src/turbo_entry.py` | P2 (optional VS) |
| `src/picking_metrics.py` | P1, P3 |
| `recommendation_history.py` | P3 |
| `config.py` / `config.json` | P2 (optional) |
| `scripts/evaluate_stock_picking.py` | P3 |
| `scripts/qmst_validation_gate.py` | P3 (new) |
| `tests/test_qmst_layer_priority.py` | P1, P2 (new) |
| `tests/test_picking_metrics.py` | P1 |
| `tests/test_vmq_strategy.py` | P2 |
| `docs/dev-log.md` | each phase |

---

## 10. Timeline

| Week | Deliverable | Phase |
|------|-------------|-------|
| 1 | Strategy doc + REASON labels + layer tests | P0, P1 |
| 1 | INCREASE turbo gate + regression | P2 |
| 2 | History `picking_rank` + validation script | P3 start |
| 2–8 | Weekly eval; no weight changes | P3 run |
| 8 | Council re-ACK; badge → VALIDATED or Phase 4 | P3 end |

---

## 11. Risk register

| Risk | Mitigation |
|------|------------|
| Fewer INCREASEs after P2 | Intended; ENRIN RSI case fixed |
| Operators ignore SCORE column | P1 labels + Excel footer |
| Forward IC still null | P3-1 history write |
| Backtest overfit | Label as stack test; walk-forward separate |
| Phase 2 without user OK | Gate: explicit confirm before merge |

---

## 12. Definition of done

### Phase 0–2 complete (operational QMST)

- [ ] All P0–P2 acceptance criteria met
- [ ] Full regression suite green
- [ ] Dry-run on `190422`-class holdings: no REASON `Score:` for pick rank
- [ ] Dev-log entry dated
- [ ] Badge: **QMST-BETA**

### Phase 3 complete (validated QMST)

- [ ] 60-day gate pass via `qmst_validation_gate.py`
- [ ] Council 5× ACK on validation
- [ ] Badge: **QMST-VALIDATED**

---

## 13. Implementation order (single PR sequence)

Recommended PRs (small, reviewable):

1. **PR1 — Docs:** P0 only  
2. **PR2 — Labels:** P1 + reason helper + tests  
3. **PR3 — INCREASE gate:** P2 + `test_qmst_layer_priority.py`  
4. **PR4 — Telemetry:** P3 history + eval + gate script + dashboard badge  

Do not combine PR3 with weight/threshold changes.

---

## 14. Council sign-off (plan)

| Agent | Plan ACK |
|-------|----------|
| ARCH | ✅ |
| QUANT | ✅ |
| RISK | ✅ |
| AUDIT | ✅ |
| SKEPTIC | ✅ |

**Next action:** User says `implement Phase 0-2` or `implement all phases`.
