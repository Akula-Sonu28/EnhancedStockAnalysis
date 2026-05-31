# Oracle Recovery Plan (P0 shipped 2026-05-30)

## Problem
v1/v2 rank is inverted on 30d (IC ~ −0.48). Rank-SELL fires on winners. Turbo entry aliased broken `score_v2`.

## Architecture (three oracles)
| Role | Engine | Use |
|------|--------|-----|
| **Pick** | `flow_quality` / volume rolling switch | Fortnightly watchlist (top 20%) |
| **Time** | `turbo_mtf` recomputed | NEW entry timing + VMQ |
| **Exit** | Hard stop, VMQ, trail | No rank-SELL on CORE |

## Config knobs
- `V2_SHADOW_MODE=true` — v2 does not drive actions
- `PICKING_RANK_DRIVER=flow_quality`
- `ORACLE_PAUSE_NEW_ON_HOLD_SHADOW=true`
- `ORACLE_DISABLE_RANK_SELL_ON_CORE=true`
- `CALIBRATION_MODE=diagnostic`
- `VMQ_REQUIRE_TURBO_PASS=true`, `VMQ_TURBO_MIN=65`

## Files
- `src/flow_quality_oracle.py` — pick scores + pause logic
- `data/oracle_weights.json` — turbo tau_entry weights
- `scripts/oracle_telemetry.py` — nightly IC JSON

## Rating ladder
| Stage | Oracle |
|-------|--------|
| Before P0 | 3.5/10 |
| P0 shipped | ~5/10 (governance + picker) |
| 60d live NEW labels | ~6/10 |
| Multi-regime proof | 7+/10 |

## Next
- Backfill `fq_score` on historical rows
- 60 days forward on NEW POSITION before raising oracle above 5/10
