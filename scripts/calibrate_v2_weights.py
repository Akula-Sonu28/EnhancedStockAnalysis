"""
Standalone runner: calibrate v2 weights from recommendation history.

Reads `data/recommendation_history.csv` (default) or `data/historical_outcomes.csv`
(when --source historical), runs the v2 IC blend calibration, and writes
`data/calibrated_weights_v2.json`. Intended for nightly cron invocation; safe
to run manually.

Sources:
  recommendation_history (default):
    Live engine outputs over the forward window. Requires the schema written by
    record_recommendation; small until 30+ days of forward returns mature.
  historical_outcomes:
    Combined dataset built by scripts/build_historical_outcomes.py - pairwise
    joins of historical reports + BT Trades. Bypasses the 30-day wait.

Exit codes:
    0 - calibration written
    1 - skipped (insufficient samples or no IC above floor)
    2 - error
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from hybrid_scoring_v2 import HybridOptimizedScoringEngineV2  # noqa: E402

HISTORY_PATH = REPO_ROOT / 'data' / 'recommendation_history.csv'
HISTORICAL_OUTCOMES_PATH = REPO_ROOT / 'data' / 'historical_outcomes.csv'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--source', choices=('recommendation_history', 'historical_outcomes'),
        default='recommendation_history',
        help='Input dataset for calibration. recommendation_history reads '
             'data/recommendation_history.csv (live engine, forward returns); '
             'historical_outcomes reads data/historical_outcomes.csv (reports + BT Trades).')
    parser.add_argument(
        '--per-regime', action='store_true',
        help='Tier C2 - in addition to (or instead of) the global weights, '
             'split the dataset by `regime` and write per-regime weight files '
             'data/calibrated_weights_v2_{BULL,BEAR,SIDEWAYS}.json. The runtime '
             'loader prefers the regime file matching the current market regime '
             'and falls back to the global file when a regime file is missing.')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='[v2 calibrate] %(message)s')

    try:
        from config import get_config
        _cfg = get_config()
        if str(getattr(_cfg, 'CALIBRATION_MODE', 'production')).lower() == 'diagnostic':
            print(
                'SKIPPED: CALIBRATION_MODE=diagnostic — IC report only, '
                'not overwriting calibrated_weights_v2.json. '
                'Run scripts/oracle_telemetry.py for live oracle metrics.'
            )
            return 0
    except Exception:
        pass

    src_path = HISTORY_PATH if args.source == 'recommendation_history' else HISTORICAL_OUTCOMES_PATH
    if not src_path.exists():
        print(f'ERROR: source file missing: {src_path}')
        if args.source == 'historical_outcomes':
            print('       run scripts/build_historical_outcomes.py first')
        return 2

    df = pd.read_csv(src_path)
    if df.empty:
        print(f'ERROR: source empty: {src_path}')
        return 2

    print(f'Loaded {len(df)} rows from {src_path} (source={args.source})')
    print(f"  return_7d non-null:  {df.get('return_7d', pd.Series(dtype=float)).notna().sum()}")
    print(f"  return_30d non-null: {df.get('return_30d', pd.Series(dtype=float)).notna().sum()}")

    # [v3 Layer 4] Per-component history schema. Prefer hybrid_* names (current
    # writer) and fall back to the earlier flat names if upgrading from a legacy
    # CSV. Without any of these, calibration will skip every component and exit 1.
    component_pairs = [
        ('fundamental_quality', 'hybrid_fundamental_quality', 'fundamental_score'),
        ('momentum_technical',  'hybrid_momentum_technical',  'momentum_score'),
        ('volume_strength',     'hybrid_volume_strength',     'volume_composite_score'),
        ('multi_timeframe',     'hybrid_multi_timeframe',     'mtf_composite_score'),
        ('ml_signal',           'hybrid_ml_signal',           'ml_expected_return'),
        ('risk_adjustment',     'hybrid_risk_adjustment',     'risk_adjusted_score'),
        # [Rule 3a] Growth + Value factors (8-component calibration).
        ('growth',              'hybrid_growth',              'growth_score'),
        ('value',               'hybrid_value',               'value_score'),
    ]
    present = []
    missing = []
    for weight_key, primary, fallback in component_pairs:
        used = primary if primary in df.columns else (fallback if fallback in df.columns else None)
        if used is None:
            missing.append(f'{weight_key} (looked for {primary} / {fallback})')
        else:
            present.append(f'{weight_key} <- {used}')
    print(f'  component columns present: {present}')
    if missing:
        print(f'  component columns missing: {missing}')
        print('  (calibration will return SKIPPED unless at least one component has data)')

    weights = HybridOptimizedScoringEngineV2.calibrate_weights_from_outcomes(df)
    if weights is None:
        print('SKIPPED: insufficient data or all ICs below floor - no calibrated_weights_v2.json written')
        if not args.per_regime:
            return 1

    if weights is not None:
        print('SUCCESS: GLOBAL calibrated weights:')
        for k, v in weights.items():
            sign = '+' if v >= 0 else '-'
            print(f'  {k:>22s}: {sign}{abs(v):.4f}')

    # Tier C2: per-regime calibration produces three additional files.
    if args.per_regime:
        per_regime = HybridOptimizedScoringEngineV2.calibrate_weights_per_regime_from_outcomes(df)
        print(f'\nPER-REGIME calibration ({len(per_regime)} regimes evaluated):')
        any_written = False
        for rg in HybridOptimizedScoringEngineV2._SUPPORTED_REGIMES:
            w = per_regime.get(rg)
            if w is None:
                print(f'  {rg:9s}: SKIPPED (insufficient data)')
                continue
            any_written = True
            path = HybridOptimizedScoringEngineV2._REGIME_WEIGHT_PATH_TEMPLATE.format(regime=rg)
            print(f'  {rg:9s}: written -> {path}')
            for k, v in w.items():
                sign = '+' if v >= 0 else '-'
                print(f'      {k:>22s}: {sign}{abs(v):.4f}')
        if not any_written and weights is None:
            return 1

    print(f'\n(source={args.source})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
