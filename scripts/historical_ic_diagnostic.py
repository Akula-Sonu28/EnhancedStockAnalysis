"""Per-regime Information Coefficient (IC) diagnostic.

Reads `data/historical_outcomes.csv` (the combined dataset built by
`build_historical_outcomes.py`) and computes, separately for each market
regime in {BULL, BEAR, SIDEWAYS}, the score predictiveness measures:

    - Spearman IC_30d (correlation of `score` to `return_30d`)
    - Spearman IC_7d
    - Q5 minus Q1 quintile spread (top score quintile vs bottom)
    - Hit rate (sign of return matches sign of score-z within regime)
    - Sample size and date span

Also computes a global (regime-agnostic) IC.

A regime with `n < MIN_REGIME_N` is reported as INSUFFICIENT (not computed)
to prevent misleading inference.

Based on the global IC, prints exactly one of four verdicts:

    PROMOTION_READY            global IC_30d >= +0.05 AND spread >= +3pp AND n >= 200
    REGIME_CONDITIONAL_ALPHA   regime ICs split sign; positive in some, negative in others
    ESCALATE_TIER_C            global IC <= 0 across all regimes
    HOLD_SHADOW                otherwise (insufficient evidence yet)

Output: `data/regime_ic_diagnostic.json` plus a console table.

Exit codes:
    0 - diagnostic written
    1 - empty / unusable dataset
    2 - error
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

OUTCOMES_PATH = REPO_ROOT / 'data' / 'historical_outcomes.csv'
DIAG_PATH = REPO_ROOT / 'data' / 'regime_ic_diagnostic.json'

MIN_REGIME_N = 50
IC_FLOOR = 0.05
SPREAD_PP_FLOOR = 3.0
SAMPLE_SIZE_FLOOR = 200


def _ic(df: pd.DataFrame, score_col: str, ret_col: str) -> dict:
    from scipy.stats import spearmanr
    sub = df.dropna(subset=[score_col, ret_col])
    if len(sub) < 30:
        return {'rho': None, 'p': None, 'n': len(sub)}
    rho, p = spearmanr(sub[score_col], sub[ret_col])
    if pd.isna(rho):
        return {'rho': None, 'p': None, 'n': len(sub)}
    return {'rho': round(float(rho), 4), 'p': round(float(p), 6), 'n': int(len(sub))}


def _quintile_spread(df: pd.DataFrame, score_col: str, ret_col: str) -> dict:
    sub = df.dropna(subset=[score_col, ret_col]).copy()
    if len(sub) < 25:
        return {'q1': None, 'q5': None, 'spread': None, 'n': len(sub)}
    try:
        sub['_q'] = pd.qcut(sub[score_col], 5, labels=False, duplicates='drop')
    except ValueError:
        return {'q1': None, 'q5': None, 'spread': None, 'n': len(sub)}
    q5 = sub[sub['_q'] == sub['_q'].max()][ret_col].mean()
    q1 = sub[sub['_q'] == sub['_q'].min()][ret_col].mean()
    return {
        'q1': round(float(q1), 3),
        'q5': round(float(q5), 3),
        'spread': round(float(q5 - q1), 3),
        'n': int(len(sub)),
    }


def _hit_rate(df: pd.DataFrame, score_col: str, ret_col: str) -> dict:
    sub = df.dropna(subset=[score_col, ret_col]).copy()
    if len(sub) < 30:
        return {'rate': None, 'n': len(sub)}
    median = sub[score_col].median()
    above = sub[sub[score_col] > median][ret_col]
    if len(above) == 0:
        return {'rate': None, 'n': len(sub)}
    rate = float((above > 0).mean() * 100)
    return {'rate': round(rate, 1), 'n': int(len(above))}


def _date_span(df: pd.DataFrame) -> dict:
    if 'date' not in df.columns or df['date'].isna().all():
        return {'first': None, 'last': None}
    dates = pd.to_datetime(df['date'], errors='coerce').dropna()
    if dates.empty:
        return {'first': None, 'last': None}
    return {'first': dates.min().strftime('%Y-%m-%d'),
            'last': dates.max().strftime('%Y-%m-%d')}


def _compute_for_subset(sub: pd.DataFrame, score_col: str = 'score') -> dict:
    if len(sub) < MIN_REGIME_N:
        return {
            'status': 'INSUFFICIENT',
            'n_rows': int(len(sub)),
            'reason': f'fewer than {MIN_REGIME_N} rows',
        }
    return {
        'status': 'OK',
        'n_rows': int(len(sub)),
        'date_span': _date_span(sub),
        'ic_30d': _ic(sub, score_col, 'return_30d'),
        'ic_7d': _ic(sub, score_col, 'return_7d'),
        'quintile_30d': _quintile_spread(sub, score_col, 'return_30d'),
        'hit_rate_30d': _hit_rate(sub, score_col, 'return_30d'),
    }


def _decide_verdict(global_blob: dict, regimes_blob: dict) -> dict:
    """Apply the four-way decision tree."""
    g_ic = (global_blob.get('ic_30d') or {}).get('rho')
    g_spread = (global_blob.get('quintile_30d') or {}).get('spread')
    g_n = (global_blob.get('quintile_30d') or {}).get('n') or 0

    # Outright PROMOTION_READY
    if (g_ic is not None and g_ic >= IC_FLOOR and
            g_spread is not None and g_spread >= SPREAD_PP_FLOOR and
            g_n >= SAMPLE_SIZE_FLOOR):
        return {
            'verdict': 'PROMOTION_READY',
            'reason': (f'Global IC_30d={g_ic} >= {IC_FLOOR}; spread={g_spread}pp '
                       f'>= {SPREAD_PP_FLOOR}pp; n={g_n} >= {SAMPLE_SIZE_FLOOR}'),
            'next_action': 'Run scripts/promote_v2.py to flip V2_SHADOW_MODE.',
        }

    # Regime-conditional: any positive AND any negative across REGIMES
    regime_ics = {}
    for rg, blob in regimes_blob.items():
        if not isinstance(blob, dict) or blob.get('status') != 'OK':
            continue
        rho = (blob.get('ic_30d') or {}).get('rho')
        if rho is not None:
            regime_ics[rg] = rho
    if regime_ics:
        positive = [rg for rg, ic in regime_ics.items() if ic >= IC_FLOOR]
        negative = [rg for rg, ic in regime_ics.items() if ic <= -IC_FLOOR]
        if positive and negative:
            return {
                'verdict': 'REGIME_CONDITIONAL_ALPHA',
                'reason': (f'IC sign splits across regimes: positive in {positive}, '
                           f'negative in {negative}'),
                'next_action': ('Plan a follow-up to gate v2 weights on regime; '
                                'do not promote globally yet.'),
            }

    # All regimes (with sufficient data) flat or negative
    if (g_ic is not None and g_ic <= 0
            and (not regime_ics or all(ic <= 0 for ic in regime_ics.values()))):
        return {
            'verdict': 'ESCALATE_TIER_C',
            'reason': (f'Global IC_30d={g_ic} <= 0 with no regime above {IC_FLOOR}. '
                       f'Existing components are not predictive.'),
            'next_action': ('Add Layer 1 forward-leaning signals (14d/60d momentum '
                            'acceleration, breadth, sector rotation) and re-calibrate.'),
        }

    return {
        'verdict': 'HOLD_SHADOW',
        'reason': 'Evidence is mixed or insufficient; v2 stays in shadow.',
        'next_action': ('Re-run scripts/build_historical_outcomes.py weekly and '
                        'check this diagnostic again.'),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--score-col', default='score',
                        help='Score column to test for predictiveness (default: score).')
    parser.add_argument('--no-write', action='store_true',
                        help='Print only; do not persist regime_ic_diagnostic.json.')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='[regime ic] %(message)s')

    if not OUTCOMES_PATH.exists():
        print(f'ERROR: {OUTCOMES_PATH} missing - run scripts/build_historical_outcomes.py first')
        return 2

    df = pd.read_csv(OUTCOMES_PATH)
    if df.empty:
        print('ERROR: historical_outcomes empty')
        return 1

    # Coerce types
    for c in ('score', 'return_7d', 'return_30d'):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df['regime'] = df.get('regime', pd.Series(['UNKNOWN'] * len(df))).fillna('UNKNOWN').astype(str).str.upper()

    print(f'Loaded {len(df)} rows from {OUTCOMES_PATH}')

    # Global
    global_blob = _compute_for_subset(df, score_col=args.score_col)

    # Per-regime (only the named regimes; UNKNOWN is informational)
    regimes_blob = {}
    for rg in ('BULL', 'BEAR', 'SIDEWAYS', 'UNKNOWN'):
        sub = df[df['regime'] == rg]
        regimes_blob[rg] = _compute_for_subset(sub, score_col=args.score_col)

    # Per-source diagnostics (informational): reports_pairwise vs bt_trades
    sources_blob = {}
    if 'data_source' in df.columns:
        for src in df['data_source'].dropna().unique():
            sub = df[df['data_source'] == src]
            sources_blob[str(src)] = _compute_for_subset(sub, score_col=args.score_col)

    verdict = _decide_verdict(global_blob, regimes_blob)

    output = {
        'updated': datetime.now().isoformat(),
        'score_col': args.score_col,
        'thresholds': {
            'min_regime_n': MIN_REGIME_N,
            'ic_floor': IC_FLOOR,
            'spread_pp_floor': SPREAD_PP_FLOOR,
            'sample_size_floor': SAMPLE_SIZE_FLOOR,
        },
        'global': global_blob,
        'regimes': regimes_blob,
        'sources': sources_blob,
        'verdict': verdict,
    }

    if not args.no_write:
        DIAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DIAG_PATH.write_text(json.dumps(output, indent=2))
        print(f'Wrote {DIAG_PATH}')

    # Console table
    print('\n=== Regime IC Diagnostic ===')

    def _fmt(blob: dict, label: str):
        status = blob.get('status', '?')
        if status == 'INSUFFICIENT':
            print(f'  {label:18s}  status=INSUFFICIENT (n={blob.get("n_rows", 0)})')
            return
        n = blob.get('n_rows', 0)
        ic30 = (blob.get('ic_30d') or {}).get('rho')
        ic7  = (blob.get('ic_7d')  or {}).get('rho')
        spr  = (blob.get('quintile_30d') or {}).get('spread')
        hit  = (blob.get('hit_rate_30d') or {}).get('rate')
        span = blob.get('date_span', {})
        print(f'  {label:18s}  n={n:5d}  IC_30d={ic30}  IC_7d={ic7}  '
              f'spread_30d={spr}pp  hit_30d={hit}%  span={span.get("first")}..{span.get("last")}')

    _fmt(global_blob, 'GLOBAL')
    for rg in ('BULL', 'BEAR', 'SIDEWAYS', 'UNKNOWN'):
        _fmt(regimes_blob[rg], rg)
    print('  --- by data_source ---')
    for src, blob in sources_blob.items():
        _fmt(blob, src)

    print('\n=== VERDICT ===')
    print(f"  {verdict['verdict']}")
    print(f"  reason:      {verdict['reason']}")
    print(f"  next_action: {verdict['next_action']}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
