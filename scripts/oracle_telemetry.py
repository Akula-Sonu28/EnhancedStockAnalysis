#!/usr/bin/env python3
"""Nightly oracle telemetry: fq vs volume IC, active oracle, walk-forward status."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from config import get_config
from src.flow_quality_oracle import (
    add_oracle_pick_columns,
    read_walkforward_verdict,
    resolve_active_oracle,
)
from src.picking_metrics import filter_rank_surface, quintile_spread, spearman_ic


def main() -> int:
    cfg = get_config()
    data_dir = Path(cfg.DATA_DIR)
    hist_path = data_dir / 'recommendation_history.csv'
    out_path = data_dir / 'oracle_telemetry.json'

    payload = {
        'updated': datetime.now().isoformat(),
        'v2_shadow_mode': bool(getattr(cfg, 'V2_SHADOW_MODE', True)),
        'calibration_mode': str(getattr(cfg, 'CALIBRATION_MODE', 'diagnostic')),
        'walkforward_verdict': read_walkforward_verdict(str(data_dir)),
        'active_oracle': 'fq_score',
        'metrics': {},
    }

    if hist_path.exists():
        df = pd.read_csv(hist_path, low_memory=False)
        df = add_oracle_pick_columns(df, cfg)
        payload['active_oracle'] = resolve_active_oracle(df, cfg)
        work = filter_rank_surface(df) if 'action' in df.columns else df
        ret_col = 'return_30d'
        if ret_col in work.columns:
            ret = pd.to_numeric(work[ret_col], errors='coerce')
            for col, label in (
                ('fq_score', 'fq_30d'),
                ('volume_pick_score', 'volume_30d'),
            ):
                if col not in work.columns:
                    continue
                score = pd.to_numeric(work[col], errors='coerce')
                ic, p, n = spearman_ic(score, ret)
                q5, q1, spread, _ = quintile_spread(score, ret)
                payload['metrics'][label] = {
                    'ic': ic,
                    'p': p,
                    'n': n,
                    'spread_pp': spread,
                    'q5_mean_pct': q5,
                    'q1_mean_pct': q1,
                }

    out_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
