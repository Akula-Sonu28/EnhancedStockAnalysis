# QMST — Quality-Momentum Swing Turbo

**Operational strategy for this repo.** Not a new scoring engine — a layer doctrine over the oracle stack.

**Status badges:** `QMST-BETA` (default) → `QMST-VALIDATED` (60-day gates pass) → `QMST-DEMOTE` (review if pick IC &lt; 0 for 60 days).

**Master plan:** [QMST-MASTER-PLAN.md](./QMST-MASTER-PLAN.md)

---

## Layer priority (enforced)

```
VMQ P&L exit  >  Turbo entry block  >  Pick rank (fq_score)  >  SCORE audit (v1/v2)
```

When layers conflict, the higher layer wins. Example: NATCOPHARM can have good FQ/VL but VMQ hard stop still → **SELL**.

---

## Stage 1 — seven marks (unchanged)

All marks are 50 = neutral. Produced by `hybrid_optimized_scoring.py`:

| Mark | Column | Role in QMST |
|------|--------|--------------|
| FQ | `hybrid_fundamental_quality` | Quality floor, value-trap detection |
| MT | `hybrid_momentum_technical` | Momentum floor, fq penalty (λ×MT) |
| VS | `hybrid_volume_strength` | **Pick rank** primary input |
| MTF | `hybrid_multi_timeframe` | Turbo entry floor |
| RK | `hybrid_risk_adjustment` | Risk context |
| GR | `hybrid_growth` | Turbo weights (τ_entry) |
| VL | `hybrid_value` | Value-trap guard |

---

## Layers 0–4

| Layer | Driver | Module | Config |
|-------|--------|--------|--------|
| 0 | Universe | `src/universe_filter` | mandatory |
| 1 | Quality floor | turbo + VMQ gates | scattered |
| 2 | **Pick** | `src/flow_quality_oracle.py` | `PICKING_RANK_DRIVER=flow_quality` |
| 3 | **Entry** | `src/turbo_entry.py` | `ENTRY_DRIVER=turbo_mtf` |
| 4 | **Exit** | `src/vmq_strategy.py` | `VMQ_ENABLED=true` |

**Pick rank:** `fq_score = VS − λ×MT` (regime-adaptive λ). Top 20% → oracle watchlist (`ORACLE_WATCHLIST_PCT`).

**Entry:** `turbo_score` from `data/oracle_weights.json` τ_entry weights + MTF/mom floors + short confirm + RSI guards. Applies to **NEW POSITION** and **INCREASE** (invest &gt; 0).

**Exit:** VMQ swing (−5%), hard (−8%), optional day-3/5 validation (off by default), trail. Rank-SELL disabled when `ORACLE_DISABLE_RANK_SELL_ALL=true`.

**Production default — day-3/5 OFF:** `VMQ_DAY3_ENABLED=false`. Hard/swing/trail still apply. Backtest: 12m +4.9% vs Nifty, 28 trades, ₹0 STCG. Use `python3 -m backtest.runner qmst --day3` only for experiments.

**Pick gates (FQ/RK floors):** `QMST_PICK_GATES_ENABLED=false` by default. Thresholds: FQ ≥ 48, RK ≥ 42 (VL ≥ 45 optional via `QMST_PICK_VL_GATE`). Backtest before enabling: `python3 scripts/backtest_qmst_pick_gates.py`. Promoter pledge not in historical data yet.

**Validation badge:** `python3 scripts/qmst_validation_gate.py` — production profile uses Sharpe floor **−0.10** (satellite, low trade count); excess return remains primary.

**Day-3/5 experiments (when `VMQ_DAY3_ENABLED=true`):** When `VMQ_DAY3_REGIME_GATED=true`, early validation runs only in **BEAR** or when VIX ≥ `VMQ_DAY3_VIX_MIN` (default 25). **BULL** and **SIDEWAYS** skip day-3/5; hard/swing/trail still apply.

