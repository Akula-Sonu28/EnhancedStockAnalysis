#!/usr/bin/env python3
"""Compare QMST baseline vs FQ/RK pick-gate variants across 3m/6m/12m windows.

Writes data/qmst_pick_gates_backtest.json — use before enabling QMST_PICK_GATES_ENABLED.

Usage:
    python3 scripts/backtest_qmst_pick_gates.py
    python3 scripts/backtest_qmst_pick_gates.py --durations 12m
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backtest.data.path2_rescore import Path2Rescorer
from backtest.data.qmst_loader import enrich_snapshots
from backtest.engine import BacktestEngine, EngineConfig
from backtest.qmst_strategy import QMSTStrategyAdapter
from backtest.runner import _months_before

OUT_PATH = REPO_ROOT / 'data' / 'qmst_pick_gates_backtest.json'

DURATIONS = {
    '3m': 3,
    '6m': 6,
    '12m': 12,
}

SUMMARY_KEYS = (
    'total_return_pct', 'excess_return_pct', 'benchmark_return_pct',
    'sharpe', 'max_drawdown_pct', 'trades_total', 'stcg_paid',
    'qmst_entries_passed', 'qmst_entries_blocked', 'qmst_pick_gates_blocked',
)


def _run_variant(
    months: int,
    pick_gates: bool,
    capital: float,
    top_n: int,
    rebalance: str,
) -> dict:
    end = date.today()
    start = _months_before(end, months)
    rescorer = Path2Rescorer()
    raw = rescorer.build_snapshots(start, end, cadence=rebalance)
    snapshots = enrich_snapshots(raw, min_universe=20)
    if not snapshots:
        return {'error': f'no snapshots for {months}m window'}

    cfg = EngineConfig(
        initial_capital=capital,
        target_positions=top_n,
        max_positions=top_n + 5,
        rebalance=rebalance,
        rank_column='fq_score',
        watchlist_column='on_oracle_watchlist',
        require_turbo_pass=True,
        apply_min_entry_score=False,
        allow_rotation=False,
    )
    strategy = QMSTStrategyAdapter(include_day3=False, pick_gates_enabled=pick_gates)
    engine = BacktestEngine(engine_label='qmst', cfg=cfg, strategy=strategy)
    result = engine.run(snapshots)

    block = {
        'window': f'{start} to {end}',
        'pick_gates_enabled': pick_gates,
        'months': months,
    }
    for k in SUMMARY_KEYS:
        if k in result.summary:
            block[k] = result.summary[k]
    block['qmst_pick_gates_blocked'] = strategy.pick_gates_blocked
    block['qmst_entries_passed'] = strategy.entries_passed
    block['qmst_entries_blocked'] = strategy.entries_blocked
    return block


def _recommendation(baseline: dict, gated: dict) -> str:
    if baseline.get('error') or gated.get('error'):
        return 'INSUFFICIENT_DATA'
    b_ex = float(baseline.get('excess_return_pct') or 0)
    g_ex = float(gated.get('excess_return_pct') or 0)
    b_tr = int(baseline.get('trades_total') or 0)
    g_tr = int(gated.get('trades_total') or 0)
    if g_ex > b_ex + 1.0 and g_tr <= b_tr:
        return 'ENABLE_GATES'
    if g_ex >= b_ex - 0.5 and g_tr < b_tr * 0.85:
        return 'ENABLE_GATES_FEWER_TRADES'
    if g_ex < b_ex - 2.0:
        return 'KEEP_GATES_OFF'
    return 'INCONCLUSIVE'


def main() -> int:
    parser = argparse.ArgumentParser(description='QMST pick-gate A/B backtest')
    parser.add_argument('--durations', nargs='+', default=list(DURATIONS.keys()),
                        choices=list(DURATIONS.keys()))
    parser.add_argument('--capital', type=float, default=100_000.0)
    parser.add_argument('--top-n', type=int, default=10)
    parser.add_argument('--rebalance', default='weekly', choices=('daily', 'weekly', 'monthly'))
    args = parser.parse_args()

    from config import get_config
    cfg = get_config()

    report = {
        'generated': date.today().isoformat(),
        'gate_thresholds': {
            'QMST_PICK_FQ_MIN': getattr(cfg, 'QMST_PICK_FQ_MIN', 48.0),
            'QMST_PICK_RK_MIN': getattr(cfg, 'QMST_PICK_RK_MIN', 42.0),
            'QMST_PICK_VL_GATE': getattr(cfg, 'QMST_PICK_VL_GATE', False),
            'QMST_PICK_VL_MIN': getattr(cfg, 'QMST_PICK_VL_MIN', 45.0),
        },
        'note': 'Promoter pledge=0 not backtestable (no column in historical_outcomes).',
        'by_duration': {},
    }

    for label in args.durations:
        months = DURATIONS[label]
        print(f'Running {label}: baseline vs pick-gates ...')
        baseline = _run_variant(months, False, args.capital, args.top_n, args.rebalance)
        gated = _run_variant(months, True, args.capital, args.top_n, args.rebalance)
        rec = _recommendation(baseline, gated)
        report['by_duration'][label] = {
            'baseline_no_gates': baseline,
            'with_pick_gates': gated,
            'delta_excess_return_pp': (
                None if baseline.get('error') or gated.get('error')
                else round(float(gated.get('excess_return_pct', 0)) - float(baseline.get('excess_return_pct', 0)), 2)
            ),
            'recommendation': rec,
        }
        if not baseline.get('error'):
            print(
                f'  {label} baseline excess={baseline.get("excess_return_pct"):.2f}% '
                f'trades={baseline.get("trades_total")} | '
                f'gated excess={gated.get("excess_return_pct"):.2f}% '
                f'trades={gated.get("trades_total")} → {rec}'
            )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'\nWrote {OUT_PATH}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
