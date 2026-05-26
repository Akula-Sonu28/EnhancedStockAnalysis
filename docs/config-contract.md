# Config Contract — Defaults vs Production Overrides

This document records **intentional** differences between `config.py` dataclass
defaults and the live `config.json` overrides loaded at import time. JSON always
wins over Python defaults (`load_config_from_file`).

Human decision (2026-05-24 audit): these overrides are **production tuning** —
do not revert without explicit investor approval.

## Intentional overrides (`config.json` ≠ `config.py` default)

| Key | `config.py` default | `config.json` (live) | Rationale |
|-----|-------------------|----------------------|-----------|
| `HARD_STOP_PCT` | `-0.07` | `-0.08` | Tighter tactical stop (−8% vs −7%) |
| `ROTATION_FRICTION_POINTS` | `5.0` | `3.0` | Lower friction — rotations need 3pp edge |
| `REGIME_FLIP_COOLDOWN_DAYS` | `7` | `5` | Shorter recent-buy hold window (5 trading days) |

## Locked (must match unless explicitly approved)

| Key | Value | Notes |
|-----|-------|-------|
| `STRONG_BUY_THRESHOLD` | `70` | Do not change without full regression |
| `BUY_THRESHOLD` | `60` | |
| `HOLD_THRESHOLD` | `50` | |
| `SELL_THRESHOLD` | `40` | |
| `V2_SHADOW_MODE` | `false` | v2 LIVE since 2026-05-13; forward IC window accrues until ~2026-06-12 |

## Sector cap policy (code + config)

| Key | Value | Behavior |
|-----|-------|----------|
| `SECTOR_CAP` | `10` | Max names per sector in allocation |
| `SECTOR_CAP_ENFORCE_HOLDINGS` | `true` | Post-holdings pass marks excess as `REDUCE (SECTOR OVERWEIGHT)` |
| ROI-first skip | *(code)* | Holdings with `overall_score ≥ 50` are **exempt** from sector REDUCE — documented in `_Metadata` and `reference.md` §5 |

## Promotion telemetry

- Run `python3 scripts/v2_promotion_check.py` after calibration or weekly.
- `--evaluate` prints metrics without writing `data/v2_promotion_status.json`.
- Forward mode v2 IC requires joint `score_v2` + `return_30d` in history (~30d after v2 live).

## See also

- [`config.py`](../config.py) — dataclass defaults and `_VALIDATION_RULES`
- [`.cursor/skills/stock-analysis-system/reference.md`](../.cursor/skills/stock-analysis-system/reference.md) — full system reference
