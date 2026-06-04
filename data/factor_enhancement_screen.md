# Factor enhancement screen (pre-implementation)

Generated: 2026-05-31T19:51:53
Dataset: `data/historical_outcomes_with_fq_all_dates.csv` | rows=845 | 2026-03-17 → 2026-04-29
Forward return: `return_30d` | watchlist_only=True

## Gate

1. **IC screen** (this file) — factor must beat `fq_score` on CS-IC or spread.
2. **QMST backtest** — only then change `rank_column` / pick driver in engine.
3. **Regression** — `python3 tests/test_v2_regression.py` after code change.

## Baseline (`fq_score`)

```json
{
  "factor": "fq_score",
  "n": 845,
  "ic_rho": 0.0394,
  "ic_p": 0.252848,
  "q5_mean_pct": 11.605,
  "q1_mean_pct": 9.322,
  "spread_pp": 2.283,
  "cs_ic_mean": 0.0576,
  "cs_ic_std": 0.1276,
  "cs_n_dates": 9,
  "top20_mean_return": 9.302,
  "description": "baseline",
  "vs_fq_score": "BASELINE"
}
```

## Ranked factors

| Factor | IC | Spread pp | CS IC mean | Top20 ret | vs fq |
|--------|-----|-----------|------------|-----------|-------|
| turbo_proxy | -0.0128 | -0.72 | 0.145 | 9.637 | MARGINAL |
| hybrid_volume_strength | -0.0122 | 0.1 | 0.114 | 11.367 | MARGINAL |
| hybrid_multi_timeframe | -0.0032 | 0.67 | 0.1126 | 8.626 | MARGINAL |
| hybrid_momentum_technical | -0.0441 | -0.282 | 0.0811 | 8.7 | MARGINAL |
| mtf_minus_mom | 0.1163 | 4.698 | 0.0647 | 8.829 | PROMOTE |
| fq_score | 0.0394 | 2.283 | 0.0576 | 9.302 | BASELINE |
| picking_rank | 0.0394 | 2.283 | 0.0576 | 9.302 | HOLD |
| fund_gated_flow | 0.0237 | 1.54 | 0.036 | 9.12 | HOLD |
| quality_flow | -0.0202 | -0.26 | -0.005 | 9.698 | REJECT |
| fq_lambda_2 | 0.0965 | 3.045 | -0.0202 | 8.97 | PROMOTE |
| hybrid_fundamental_quality | 0.0022 | 0.024 | -0.0363 | 9.333 | REJECT |
| score | -0.5013 | -13.056 | -0.3687 | 7.09 | REJECT |
| hybrid_risk_adjustment | -0.373 | -10.349 | -0.4129 | 5.411 | REJECT |

## Promote candidates

- `mtf_minus_mom`
- `fq_lambda_2`
