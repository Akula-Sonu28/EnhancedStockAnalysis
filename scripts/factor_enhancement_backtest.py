#!/usr/bin/env python3
"""QMST portfolio backtest comparing rank_column variants (pre-implementation gate).

Run AFTER factor_enhancement_screen.py. Compares pick-rank variants vs fq_score baseline.

Usage:
    python3 scripts/factor_enhancement_backtest.py
    python3 scripts/factor_enhancement_backtest.py --durations 3m 6m 12m
    python3 scripts/factor_enhancement_backtest.py --months 6
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backtest.data.path2_rescore import Path2Rescorer  # noqa: E402
from backtest.data.qmst_loader import enrich_snapshots  # noqa: E402
from backtest.engine import BacktestEngine, EngineConfig  # noqa: E402
from backtest.qmst_strategy import QMSTStrategyAdapter  # noqa: E402
from backtest.runner import _months_before  # noqa: E402

OUT_PATH = REPO_ROOT / 'data' / 'factor_enhancement_backtest.json'
SCREEN_PATH = REPO_ROOT / 'data' / 'factor_enhancement_screen.json'

DURATIONS = {'3m': 3, '6m': 6, '12m': 12}

# label -> rank column name on snapshot df (built in _add_rank_columns)
VARIANTS = {
    'fq_score': 'fq_score',
    'fq_lambda_2': 'rank_fq_lambda_2',
    'flow_lam_0_8': 'rank_flow_lam_0_8',
    'flow_lam_1_0': 'rank_flow_lam_1_0',
    'flow_lam_1_25': 'rank_flow_lam_1_25',
    'flow_lam_1_5': 'rank_flow_lam_1_5',
    'low_mom_high_vol': 'rank_low_mom_high_vol',
    'anti_chase_mtf': 'rank_anti_chase_mtf',
    'flow_mtf_confirm': 'rank_flow_mtf_confirm',
    'fq_adapt_score': 'fq_adapt_score',
    'score_v2': 'score_v2',
    'mtf_minus_mom': 'rank_mtf_minus_mom',
    'hybrid_multi_timeframe': 'hybrid_multi_timeframe',
}


def _add_rank_columns(snapshots: list) -> list:
    import pandas as pd
    from backtest.data.path1_loader import DateSnapshot
    from src.flow_quality_oracle import adaptive_momentum_lambda, compute_flow_quality_score

    out = []
    for snap in snapshots:
        df = snap.df.copy()
        mtf = pd.to_numeric(df.get('hybrid_multi_timeframe'), errors='coerce')
        mt = pd.to_numeric(df.get('hybrid_momentum_technical'), errors='coerce')
        vs = pd.to_numeric(df.get('hybrid_volume_strength'), errors='coerce')
        df['rank_mtf_minus_mom'] = mtf - mt
        for lam in (0.8, 1.0, 1.25, 1.5, 2.0):
            key = f'rank_flow_lam_{str(lam).replace(".", "_")}'
            df[key] = vs - lam * mt
        df['rank_fq_lambda_2'] = vs - 2.0 * mt
        df['rank_low_mom_high_vol'] = vs - 1.5 * mt.clip(lower=40)
        df['rank_anti_chase_mtf'] = (vs - 1.25 * mt) + 0.1 * (mtf - 50)
        df['rank_flow_mtf_confirm'] = (vs - 0.5 * mt) + 0.15 * (mtf - 50)
        if 'fq_score' not in df.columns:
            df['fq_score'] = vs - 0.5 * mt
        df['fq_adapt_score'] = [
            compute_flow_quality_score(v, m, lam=adaptive_momentum_lambda(m), cfg=None)
            for v, m in zip(vs.fillna(50), mt.fillna(50))
        ]
        out.append(DateSnapshot(decision_date=snap.decision_date, df=df))
    return out


def _run_window(
    snapshots: list,
    rank_column: str,
    capital: float,
    top_n: int,
) -> dict:
    cfg = EngineConfig(
        initial_capital=capital,
        target_positions=top_n,
        max_positions=top_n + 5,
        rebalance='weekly',
        rank_column=rank_column,
        watchlist_column='on_oracle_watchlist',
        require_turbo_pass=True,
        apply_min_entry_score=False,
        allow_rotation=False,
    )
    strategy = QMSTStrategyAdapter(include_day3=False, pick_gates_enabled=False)
    engine = BacktestEngine(engine_label='qmst_factor_test', cfg=cfg, strategy=strategy)
    result = engine.run(snapshots)
    return {
        'rank_column': rank_column,
        'total_return_pct': round(float(result.summary.get('total_return_pct') or 0), 2),
        'excess_return_pct': round(float(result.summary.get('excess_return_pct') or 0), 2),
        'benchmark_return_pct': result.summary.get('benchmark_return_pct'),
        'sharpe': round(float(result.summary.get('sharpe') or 0), 2),
        'max_drawdown_pct': round(float(result.summary.get('max_drawdown_pct') or 0), 2),
        'trades_total': int(result.summary.get('trades_total') or 0),
        'qmst_entries_passed': strategy.entries_passed,
        'qmst_entries_blocked': strategy.entries_blocked,
    }


def _gate_vs_baseline(variant_ex: float, baseline_ex: float) -> str:
    if variant_ex > baseline_ex + 1.0:
        return 'IMPLEMENT'
    if variant_ex >= baseline_ex - 0.5:
        return 'PAPER_ONLY'
    return 'REJECT'


def _run_duration(
    months: int,
    label: str,
    capital: float,
    top_n: int,
    variant_names: list[str],
) -> dict:
    end = date.today()
    start = _months_before(end, months)
    print(f'\n--- {label} ({start} -> {end}) ---')
    print('Building Path2 snapshots...')
    rescorer = Path2Rescorer()
    raw = rescorer.build_snapshots(start, end, cadence='weekly')
    if not raw:
        return {'error': 'no snapshots', 'months': months, 'label': label}

    enriched = _add_rank_columns(enrich_snapshots(raw, min_universe=20))
    print(f'Snapshots: {len(enriched)}')

    results = {}
    for name in variant_names:
        col = VARIANTS.get(name, name)
        print(f'  {name} ({col})...')
        block = _run_window(enriched, col, capital, top_n)
        block['label'] = name
        results[name] = block

    baseline_ex = float(results.get('fq_score', {}).get('excess_return_pct') or 0)
    recommendations = {}
    for name, block in results.items():
        if name == 'fq_score':
            recommendations[name] = 'BASELINE'
        else:
            ex = float(block.get('excess_return_pct') or 0)
            recommendations[name] = _gate_vs_baseline(ex, baseline_ex)

    return {
        'label': label,
        'months': months,
        'window': f'{start} to {end}',
        'n_snapshots': len(enriched),
        'results': results,
        'recommendations': recommendations,
        'baseline_excess_pct': baseline_ex,
    }


def _cross_window_summary(windows: dict) -> dict:
    """Count wins per variant across 3m/6m/12m on excess return."""
    variants = [v for v in VARIANTS if v != 'fq_score']
    summary = {}
    for v in variants:
        wins = 0
        paper = 0
        reject = 0
        deltas = []
        for _label, block in windows.items():
            if block.get('error'):
                continue
            rec = block.get('recommendations', {}).get(v, 'REJECT')
            if rec == 'IMPLEMENT':
                wins += 1
            elif rec == 'PAPER_ONLY':
                paper += 1
            else:
                reject += 1
            b_ex = float(block.get('baseline_excess_pct') or 0)
            v_ex = float(block.get('results', {}).get(v, {}).get('excess_return_pct') or 0)
            deltas.append(round(v_ex - b_ex, 2))
        if wins >= 2:
            overall = 'CONFIRM_IMPLEMENT'
        elif wins == 1 and reject <= 1:
            overall = 'MIXED'
        else:
            overall = 'DO_NOT_IMPLEMENT'
        summary[v] = {
            'implement_windows': wins,
            'paper_windows': paper,
            'reject_windows': reject,
            'excess_delta_pp': deltas,
            'overall': overall,
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--durations',
        nargs='*',
        default=['3m', '6m', '12m'],
        help='Windows: 3m 6m 12m (default: all three)',
    )
    parser.add_argument('--months', type=int, default=None,
                        help='Single window only (overrides --durations)')
    parser.add_argument('--capital', type=float, default=100_000.0)
    parser.add_argument('--top-n', type=int, default=10)
    parser.add_argument('--variants', nargs='*', default=list(VARIANTS.keys()))
    args = parser.parse_args()

    if args.months is not None:
        duration_map = {f'{args.months}m': args.months}
    else:
        duration_map = {}
        for d in args.durations:
            key = d.lower().replace('months', 'm')
            if key not in DURATIONS:
                print(f'ERROR: unknown duration {d!r}; use 3m 6m 12m')
                return 1
            duration_map[key] = DURATIONS[key]

    windows = {}
    for label, months in sorted(duration_map.items(), key=lambda x: x[1]):
        windows[label] = _run_duration(
            months, label, args.capital, args.top_n, args.variants,
        )

    screen_promote = []
    if SCREEN_PATH.exists():
        try:
            screen_promote = json.loads(SCREEN_PATH.read_text()).get('promote_candidates', [])
        except Exception:
            pass

    cross = _cross_window_summary(windows)
    payload = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'durations': list(duration_map.keys()),
        'ic_screen_promote': screen_promote,
        'windows': windows,
        'cross_window_summary': cross,
        'implement_if': (
            'CONFIRM_IMPLEMENT on 2+ windows (excess beat fq_score by >1pp) '
            'AND IC screen not REJECT — then shadow A/B in config'
        ),
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2))

    print('\n' + '=' * 88)
    print('FACTOR BACKTEST — 3m / 6m / 12m vs fq_score (excess return %)')
    print('=' * 88)
    header = f'{"variant":22s}'
    for label in sorted(duration_map.keys(), key=lambda k: duration_map[k]):
        header += f' {label:>10s}'
    header += f' {"overall":>18s}'
    print(header)
    print('-' * 88)

    for name in args.variants:
        row = f'{name:22s}'
        for label in sorted(duration_map.keys(), key=lambda k: duration_map[k]):
            block = windows.get(label, {})
            if block.get('error'):
                row += f' {"n/a":>10s}'
                continue
            ex = block.get('results', {}).get(name, {}).get('excess_return_pct', 0)
            rec = block.get('recommendations', {}).get(name, '')
            mark = '*' if rec == 'IMPLEMENT' else ''
            row += f' {ex:>9.2f}{mark}'
        if name != 'fq_score':
            row += f' {cross.get(name, {}).get("overall", ""):>18s}'
        else:
            row += f' {"BASELINE":>18s}'
        print(row)

    print('-' * 88)
    print('* = IMPLEMENT gate (>1pp vs fq_score excess in that window)')
    print(f'\nWrote {OUT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
