# Strategy deep-dive summary (2026-05-31)

Pre-implementation gate: IC screen (`strategy_deepdive_screen.py`) + QMST Path2 backtest 3m/6m/12m.

## Verdict

**No strategy clearly beats `fq_lambda_2` (VS − 2×MT) on portfolio backtest.**

**Production default stays `fq_score` (VS − 0.5×MT)** until shadow trial completes.

**Best shadow candidate:** `fq_lambda_2` → alias `flow_lam_2_0` / `rank_fq_lambda_2`.

**Second-tier shadows (12m only):** `flow_lam_1_25`, `fq_adapt_score`, `anti_chase_mtf`.

**Reject as pick driver:** `score_v2`, `hybrid_multi_timeframe` alone, `flow_lam_0_8` (despite high pooled IC).

---

## Lambda sweep (VS − λ×MT)

| λ | Pooled IC | CS IC | 3m excess | 6m excess | 12m excess |
|---|-----------|-------|-----------|-----------|------------|
| 0.5 (fq_score) | 0.38 | 0.057 | 19.37 | 16.35 | 8.17 |
| 0.8 | **0.41** | **0.058** | 19.37 | 16.35 | 6.94 |
| 1.0 | 0.42 | 0.057 | 19.37 | 16.24 | 8.14 |
| 1.25 | 0.43 | 0.055 | 19.37 | 16.24 | **12.24** |
| 1.5 | 0.43 | 0.052 | 19.37 | 16.24 | **12.24** |
| **2.0 (fq_lambda_2)** | 0.43 | 0.047 | 19.37 | **18.52** | **13.06** |

Insight: λ≈0.8 maximizes **IC** on history; λ≈1.25–2.0 maximizes **12m simulated excess**. Pick λ by objective (predictive fit vs P&L sim).

---

## Composite strategies (backtest excess vs fq_score)

| Strategy | 6m Δ | 12m Δ | Overall |
|----------|------|-------|---------|
| fq_lambda_2 | +2.2pp | +4.9pp | **CONFIRM** |
| flow_lam_1_25 / 1.5 / low_mom_high_vol | ~0 | +4.1pp | MIXED |
| fq_adapt_score | −0.6pp | +4.2pp | MIXED |
| anti_chase_mtf | ~0 | +3.6pp | MIXED |
| score_v2 | +4.6pp | −3.4pp | REJECT (unstable) |
| flow_mtf_confirm | 0 | 0 | REJECT |

---

## IC-only traps (do not implement from IC alone)

| Strategy | Why trap |
|----------|----------|
| score_v2 | CS IC 0.086 but pooled IC negative; 12m backtest fails |
| hybrid_ml_signal | Sparse data; negative spread |
| flow_lam_0_8 | Best pooled IC; 12m backtest worse than baseline |

---

## Commands

```bash
python3 scripts/strategy_deepdive_screen.py
python3 scripts/factor_enhancement_backtest.py --durations 3m 6m 12m \
  --variants fq_score fq_lambda_2 flow_lam_1_25 fq_adapt_score anti_chase_mtf
```

## Next step

Shadow A/B: `PICK_RANK_DRIVER=fq_score|fq_lambda_2` — not broader composite until 12m+6m confirmed on live history.
