#!/usr/bin/env python3
"""QMST validation gate — forward IC + walk-forward + backtest thresholds.

Reads:
  data/stock_picking_trends.md (via evaluate_stock_picking pipeline)
  data/picking_ic_report.json (optional)
  data/walkforward_v2_validation.json
  data/recommendation_history.csv
  data/qmst_report_picking_validation.json (report-backfill pick IC)
  data/qmst_backtest_comparison.json (QMST backtest excess/sharpe)

Writes:
  data/qmst_validation_status.json

Exit 0 when all gates pass (QMST-VALIDATED), 1 otherwise (QMST-BETA).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config import get_config  # noqa: E402
from src.picking_metrics import (  # noqa: E402
    add_picking_rank_column,
    evaluate_picking_panel,
    filter_rank_surface,
)

HISTORY_PATH = REPO_ROOT / 'data' / 'recommendation_history.csv'
WALKFORWARD_PATH = REPO_ROOT / 'data' / 'walkforward_v2_validation.json'
PICKING_IC_PATH = REPO_ROOT / 'data' / 'picking_ic_report.json'
REPORT_PICKING_PATH = REPO_ROOT / 'data' / 'qmst_report_picking_validation.json'
QMST_BACKTEST_PATH = REPO_ROOT / 'data' / 'qmst_backtest_comparison.json'
OUT_PATH = REPO_ROOT / 'data' / 'qmst_validation_status.json'

GATES = {
    'forward_picking_ic_30d': 0.05,
    'quintile_spread_pp': 3.0,
    'walkforward_oos_ic': 0.05,
    'backtest_excess_return': 0.0,
    'backtest_sharpe': 0.15,
}

# Production satellite profile (no day-3, low trade count): excess return is primary.
PRODUCTION_BACKTEST_GATES = {
    'backtest_excess_return': 0.0,
    'backtest_sharpe': -0.10,
}


def _backtest_gate_thresholds(bt_source: str) -> dict:
    if bt_source and ('production_default' in bt_source or 'no_day3' in bt_source):
        return {**GATES, **PRODUCTION_BACKTEST_GATES}
    return GATES


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _eval_forward_picking() -> dict:
    if not HISTORY_PATH.exists():
        return {'status': 'NO_HISTORY', 'ic_rho': None, 'spread_pp': None, 'n': 0}
    import pandas as pd

    hist = pd.read_csv(HISTORY_PATH, parse_dates=['date'])
    surf = filter_rank_surface(hist)
    surf = add_picking_rank_column(surf, get_config())
    return evaluate_picking_panel(surf, score_col='picking_rank', rank_surface_only=False)


def _load_report_picking_backfill() -> dict:
    data = _load_json(REPORT_PICKING_PATH)
    if not data:
        return {}
    gates = data.get('gates') or {}
    fwd = gates.get('forward_picking_ic_30d') or {}
    spread = gates.get('quintile_spread_pp') or {}
    return {
        'ic_rho': fwd.get('value'),
        'spread_pp': spread.get('value'),
        'n': fwd.get('n', 0),
        'ic_days': data.get('ic_decision_dates'),
        'pick_layer_certified': data.get('pick_layer_certified'),
        'report_dates': data.get('report_dates_with_vs_mt'),
    }


def _load_qmst_backtest_metrics() -> dict:
    data = _load_json(QMST_BACKTEST_PATH)
    if not data:
        return {}
    prod = data.get('production_default') or {}
    by_dur = prod.get('by_duration') or data.get('no_day3_by_duration') or {}
    block = by_dur.get('12m') if isinstance(by_dur, dict) else None
    if isinstance(block, dict):
        excess = block.get('excess_return_pct')
        sharpe = block.get('sharpe')
        if excess is not None and sharpe is not None:
            return {
                'excess_return': float(excess) / 100.0,
                'sharpe': float(sharpe),
                'source': 'production_default_12m_no_day3',
                'window': block.get('window'),
            }
    for key in ('no_day3_by_duration',):
        nested = data.get(key)
        if isinstance(nested, dict) and '12m' in nested:
            block = nested['12m']
            excess = block.get('excess_return_pct')
            sharpe = block.get('sharpe')
            if excess is not None and sharpe is not None:
                return {
                    'excess_return': float(excess) / 100.0,
                    'sharpe': float(sharpe),
                    'source': f'{key}.12m',
                    'window': block.get('window'),
                }
    return {}


def main() -> int:
    cfg = get_config()
    generated = datetime.now().isoformat(timespec='seconds')
    forward = _eval_forward_picking()
    report_pick = _load_report_picking_backfill()
    wf = _load_json(WALKFORWARD_PATH)
    picking_ic = _load_json(PICKING_IC_PATH)
    qmst_bt = _load_qmst_backtest_metrics()

    # Prefer live history; fall back to report-backfill pick IC when live is undefined.
    fwd_ic = forward.get('ic_rho')
    fwd_spread = forward.get('spread_pp')
    fwd_n = forward.get('n', 0)
    fwd_source = 'recommendation_history'
    if fwd_ic is None or (isinstance(fwd_ic, float) and np.isnan(fwd_ic)):
        if report_pick.get('ic_rho') is not None:
            fwd_ic = report_pick.get('ic_rho')
            fwd_spread = report_pick.get('spread_pp')
            fwd_n = report_pick.get('n', 0)
            fwd_source = 'report_backfill_42d'

    wf_ic = None
    try:
        wf_ic = (wf.get('folds_summary') or {}).get('mean_ic')
        if wf_ic is None:
            wf_ic = wf.get('mean_oos_ic')
    except Exception:
        wf_ic = None

    backtest_excess = picking_ic.get('excess_return')
    backtest_sharpe = picking_ic.get('sharpe')
    bt_source = 'picking_ic_report'
    if qmst_bt:
        backtest_excess = qmst_bt.get('excess_return')
        backtest_sharpe = qmst_bt.get('sharpe')
        bt_source = qmst_bt.get('source', 'qmst_backtest_comparison')

    gate_thr = _backtest_gate_thresholds(bt_source or '')

    checks = {
        'forward_picking_ic_30d': {
            'value': fwd_ic,
            'threshold': GATES['forward_picking_ic_30d'],
            'pass': (
                fwd_ic is not None
                and not (isinstance(fwd_ic, float) and np.isnan(fwd_ic))
                and float(fwd_ic) >= GATES['forward_picking_ic_30d']
                and (fwd_n or 0) >= 30
            ),
            'n': fwd_n,
            'source': fwd_source,
        },
        'quintile_spread_pp': {
            'value': fwd_spread,
            'threshold': GATES['quintile_spread_pp'],
            'pass': (
                fwd_spread is not None
                and not (isinstance(fwd_spread, float) and np.isnan(fwd_spread))
                and float(fwd_spread) >= GATES['quintile_spread_pp']
            ),
            'source': fwd_source,
        },
        'walkforward_oos_ic': {
            'value': wf_ic,
            'threshold': GATES['walkforward_oos_ic'],
            'pass': wf_ic is not None and float(wf_ic) >= GATES['walkforward_oos_ic'],
        },
        'backtest_excess_return': {
            'value': backtest_excess,
            'threshold': gate_thr['backtest_excess_return'],
            'pass': (
                backtest_excess is not None
                and float(backtest_excess) > gate_thr['backtest_excess_return']
            ),
            'optional': not PICKING_IC_PATH.exists() and not QMST_BACKTEST_PATH.exists(),
            'source': bt_source,
            'profile': 'production' if bt_source and 'production' in bt_source else 'default',
        },
        'backtest_sharpe': {
            'value': backtest_sharpe,
            'threshold': gate_thr['backtest_sharpe'],
            'pass': (
                backtest_sharpe is not None
                and float(backtest_sharpe) > gate_thr['backtest_sharpe']
            ),
            'optional': not PICKING_IC_PATH.exists() and not QMST_BACKTEST_PATH.exists(),
            'source': bt_source,
            'profile': 'production' if bt_source and 'production' in bt_source else 'default',
        },
        'report_pick_layer': {
            'value': report_pick.get('pick_layer_certified'),
            'threshold': True,
            'pass': bool(report_pick.get('pick_layer_certified')),
            'optional': not REPORT_PICKING_PATH.exists(),
            'ic_days': report_pick.get('ic_days'),
            'report_dates': report_pick.get('report_dates'),
        },
    }

    required = [k for k, v in checks.items() if not v.get('optional')]
    all_required_pass = all(checks[k]['pass'] for k in required)
    optional_pass = all(
        checks[k]['pass'] for k in checks if checks[k].get('optional') and checks[k]['value'] is not None
    )

    if all_required_pass and (optional_pass or not PICKING_IC_PATH.exists()):
        badge = 'QMST-VALIDATED'
    elif forward.get('ic_rho') is not None and forward.get('ic_rho') < 0:
        badge = 'QMST-DEMOTE'
    elif report_pick.get('pick_layer_certified') and wf_ic is not None and float(wf_ic) >= GATES['walkforward_oos_ic']:
        badge = 'QMST-BETA'
    else:
        badge = str(getattr(cfg, 'QMST_STATUS_BADGE', 'QMST-BETA') or 'QMST-BETA')

    status = {
        'generated': generated,
        'badge': badge,
        'qmst_enabled': bool(getattr(cfg, 'QMST_ENABLED', True)),
        'gates': checks,
        'all_required_pass': all_required_pass,
        'report_pick_layer_certified': bool(report_pick.get('pick_layer_certified')),
        'forward_ic_source': fwd_source,
        'backtest_source': bt_source if qmst_bt or picking_ic else None,
        'note': (
            'Run `python3 scripts/evaluate_fq_from_reports.py --qmst-validation` for '
            '42-day report pick IC. Full QMST-VALIDATED requires all gates + '
            '60 consecutive days of live picking_rank history for production proof.'
        ),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(status, indent=2), encoding='utf-8')

    print(f'QMST badge: {badge}')
    for name, chk in checks.items():
        val = chk.get('value')
        thr = chk.get('threshold')
        ok = 'PASS' if chk.get('pass') else 'FAIL'
        opt = ' (optional)' if chk.get('optional') else ''
        print(f'  [{ok}] {name}: {val} (need {thr}){opt}')
    print(f'Wrote {OUT_PATH}')
    return 0 if badge == 'QMST-VALIDATED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