**Day-3/5 smart skip:** When `VMQ_DAY3_SMART_SKIP=true`, skip early validation if P&L &gt; `VMQ_DAY3_SKIP_PNL_MIN` (5%), `turbo_score` ≥ `VMQ_TURBO_MIN`, or `hybrid_multi_timeframe` ≥ `VMQ_DAY3_SKIP_MTF_MIN` (52). Hard/swing/trail always apply.

**SCORE audit:** `final_blended_score` / v2 shadow — logged and exported, **never** the pick driver when `ORACLE_STACK_ALIGN=true`.

---

## Example paths (run 190422)

### AIAENG — NEW (happy entry)

- On oracle watchlist, turbo ~83.9 **PASS**, confirm +12.7%
- Action: **NEW POSITION** after turbo gate
- REASON shows Turbo PASS + pick context

### ACUTAAS — HOLD (happy hold)

- P&L +5.04%, turbo PASS, fq −32.8, holdings rank #7/19
- Middle 50% → **HOLD** without high fq
- REASON: `Pick rank: -32.8` (not `Score:`)

### NATCOPHARM — SELL (VMQ override)

- VMQ hard stop −12.6% overrides good FQ/VL
- Action: **SELL** — P&L layer wins

---

## Weekly operator playbook

| Step | Action |
|------|--------|
| 1 | `python3 analyze_top200_stocks_enhanced.py --dry-run --fast` |
| 2 | Type **ANALYSE** (post-analysis audit) |
| 3 | One live `python3 analyze_top200_stocks_enhanced.py` per week |
| 4 | **ANALYSE** again on live run |
| 5 | `python3 scripts/evaluate_stock_picking.py` |
| 6 | `python3 scripts/qmst_validation_gate.py` |
| 7 | `python3 scripts/verify_regime.py` — sanity-check regime vs Nifty/VIX |
| 8 | `python3 -m backtest.runner qmst --capital 100000 --top-n 10 --rebalance weekly` |
| 8b | `python3 scripts/backtest_qmst_pick_gates.py` — A/B pick gates before enabling |
| 9 | Execute: **SELL** (VMQ) → **INCREASE/NEW** (turbo PASS) → **HOLD** |

---

## Validation gates (Phase 3 — 60 consecutive days)

| Gate | Threshold |
|------|-----------|
| Forward `picking_rank` IC (30d) | ≥ 0.05 |
| Q5−Q1 spread | ≥ +3 pp |
| Walk-forward OOS IC | ≥ 0.05 |
| Backtest excess vs benchmark | &gt; 0 |
| Backtest Sharpe | &gt; 0.15 |

Run `python3 scripts/qmst_validation_gate.py` → writes `data/qmst_validation_status.json` and may flip badge to **QMST-VALIDATED**.

---

## Non-goals

- U7 / council composite score
- Using `final_blended_score` as pick driver
- Rank-SELL on profitable holdings (oracle stack)
- v1 engine changes (`hybrid_optimized_scoring.py`)

---

## Locked config (do not drift without council review)

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
  "VMQ_DAY3_ENABLED": false,
  "QMST_PICK_GATES_ENABLED": false,
  "QMST_PICK_FQ_MIN": 48,
  "QMST_PICK_RK_MIN": 42,
  "VMQ_DAY3_REGIME_GATED": true,
  "VMQ_DAY3_ACTIVE_REGIMES": "bear,high_vol",
  "VMQ_DAY3_VIX_MIN": 25,
  "VMQ_DAY3_SMART_SKIP": true,
  "VMQ_DAY3_SKIP_PNL_MIN": 5.0,
  "VMQ_DAY3_SKIP_MTF_MIN": 52,
  "VMQ_VALIDATION_FAIL_5D": -1.0,
  "V2_SHADOW_MODE": true,
  "TURBO_ENTRY_VS_MIN": 0
}
```
