# Stock Picking Trends & Accuracy

**Generated:** 2026-05-31T00:51:54
**QMST status:** QMST-BETA
**Source:** `recommendation_history.csv` (1300 rows, 2026-03-24 22:55:43.784902 → 2026-05-25 18:54:24.795113)

## Picking ability rating: **6.5/10** (Good)

Rank-surface IC (excludes forced SELL/EXIT rows):

| Engine | IC (30d) | Q5−Q1 (pp) | n |
|--------|----------|------------|---|
| v1 score | -0.3452825668854941 | -6.8091168327796225 | 428 |
| v2 score | None | None | 0 |
| picking_rank | None | nan | 428 |

### Historical outcomes panel (v2 calibration universe)

| v1 score | -0.4811906300053678 | -12.706441534418156 | 4408 |
| v2 synth | 0.003528829018876656 | 0.5346887555457345 | 3697 |

Walk-forward mean OOS IC (5-fold): **0.0717**

## QMST forward pick telemetry

| picking_rank IC | None | spread nan pp | n=428 |

> Validation gates: `python3 scripts/qmst_validation_gate.py`

_Note: forward `recommendation_history` v2 IC needs 30d returns on rows with `hybrid_*` columns (hybrid logging started 2026-05-07)._

## Overall Hit Rates

| Horizon | BUY correct | n | SELL correct | n |
|---------|-------------|---|--------------|---|
| 30d | 85.4% | 48 | 21.9% | 351 |

> Re-run: `python3 scripts/evaluate_stock_picking.py`
