#!/usr/bin/env python3
"""Screen candidate pick factors vs baseline BEFORE pipeline changes.

Uses historical outcomes (forward returns already joined). Reports Spearman IC,
quintile spreads, and per-date cross-sectional IC. Writes JSON for review.

Usage:
    python3 scripts/factor_enhancement_screen.py
    python3 scripts/factor_enhancement_screen.py --watchlist-only
    python3 scripts/factor_enhancement_screen.py --input data/historical_outcomes.csv

Exit 0 on success, 1 if dataset unusable.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.picking_metrics import quintile_spread, spearman_ic  # noqa: E402

DEFAULT_INPUT = REPO_ROOT / 'data' / 'historical_outcomes_with_fq_all_dates.csv'
OUT_JSON = REPO_ROOT / 'data' / 'factor_enhancement_screen.json'
OUT_MD = REPO_ROOT / 'data' / 'factor_enhancement_screen.md'

BASELINES = ('fq_score', 'score', 'picking_rank')

# Candidate factors: name -> description (computed in add_derived_factors)
CANDIDATE_META = {
    'hybrid_volume_strength': 'VS alone (volume leg of fq)',
    'hybrid_momentum_technical': 'MT alone (momentum leg)',
    'hybrid_multi_timeframe': 'MTF alone (turbo weight)',
    'hybrid_fundamental_quality': 'FQ quality mark',
    'hybrid_growth': 'Growth mark',
    'hybrid_value': 'Value mark',
    'hybrid_risk_adjustment': 'Risk mark (higher = safer in engine)',
    'mtf_minus_mom': 'MTF - MT (trend alignment)',
    'fq_lambda_2': 'VS - 2*MT (stricter anti-chase)',
    'quality_flow': 'FQ + 0.5*VS',
    'turbo_proxy': '0.35*MTF + 0.25*MT + 0.40*VS',
    'fund_gated_flow': 'fq_score if FQ>=48 else NaN',
}


def add_derived_factors(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    vs = pd.to_numeric(out.get('hybrid_volume_strength'), errors='coerce')
    mt = pd.to_numeric(out.get('hybrid_momentum_technical'), errors='coerce')
    mtf = pd.to_numeric(out.get('hybrid_multi_timeframe'), errors='coerce')
    fq = pd.to_numeric(out.get('hybrid_fundamental_quality'), errors='coerce')
    fq_score = pd.to_numeric(out.get('fq_score'), errors='coerce')

    out['mtf_minus_mom'] = mtf - mt
    out['fq_lambda_2'] = vs - 2.0 * mt
    out['quality_flow'] = fq + 0.5 * vs
    out['turbo_proxy'] = 0.35 * mtf + 0.25 * mt + 0.40 * vs
    out['fund_gated_flow'] = fq_score.where(fq >= 48)
    return out


def _cs_ic_by_date(df: pd.DataFrame, factor: str, ret_col: str) -> dict:
    """Mean Spearman IC across dates (cross-sectional per snapshot)."""
    rhos = []
    for _, grp in df.groupby('date'):
        if len(grp) < 15:
            continue
        rho, _, n = spearman_ic(
            pd.to_numeric(grp[factor], errors='coerce'),
            pd.to_numeric(grp[ret_col], errors='coerce'),
        )
        if rho is not None and n >= 15:
            rhos.append(rho)
    if not rhos:
        return {'mean_rho': None, 'n_dates': 0, 'n_pairs': 0}
    return {
        'mean_rho': round(float(np.mean(rhos)), 4),
        'std_rho': round(float(np.std(rhos)), 4),
        'n_dates': len(rhos),
        'n_pairs': len(rhos),
    }


def _eval_factor(df: pd.DataFrame, factor: str, ret_col: str) -> dict:
    score = pd.to_numeric(df[factor], errors='coerce')
    ret = pd.to_numeric(df[ret_col], errors='coerce')
    rho, p, n = spearman_ic(score, ret)
    q5, q1, spread, _ = quintile_spread(score, ret)
    cs = _cs_ic_by_date(df, factor, ret_col)
    return {
        'factor': factor,
        'n': n,
        'ic_rho': round(rho, 4) if rho is not None else None,
        'ic_p': round(p, 6) if p is not None else None,
        'q5_mean_pct': round(q5, 3) if q5 is not None else None,
        'q1_mean_pct': round(q1, 3) if q1 is not None else None,
        'spread_pp': round(spread, 3) if spread is not None else None,
        'cs_ic_mean': cs.get('mean_rho'),
        'cs_ic_std': cs.get('std_rho'),
        'cs_n_dates': cs.get('n_dates'),
    }


def _top_quintile_mean_return(df: pd.DataFrame, factor: str, ret_col: str, top_pct: float = 0.2) -> dict:
    """Per date: mean return of top top_pct by factor; then average across dates."""
    means = []
    for _, grp in df.groupby('date'):
        sub = grp.dropna(subset=[factor, ret_col])
        if len(sub) < 10:
            continue
        cutoff = sub[factor].quantile(1.0 - top_pct)
        top = sub[sub[factor] >= cutoff]
        if len(top) >= 2:
            means.append(float(top[ret_col].mean()))
    if not means:
        return {'mean_top_return_pct': None, 'n_dates': 0}
    return {
        'mean_top_return_pct': round(float(np.mean(means)), 3),
        'n_dates': len(means),
    }


def _verdict_vs_baseline(candidate: dict, baseline: dict) -> str:
    c_ic = candidate.get('ic_rho')
    b_ic = baseline.get('ic_rho')
    c_sp = candidate.get('spread_pp')
    b_sp = baseline.get('spread_pp')
    c_cs = candidate.get('cs_ic_mean')
    b_cs = baseline.get('cs_ic_mean')
    if c_ic is None or b_ic is None:
        return 'INSUFFICIENT'
    better_ic = c_ic > b_ic + 0.01
    better_sp = (c_sp is not None and b_sp is not None and c_sp > b_sp + 0.5)
    better_cs = (
        c_cs is not None and b_cs is not None and c_cs > b_cs + 0.02
    )
    if better_ic and (better_sp or better_cs):
        return 'PROMOTE'
    if better_ic or better_cs:
        return 'MARGINAL'
    if c_ic < b_ic - 0.02:
        return 'REJECT'
    return 'HOLD'


def main() -> int:
    parser = argparse.ArgumentParser(description='Screen pick factors before implementation')
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--ret', default='return_30d', choices=('return_7d', 'return_30d'))
    parser.add_argument('--watchlist-only', action='store_true',
                        help='Restrict to on_oracle_watchlist rows (pick surface)')
    parser.add_argument('--min-rows', type=int, default=200)
    args = parser.parse_args()

    if not args.input.exists():
        print(f'ERROR: missing {args.input}')
        return 1

    raw = pd.read_csv(args.input, parse_dates=['date'])
    work = raw.dropna(subset=[args.ret]).copy()
    if args.watchlist_only and 'on_oracle_watchlist' in work.columns:
        work = work[work['on_oracle_watchlist'].astype(bool)].copy()

    work = add_derived_factors(work)
    if len(work) < args.min_rows:
        print(f'ERROR: only {len(work)} rows with {args.ret} (need {args.min_rows})')
        return 1

    factors = list(BASELINES) + list(CANDIDATE_META.keys())
    factors = [f for f in factors if f in work.columns]

    results = []
    for fac in factors:
        sub = work.dropna(subset=[fac])
        if len(sub) < args.min_rows:
            continue
        row = _eval_factor(sub, fac, args.ret)
        row['top20_mean_return'] = _top_quintile_mean_return(sub, fac, args.ret).get('mean_top_return_pct')
        row['description'] = CANDIDATE_META.get(fac, 'baseline' if fac in BASELINES else fac)
        results.append(row)

    baseline_row = next((r for r in results if r['factor'] == 'fq_score'), None)
    if baseline_row is None:
        baseline_row = next((r for r in results if r['factor'] == 'score'), results[0])

    for r in results:
        r['vs_fq_score'] = _verdict_vs_baseline(r, baseline_row) if r['factor'] != baseline_row['factor'] else 'BASELINE'

    results.sort(
        key=lambda x: (x.get('cs_ic_mean') is None, -(x.get('cs_ic_mean') or -99)),
    )

    by_regime = {}
    if 'regime' in work.columns:
        for reg in ('BULL', 'BEAR', 'SIDEWAYS'):
            sub = work[work['regime'].astype(str).str.upper() == reg]
            if len(sub) < 80:
                continue
            reg_rows = []
            for fac in factors:
                s2 = sub.dropna(subset=[fac])
                if len(s2) < 50:
                    continue
                reg_rows.append(_eval_factor(s2, fac, args.ret))
            if reg_rows:
                by_regime[reg] = sorted(
                    reg_rows,
                    key=lambda x: (x.get('ic_rho') is None, -(x.get('ic_rho') or -99)),
                )[:8]

    promote = [r for r in results if r.get('vs_fq_score') == 'PROMOTE']
    marginal = [r for r in results if r.get('vs_fq_score') == 'MARGINAL']

    payload = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'input': str(args.input.relative_to(REPO_ROOT)),
        'return_column': args.ret,
        'watchlist_only': args.watchlist_only,
        'n_rows': len(work),
        'date_min': str(work['date'].min().date()),
        'date_max': str(work['date'].max().date()),
        'baseline': baseline_row['factor'],
        'baseline_metrics': baseline_row,
        'ranked_factors': results,
        'promote_candidates': [r['factor'] for r in promote],
        'marginal_candidates': [r['factor'] for r in marginal],
        'by_regime_top': by_regime,
        'implementation_gate': {
            'rule': 'Implement only if PROMOTE on return_30d AND backtest QMST excess improves',
            'next_script': 'python3 scripts/backtest_qmst_pick_gates.py (adapt rank_column)',
        },
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2))
    _write_md(payload)
    _print_table(results, baseline_row)

    print(f'\nWrote {OUT_JSON}')
    print(f'Wrote {OUT_MD}')
    if promote:
        print(f'\nPROMOTE vs {baseline_row["factor"]}: {", ".join(r["factor"] for r in promote)}')
    else:
        print(f'\nNo factor beat {baseline_row["factor"]} on IC+spread+CS-IC — keep fq_score pick driver.')
    print('Next: run QMST backtest with winning rank_column before touching analyze_top200.')
    return 0


def _print_table(results: list, baseline: dict) -> None:
    print('\n' + '=' * 88)
    print('FACTOR ENHANCEMENT SCREEN (pre-implementation)')
    print('=' * 88)
    print(f'{"factor":28s} {"IC_30d":>8s} {"spread":>8s} {"CS_IC":>8s} {"top20%":>8s} {"vs_fq":>10s}')
    print('-' * 88)
    for r in results:
        ic = f'{r["ic_rho"]:.4f}' if r.get('ic_rho') is not None else '   n/a'
        sp = f'{r["spread_pp"]:.2f}' if r.get('spread_pp') is not None else '   n/a'
        cs = f'{r["cs_ic_mean"]:.4f}' if r.get('cs_ic_mean') is not None else '   n/a'
        t20 = f'{r["top20_mean_return"]:.2f}' if r.get('top20_mean_return') is not None else '   n/a'
        print(f'{r["factor"]:28s} {ic:>8s} {sp:>8s} {cs:>8s} {t20:>8s} {r.get("vs_fq_score", ""):>10s}')
    print('-' * 88)
    print(f'Baseline: {baseline["factor"]}  n={baseline["n"]}')


def _write_md(payload: dict) -> None:
    lines = [
        '# Factor enhancement screen (pre-implementation)',
        '',
        f'Generated: {payload["generated"]}',
        f'Dataset: `{payload["input"]}` | rows={payload["n_rows"]} | '
        f'{payload["date_min"]} → {payload["date_max"]}',
        f'Forward return: `{payload["return_column"]}` | watchlist_only={payload["watchlist_only"]}',
        '',
        '## Gate',
        '',
        '1. **IC screen** (this file) — factor must beat `fq_score` on CS-IC or spread.',
        '2. **QMST backtest** — only then change `rank_column` / pick driver in engine.',
        '3. **Regression** — `python3 tests/test_v2_regression.py` after code change.',
        '',
        f'## Baseline (`{payload["baseline"]}`)',
        '',
        f'```json\n{json.dumps(payload["baseline_metrics"], indent=2)}\n```',
        '',
        '## Ranked factors',
        '',
        '| Factor | IC | Spread pp | CS IC mean | Top20 ret | vs fq |',
        '|--------|-----|-----------|------------|-----------|-------|',
    ]
    for r in payload['ranked_factors']:
        ic = r.get('ic_rho', 'n/a')
        sp = r.get('spread_pp', 'n/a')
        cs = r.get('cs_ic_mean', 'n/a')
        t20 = r.get('top20_mean_return', 'n/a')
        lines.append(
            f'| {r["factor"]} | {ic} | {sp} | {cs} | {t20} | {r.get("vs_fq_score", "")} |'
        )
    if payload.get('promote_candidates'):
        lines.extend(['', '## Promote candidates', ''] + [f'- `{x}`' for x in payload['promote_candidates']])
    OUT_MD.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    sys.exit(main())
