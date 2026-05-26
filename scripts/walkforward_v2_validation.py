"""Walk-forward out-of-sample validation of v2 calibrated weights.

This is the only honest way to ask "do v2 weights generalise to data they were
not trained on?" - because the historical IC of +0.16 we computed earlier was
IN-SAMPLE (calibrated and tested on the same 5,835 rows).

Algorithm:
    Read `data/historical_outcomes.csv`. Sort chronologically. For each of
    several train / test splits (single 80/20 + 5-fold expanding window):

      1. Calibrate v2 signed weights on the TRAIN slice using the same algorithm
         as `HybridOptimizedScoringEngineV2.calibrate_weights_from_outcomes`.
      2. Apply those weights to the TEST slice's hybrid_* components using the
         deviation-from-neutral formula (50 + sum (component_i - 50) * w_i).
      3. Spearman-correlate the synthesised v2 score against the realised
         `return_30d` in the TEST slice.
      4. Compute v1 IC on the same TEST slice for baseline.

    The verdict at the end is the OUT-OF-SAMPLE evidence about whether v2's
    calibrated weights are predictive on data they never saw.

Reports:
    Global out-of-sample IC (single 80/20 split, primary number).
    Per-fold IC mean +/- stderr (5-fold robustness check).
    Per-regime out-of-sample IC (does any regime show real generalisation?).
    Decisive verdict written to data/walkforward_v2_validation.json.

    --mode fixed-turbo-mtf: skip step 1; score each TEST slice with production
    Turbo MTF weights from config (DUAL_STRATEGY_PROFILES). Writes
    data/walkforward_v2_validation_fixed_turbo.json.

Exit codes:
    0 - validation complete (regardless of verdict; promotion decision is downstream)
    1 - insufficient data
    2 - error
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

OUTCOMES_PATH = REPO_ROOT / 'data' / 'historical_outcomes.csv'
RESULT_PATH = REPO_ROOT / 'data' / 'walkforward_v2_validation.json'
RESULT_PATH_FIXED_TURBO = REPO_ROOT / 'data' / 'walkforward_v2_validation_fixed_turbo.json'

MODES = ('calibrate', 'fixed-turbo-mtf')

# Strict gating thresholds (same as the strict promotion check)
IC_FLOOR = 0.05
SPREAD_PP_FLOOR = 3.0
SAMPLE_SIZE_FLOOR = 200
N_FOLDS_DEFAULT = 5
TRAIN_FRAC_PRIMARY = 0.80

HYBRID_COLS = (
    'hybrid_fundamental_quality',
    'hybrid_momentum_technical',
    'hybrid_volume_strength',
    'hybrid_multi_timeframe',
    'hybrid_ml_signal',
    'hybrid_risk_adjustment',
    'hybrid_growth',
    'hybrid_value',
)
WEIGHT_KEY_FROM_COMPONENT = {
    'hybrid_fundamental_quality': 'fundamental_quality',
    'hybrid_momentum_technical':  'momentum_technical',
    'hybrid_volume_strength':     'volume_strength',
    'hybrid_multi_timeframe':     'multi_timeframe',
    'hybrid_ml_signal':           'ml_signal',
    'hybrid_risk_adjustment':     'risk_adjustment',
    'hybrid_growth':              'growth',
    'hybrid_value':               'value',
}


def _load_fixed_turbo_weights(weights_path: Path = None) -> dict:
    """Load production Turbo MTF weights (no per-fold recalibration)."""
    if weights_path is not None:
        blob = json.loads(weights_path.read_text())
        w = blob.get('weights') or blob
        return {k: float(v) for k, v in w.items()}

    from config import get_config
    profiles = getattr(get_config(), 'DUAL_STRATEGY_PROFILES', {}) or {}
    turbo = profiles.get('turbo_mtf') or {}
    weights = turbo.get('weights')
    if weights:
        return {k: float(v) for k, v in weights.items()}

    fallback = REPO_ROOT / 'data' / 'calibrated_weights_v2.json'
    if fallback.exists():
        blob = json.loads(fallback.read_text())
        w = blob.get('weights') or blob
        return {k: float(v) for k, v in w.items()}
    return {}


def _ic(series_a: pd.Series, series_b: pd.Series) -> tuple:
    """Spearman IC. Returns (rho, p, n)."""
    from scipy.stats import spearmanr
    df = pd.concat([series_a, series_b], axis=1).dropna()
    if len(df) < 30:
        return None, None, len(df)
    rho, p = spearmanr(df.iloc[:, 0], df.iloc[:, 1])
    if pd.isna(rho):
        return None, None, len(df)
    return float(rho), float(p), int(len(df))


def _quintile_spread(score: pd.Series, ret: pd.Series) -> tuple:
    df = pd.concat([score, ret], axis=1).dropna()
    df.columns = ['s', 'r']
    if len(df) < 25:
        return None, None, None, len(df)
    try:
        df['_q'] = pd.qcut(df['s'], 5, labels=False, duplicates='drop')
    except ValueError:
        return None, None, None, len(df)
    q5 = df[df['_q'] == df['_q'].max()]['r'].mean()
    q1 = df[df['_q'] == df['_q'].min()]['r'].mean()
    return float(q5), float(q1), float(q5 - q1), int(len(df))


def _calibrate_on(train: pd.DataFrame) -> dict:
    """Reuse the v2 calibrator on a subset. Does NOT persist - returns weights
    in memory. Uses HybridOptimizedScoringEngineV2's algorithm so train/test
    split mirrors production behaviour."""
    from hybrid_scoring_v2 import HybridOptimizedScoringEngineV2

    # Route persistence to a throwaway temp file so the real calibrated_weights_v2.json
    # is untouched during walk-forward.
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        _orig = HybridOptimizedScoringEngineV2._CALIBRATED_WEIGHTS_PATH
        HybridOptimizedScoringEngineV2._CALIBRATED_WEIGHTS_PATH = os.path.join(td, 'wf.json')
        try:
            weights = HybridOptimizedScoringEngineV2.calibrate_weights_from_outcomes(train)
        finally:
            HybridOptimizedScoringEngineV2._CALIBRATED_WEIGHTS_PATH = _orig
    return weights or {}


def _synthesise_v2_score(test_df: pd.DataFrame, weights: dict) -> pd.Series:
    """Apply weights to per-row hybrid_* components using the deviation-from-
    neutral formula: v2 = 50 + sum (component_i - 50) * weight_i. Rows missing
    all components return NaN."""
    deviation = pd.Series(0.0, index=test_df.index)
    has_any = pd.Series(False, index=test_df.index)
    for comp_col, weight_key in WEIGHT_KEY_FROM_COMPONENT.items():
        if comp_col not in test_df.columns:
            continue
        w = float(weights.get(weight_key, 0.0))
        if w == 0.0:
            continue
        comp = pd.to_numeric(test_df[comp_col], errors='coerce')
        has_any = has_any | comp.notna()
        deviation = deviation.add(((comp - 50.0) * w).fillna(0.0), fill_value=0.0)
    score_v2 = (50.0 + deviation).clip(lower=0.0, upper=100.0)
    return score_v2.where(has_any, other=float('nan'))


def _evaluate_split_fixed(test: pd.DataFrame, weights: dict, label: str,
                          n_train: int = 0) -> dict:
    """Apply fixed weights to the TEST slice only (no train calibration)."""
    if not weights:
        return {
            'label': label,
            'status': 'WEIGHTS_MISSING',
            'n_train': int(n_train),
            'n_test': int(len(test)),
        }
    v2_test = _synthesise_v2_score(test, weights)
    ret_col = 'return_30d'
    if ret_col not in test.columns:
        return {'label': label, 'status': 'NO_RETURN_30D'}
    ret = pd.to_numeric(test[ret_col], errors='coerce')
    v1_test = pd.to_numeric(test.get('score'), errors='coerce') if 'score' in test.columns else None

    v2_rho, v2_p, v2_n = _ic(v2_test, ret)
    v2_q5, v2_q1, v2_spread, _ = _quintile_spread(v2_test, ret)

    if v1_test is not None:
        v1_rho, v1_p, v1_n = _ic(v1_test, ret)
        v1_q5, v1_q1, v1_spread, _ = _quintile_spread(v1_test, ret)
    else:
        v1_rho = v1_p = v1_n = None
        v1_q5 = v1_q1 = v1_spread = None

    return {
        'label': label,
        'status': 'OK',
        'n_train': int(n_train),
        'n_test': int(len(test)),
        'weights_train': {k: round(float(v), 4) for k, v in weights.items()},
        'v2': {
            'ic_30d': v2_rho, 'ic_p': v2_p, 'ic_n': v2_n,
            'q5': v2_q5, 'q1': v2_q1, 'spread_pp': v2_spread,
        },
        'v1': {
            'ic_30d': v1_rho, 'ic_p': v1_p, 'ic_n': v1_n,
            'q5': v1_q5, 'q1': v1_q1, 'spread_pp': v1_spread,
        },
        'edge_v2_minus_v1': (v2_rho - v1_rho) if (v2_rho is not None and v1_rho is not None) else None,
    }


def _evaluate_split(train: pd.DataFrame, test: pd.DataFrame, label: str) -> dict:
    """Calibrate on train, evaluate v2 forward IC on test. Returns metrics dict."""
    weights = _calibrate_on(train)
    if not weights:
        return {
            'label': label,
            'status': 'CALIBRATION_FAILED',
            'n_train': int(len(train)),
            'n_test': int(len(test)),
        }
    v2_test = _synthesise_v2_score(test, weights)
    ret_col = 'return_30d'
    if ret_col not in test.columns:
        return {'label': label, 'status': 'NO_RETURN_30D'}
    ret = pd.to_numeric(test[ret_col], errors='coerce')
    v1_test = pd.to_numeric(test.get('score'), errors='coerce') if 'score' in test.columns else None

    v2_rho, v2_p, v2_n = _ic(v2_test, ret)
    v2_q5, v2_q1, v2_spread, _ = _quintile_spread(v2_test, ret)

    if v1_test is not None:
        v1_rho, v1_p, v1_n = _ic(v1_test, ret)
        v1_q5, v1_q1, v1_spread, _ = _quintile_spread(v1_test, ret)
    else:
        v1_rho = v1_p = v1_n = None
        v1_q5 = v1_q1 = v1_spread = None

    return {
        'label': label,
        'status': 'OK',
        'n_train': int(len(train)),
        'n_test': int(len(test)),
        'weights_train': {k: round(float(v), 4) for k, v in weights.items()},
        'v2': {
            'ic_30d': v2_rho, 'ic_p': v2_p, 'ic_n': v2_n,
            'q5': v2_q5, 'q1': v2_q1, 'spread_pp': v2_spread,
        },
        'v1': {
            'ic_30d': v1_rho, 'ic_p': v1_p, 'ic_n': v1_n,
            'q5': v1_q5, 'q1': v1_q1, 'spread_pp': v1_spread,
        },
        'edge_v2_minus_v1': (v2_rho - v1_rho) if (v2_rho is not None and v1_rho is not None) else None,
    }


def _per_regime_eval(train: pd.DataFrame, test: pd.DataFrame,
                     fixed_weights: dict = None) -> dict:
    """Evaluate test per regime. Calibrate on train unless fixed_weights supplied."""
    if fixed_weights is not None:
        weights = fixed_weights
    else:
        weights = _calibrate_on(train)
    if not weights:
        return {}
    out = {}
    for rg in ('BULL', 'BEAR', 'SIDEWAYS'):
        sub = test[test['regime'].astype(str).str.upper() == rg]
        if len(sub) < 50:
            out[rg] = {'status': 'INSUFFICIENT', 'n': int(len(sub))}
            continue
        v2 = _synthesise_v2_score(sub, weights)
        ret = pd.to_numeric(sub['return_30d'], errors='coerce')
        rho, p, n = _ic(v2, ret)
        q5, q1, spread, _ = _quintile_spread(v2, ret)
        out[rg] = {
            'status': 'OK',
            'n': int(len(sub)),
            'ic_30d': rho, 'ic_p': p,
            'q5': q5, 'q1': q1, 'spread_pp': spread,
        }
    return out


def _verdict(primary: dict, folds_summary: dict, regime: dict) -> dict:
    """Reduce all evidence into a single verdict string + reason."""
    p_ic = (primary.get('v2') or {}).get('ic_30d')
    p_spread = (primary.get('v2') or {}).get('spread_pp')
    p_n = (primary.get('v2') or {}).get('ic_n') or 0
    mean_fold_ic = folds_summary.get('mean_ic') if folds_summary else None

    # Check regime split
    regime_positive = [
        rg for rg, blob in (regime or {}).items()
        if isinstance(blob, dict) and blob.get('status') == 'OK'
        and (blob.get('ic_30d') or 0) >= IC_FLOOR
    ]
    regime_negative = [
        rg for rg, blob in (regime or {}).items()
        if isinstance(blob, dict) and blob.get('status') == 'OK'
        and (blob.get('ic_30d') or 0) <= -IC_FLOOR
    ]

    if (p_ic is not None and p_ic >= IC_FLOOR
            and p_spread is not None and p_spread >= SPREAD_PP_FLOOR
            and p_n >= SAMPLE_SIZE_FLOOR
            and (mean_fold_ic is None or mean_fold_ic >= 0)):
        return {
            'verdict': 'PROMOTE',
            'reason': (f'Primary out-of-sample IC={p_ic:.3f} >= {IC_FLOOR}; '
                       f'spread={p_spread:.2f}pp >= {SPREAD_PP_FLOOR}; '
                       f'n_test={p_n} >= {SAMPLE_SIZE_FLOOR}; '
                       f'5-fold mean IC={mean_fold_ic}'),
            'next_action': 'Re-calibrate on full dataset, persist weights, run promote_v2.py.',
        }
    if regime_positive and regime_negative:
        return {
            'verdict': 'REGIME_KEYED',
            'reason': (f'Out-of-sample IC splits by regime: positive in '
                       f'{regime_positive}, negative in {regime_negative}.'),
            'next_action': ('Promote regime-keyed weights only for regimes with '
                            'positive out-of-sample IC; keep others in shadow.'),
        }
    if (p_ic is not None and p_ic <= -IC_FLOOR
            and (not regime_positive)):
        return {
            'verdict': 'ESCALATE_TIER_C',
            'reason': (f'Primary out-of-sample IC={p_ic:.3f} below -{IC_FLOOR}; '
                       f'no regime shows positive generalisation. The current 6 '
                       f'components do not contain forward alpha.'),
            'next_action': ('Build Layer 1 forward-leaning signals: 14d/60d '
                            'momentum acceleration, breadth, sector rotation.'),
        }
    return {
        'verdict': 'HOLD_SHADOW',
        'reason': (f'Out-of-sample evidence inconclusive. '
                   f'Primary IC={p_ic}, mean fold IC={mean_fold_ic}, regimes positive={regime_positive}.'),
        'next_action': ('Keep v2 in shadow; re-run weekly as more data accumulates.'),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--mode', choices=MODES, default='calibrate',
        help='calibrate: re-fit weights each train slice (default). '
             'fixed-turbo-mtf: apply production Turbo MTF weights to each test slice.',
    )
    parser.add_argument('--train-frac', type=float, default=TRAIN_FRAC_PRIMARY,
                        help=f'Primary train fraction (default {TRAIN_FRAC_PRIMARY})')
    parser.add_argument('--folds', type=int, default=N_FOLDS_DEFAULT,
                        help='Number of expanding-window folds for robustness')
    parser.add_argument('--weights-file', type=str, default='',
                        help='Optional JSON weights file (fixed-turbo-mtf mode only)')
    parser.add_argument('--no-write', action='store_true',
                        help='Print only; do not persist JSON results')
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format='[wf] %(message)s')
    fixed_mode = args.mode == 'fixed-turbo-mtf'
    fixed_weights = None
    if fixed_mode:
        wpath = Path(args.weights_file) if args.weights_file else None
        fixed_weights = _load_fixed_turbo_weights(wpath)
        if not fixed_weights:
            print('ERROR: fixed-turbo-mtf mode requires Turbo MTF weights in config or data/calibrated_weights_v2.json')
            return 2
        print('Mode: FIXED TURBO MTF (no per-fold recalibration)')
        print('Weights:', json.dumps({k: round(v, 4) for k, v in fixed_weights.items()}, sort_keys=True))
    else:
        print('Mode: CALIBRATE (re-fit weights on each train slice)')

    if not OUTCOMES_PATH.exists():
        print(f'ERROR: {OUTCOMES_PATH} missing - run scripts/build_historical_outcomes.py first')
        return 2

    df = pd.read_csv(OUTCOMES_PATH)
    if df.empty:
        print('ERROR: historical_outcomes empty')
        return 1
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Keep only rows with at least one hybrid_* component populated AND return_30d.
    has_components = df[list(HYBRID_COLS)].notna().any(axis=1)
    has_ret = pd.to_numeric(df['return_30d'], errors='coerce').notna()
    df = df[has_components & has_ret].reset_index(drop=True)
    print(f'Eligible rows (components + return_30d): {len(df)}')
    if len(df) < 200:
        print(f'WARN: <200 eligible rows; results will be noisy')
    if len(df) < 60:
        print('ERROR: too few rows for any meaningful train/test split')
        return 1

    print(f'Date span: {df["date"].min().date()} - {df["date"].max().date()}')

    # === Primary 80/20 chronological split ===
    split_idx = int(len(df) * args.train_frac)
    train = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:].copy()
    print(f'\nPrimary split: train n={len(train)} ({train["date"].min().date()}..{train["date"].max().date()}); '
          f'test n={len(test)} ({test["date"].min().date()}..{test["date"].max().date()})')
    if fixed_mode:
        primary = _evaluate_split_fixed(test, fixed_weights, label='80/20', n_train=len(train))
    else:
        primary = _evaluate_split(train, test, label='80/20')

    # === Expanding-window folds ===
    print(f'\nRunning {args.folds}-fold expanding-window validation...')
    folds = []
    fold_size = len(df) // (args.folds + 1)
    for f in range(args.folds):
        train_end = fold_size * (f + 1)
        test_end = fold_size * (f + 2)
        tr = df.iloc[:train_end].copy()
        te = df.iloc[train_end:test_end].copy()
        if len(tr) < 100 or len(te) < 50:
            continue
        if fixed_mode:
            m = _evaluate_split_fixed(te, fixed_weights, label=f'fold_{f+1}', n_train=len(tr))
        else:
            m = _evaluate_split(tr, te, label=f'fold_{f+1}')
        folds.append(m)
        ic = (m.get('v2') or {}).get('ic_30d')
        print(f'  fold {f+1}: n_train={len(tr)} n_test={len(te)} v2_IC_30d={ic}')

    fold_ics = [(f.get('v2') or {}).get('ic_30d') for f in folds
                if f.get('status') == 'OK' and (f.get('v2') or {}).get('ic_30d') is not None]
    fold_summary = {
        'n_folds': len(fold_ics),
        'mean_ic': round(float(np.mean(fold_ics)), 4) if fold_ics else None,
        'std_ic': round(float(np.std(fold_ics)), 4) if fold_ics else None,
        'min_ic': round(float(np.min(fold_ics)), 4) if fold_ics else None,
        'max_ic': round(float(np.max(fold_ics)), 4) if fold_ics else None,
    }

    # === Per-regime on primary split ===
    print('\nPer-regime out-of-sample IC (primary split):')
    regime = _per_regime_eval(train, test, fixed_weights=fixed_weights if fixed_mode else None)
    for rg, blob in regime.items():
        if blob.get('status') == 'OK':
            print(f'  {rg}: n={blob["n"]}, IC={blob.get("ic_30d")}, '
                  f'spread={blob.get("spread_pp")}pp')
        else:
            print(f'  {rg}: {blob.get("status")} (n={blob.get("n")})')

    verdict = _verdict(primary, fold_summary, regime)

    out = {
        'updated': datetime.now().isoformat(),
        'mode': args.mode,
        'eligible_rows': int(len(df)),
        'date_span': {
            'first': df['date'].min().strftime('%Y-%m-%d'),
            'last':  df['date'].max().strftime('%Y-%m-%d'),
        },
        'primary_80_20': primary,
        'folds': folds,
        'folds_summary': fold_summary,
        'per_regime': regime,
        'verdict': verdict,
    }
    if fixed_mode:
        out['fixed_weights'] = {k: round(float(v), 4) for k, v in fixed_weights.items()}

    print('\n' + '=' * 70)
    print('PRIMARY 80/20 OUT-OF-SAMPLE VERDICT')
    print('=' * 70)
    v2 = primary.get('v2', {})
    v1 = primary.get('v1', {})
    print(f"  n_train={primary['n_train']}, n_test={primary['n_test']}")
    print(f"  v1 IC_30d:   {v1.get('ic_30d')} (p={v1.get('ic_p')})")
    print(f"  v2 IC_30d:   {v2.get('ic_30d')} (p={v2.get('ic_p')})")
    print(f"  v1 spread:   {v1.get('spread_pp')}pp")
    print(f"  v2 spread:   {v2.get('spread_pp')}pp")
    print(f"  edge v2-v1:  {primary.get('edge_v2_minus_v1')}")

    print('\n' + '=' * 70)
    print(f'{args.folds}-FOLD EXPANDING-WINDOW SUMMARY')
    print('=' * 70)
    if fold_summary['n_folds']:
        print(f"  mean IC: {fold_summary['mean_ic']} +/- {fold_summary['std_ic']}")
        print(f"  range:   [{fold_summary['min_ic']}, {fold_summary['max_ic']}]")
    else:
        print('  no folds completed')

    print('\n' + '=' * 70)
    print('VERDICT')
    print('=' * 70)
    print(f"  {verdict['verdict']}")
    print(f"  reason:      {verdict['reason']}")
    print(f"  next_action: {verdict['next_action']}")

    if not args.no_write:
        dest = RESULT_PATH_FIXED_TURBO if fixed_mode else RESULT_PATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=2, default=str))
        print(f'\nWrote {dest}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
