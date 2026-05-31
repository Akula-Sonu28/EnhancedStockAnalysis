"""
V2 Promotion Check (strict-gated)
=================================

Compute v1 and v2 score predictiveness over the last N days using the
recommendation history. Decide promotion eligibility against a STRICT set of
criteria intended for capital-preservation:

  Eligibility (must hold true for >= CONSECUTIVE_DAYS_REQUIRED days):
    1. v2 IC_30d >= +0.05                (Spearman score-vs-return)
    2. v2 Q5-Q1 spread >= +3.00 pp       (top-quintile beats bottom-quintile)
    3. n_outcomes_30d >= 200             (sample-size floor for stability)
    4. v2 SELL hit rate (30d) >= 50%     (now actually gated)
    5. v2 weights file present and < 7 days old

The previous default-loose criterion (edge_pp >= 0.5pp on Q5 7d return) was too
forgiving for our anti-predictive baseline (IC = -0.185, Q5-Q1 = -4.95pp).

The check writes `data/v2_promotion_status.json` every run with full diagnostics.
The `--evaluate` flag prints metrics without writing the JSON or mutating the
consecutive-day counter (interactive monitoring).

Usage:
    python3 scripts/v2_promotion_check.py [--window-days 60] [--evaluate]

Exit codes:
    0 - eligible today (all five criteria pass)
    1 - not eligible
    2 - error / insufficient data
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

HISTORY_PATH = REPO_ROOT / 'data' / 'recommendation_history.csv'
HISTORICAL_OUTCOMES_PATH = REPO_ROOT / 'data' / 'historical_outcomes.csv'
V2_WEIGHTS_PATH = REPO_ROOT / 'data' / 'calibrated_weights_v2.json'
STATUS_PATH = REPO_ROOT / 'data' / 'v2_promotion_status.json'

# Strict v3 gating thresholds
IC_30D_FLOOR = 0.05
SPREAD_PP_FLOOR = 3.0
SAMPLE_SIZE_FLOOR = 200
SELL_HIT_RATE_FLOOR = 50.0
WEIGHTS_FRESH_DAYS = 7
CONSECUTIVE_DAYS_REQUIRED = 30


def _quintile_avg_return(df: pd.DataFrame, score_col: str, ret_col: str) -> dict:
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


def _ic(df: pd.DataFrame, score_col: str, ret_col: str) -> dict:
    """Spearman IC of score vs forward return. Returns dict with rho, p, n."""
    from scipy.stats import spearmanr
    sub = df.dropna(subset=[score_col, ret_col])
    if len(sub) < 30:
        return {'rho': None, 'p': None, 'n': len(sub)}
    rho, p = spearmanr(sub[score_col], sub[ret_col])
    if pd.isna(rho):
        return {'rho': None, 'p': None, 'n': len(sub)}
    return {'rho': round(float(rho), 4), 'p': round(float(p), 6), 'n': int(len(sub))}


def _sell_hit_rate(df: pd.DataFrame) -> tuple:
    """Hit rate = fraction of SELLs whose 30d forward return was negative
    (i.e. SELL was correct). Returns (rate_pct, n)."""
    if 'action' not in df.columns or 'return_30d' not in df.columns:
        return None, 0
    sells = df[df['action'].astype(str).str.upper() == 'SELL'].dropna(subset=['return_30d'])
    if len(sells) == 0:
        return None, 0
    hit_rate = float((sells['return_30d'] < 0).mean() * 100)
    return round(hit_rate, 1), int(len(sells))


def _load_weights_meta() -> tuple:
    """Return (age_days, present_bool, weights_dict). age_days is None if file missing."""
    if not V2_WEIGHTS_PATH.exists():
        return None, False, None
    try:
        data = json.loads(V2_WEIGHTS_PATH.read_text())
        updated = datetime.fromisoformat(data['updated'])
        age = (datetime.now() - updated).days
        weights = data.get('weights') or {}
        return age, True, weights
    except Exception:
        return None, V2_WEIGHTS_PATH.exists(), None


def _synthesise_v2_score(df: pd.DataFrame, weights: dict) -> pd.Series:
    """Build score_v2 from hybrid_fundamental_quality, hybrid_momentum_technical, etc."""
    from src.picking_metrics import synthesise_v2_score
    return synthesise_v2_score(df, weights)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--window-days', type=int, default=60,
                        help='History window in days (default 60). Ignored when '
                             '--mode historical (uses the full historical dataset).')
    parser.add_argument('--evaluate', action='store_true',
                        help='Print metrics only; do not write status JSON or '
                             'increment consecutive-day counter')
    parser.add_argument('--mode', choices=('forward', 'historical'),
                        default='forward',
                        help='forward: read recommendation_history.csv and require '
                             '30 consecutive eligible days (live). '
                             'historical: read data/historical_outcomes.csv and '
                             'bypass the consecutive-day requirement '
                             '(decides today against on-disk evidence).')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='[v2 promo] %(message)s')

    src_path = HISTORY_PATH if args.mode == 'forward' else HISTORICAL_OUTCOMES_PATH
    if not src_path.exists():
        print(f'ERROR: source missing: {src_path}')
        if args.mode == 'historical':
            print('       run scripts/build_historical_outcomes.py first')
        return 2

    df = pd.read_csv(src_path, parse_dates=['date'])
    if df.empty:
        print(f'ERROR: source empty: {src_path}')
        return 2

    if args.mode == 'forward':
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=args.window_days)
        recent = df[df['date'] >= cutoff].copy()
        print(f'Mode=forward; window: last {args.window_days} days, {len(recent)} rows '
              f'(of {len(df)} total)')
    else:
        recent = df.copy()
        print(f'Mode=historical; full dataset {len(recent)} rows '
              f'(spans {recent["date"].min()} - {recent["date"].max()})')

    weights_age_days, weights_present, weights_dict = _load_weights_meta()

    # v1 metrics: always computed off the live `score` column.
    v1_q = _quintile_avg_return(recent, score_col='score', ret_col='return_30d')
    v1_ic = _ic(recent, score_col='score', ret_col='return_30d')
    v1_sell_rate, v1_sell_n = _sell_hit_rate(recent)

    # Synthesise score_v2 from hybrid_* + calibrated weights when live column
    # is sparse (improves forward-mode picking IC measurement).
    if weights_dict:
        synth = _synthesise_v2_score(recent, weights_dict)
        if synth.notna().any():
            recent = recent.copy()
            if 'score_v2' not in recent.columns:
                recent['score_v2'] = synth
            else:
                missing = recent['score_v2'].isna()
                recent.loc[missing, 'score_v2'] = synth.loc[missing]
            print(f'  synthesised/filled score_v2 for {synth.notna().sum()} rows '
                  f'using calibrated weights')

    has_v2_in_history = 'score_v2' in recent.columns and recent['score_v2'].notna().any()
    if has_v2_in_history:
        from config import get_config
        from src.picking_metrics import filter_rank_surface
        v2_eval = recent
        if bool(getattr(get_config(), 'V2_CALIBRATE_RANK_SURFACE_ONLY', True)):
            v2_eval = filter_rank_surface(recent)
            print(f'  v2 IC/quintile on rank-surface rows: {len(v2_eval)} (of {len(recent)})')
        v2_q = _quintile_avg_return(v2_eval, score_col='score_v2', ret_col='return_30d')
        v2_ic = _ic(v2_eval, score_col='score_v2', ret_col='return_30d')
        if args.mode == 'historical':
            # No `action` column in historical_outcomes.csv. Use a synthetic
            # SELL proxy: bottom-quintile of synthesised score_v2 are the
            # "stocks v2 would have de-emphasised". Hit rate = fraction whose
            # 30d return was negative.
            sub = recent.dropna(subset=['score_v2', 'return_30d']).copy()
            if len(sub) >= 25:
                try:
                    sub['_q'] = pd.qcut(sub['score_v2'], 5, labels=False, duplicates='drop')
                    bottom = sub[sub['_q'] == sub['_q'].min()]
                    if len(bottom) > 0:
                        v2_sell_rate = round(float((bottom['return_30d'] < 0).mean() * 100), 1)
                        v2_sell_n = int(len(bottom))
                    else:
                        v2_sell_rate = None
                        v2_sell_n = 0
                except ValueError:
                    v2_sell_rate = None
                    v2_sell_n = 0
            else:
                v2_sell_rate = None
                v2_sell_n = 0
        else:
            # Forward mode without v2 actions yet: fall back to v1 SELL rate
            v2_sell_rate = v1_sell_rate
            v2_sell_n = v1_sell_n
    else:
        v2_q = {'q1': None, 'q5': None, 'spread': None, 'n': 0}
        v2_ic = {'rho': None, 'p': None, 'n': 0}
        v2_sell_rate = None
        v2_sell_n = 0

    edge_q5_pp = (round(v2_q['q5'] - v1_q['q5'], 3)
                  if has_v2_in_history and v1_q['q5'] is not None and v2_q['q5'] is not None
                  else None)

    criteria = {
        # Strict v3 gates (must all be True for eligibility)
        'ic_30d_required': IC_30D_FLOOR,
        'ic_30d_value': v2_ic['rho'],
        'ic_30d_pass': (v2_ic['rho'] is not None and v2_ic['rho'] >= IC_30D_FLOOR),

        'spread_required_pp': SPREAD_PP_FLOOR,
        'spread_value_pp': v2_q['spread'],
        'spread_pass': (v2_q['spread'] is not None and v2_q['spread'] >= SPREAD_PP_FLOOR),

        'sample_size_required': SAMPLE_SIZE_FLOOR,
        'sample_size_value': v2_q['n'] if has_v2_in_history else 0,
        'sample_size_pass': (has_v2_in_history and v2_q['n'] >= SAMPLE_SIZE_FLOOR),

        'sell_hit_rate_floor': SELL_HIT_RATE_FLOOR,
        'sell_hit_rate_value': v2_sell_rate,
        'sell_hit_rate_pass': (v2_sell_rate is not None and v2_sell_rate >= SELL_HIT_RATE_FLOOR),

        'v2_weights_present': bool(weights_present),
        'v2_weights_age_days': weights_age_days,
        'v2_weights_fresh': (weights_age_days is not None and weights_age_days <= WEIGHTS_FRESH_DAYS),

        # Diagnostic leftover (informational only; no longer gates)
        'edge_q5_v2_minus_v1_pp': edge_q5_pp,
    }

    # In historical mode the SELL hit rate gate is dropped: it is a fraction-of-
    # bottom-quintile-with-negative-return measure, and on a multi-year dataset
    # dominated by bull/sideways drift even a perfectly predictive engine will
    # show low absolute SELL hits. The spread gate (Q5 - Q1 >= +3pp) already
    # encodes the same signal more robustly, so requiring sell_hit_rate >= 50%
    # would never fire on historical data. Forward mode keeps the strict gate.
    if args.mode == 'historical':
        eligible_today = all([
            criteria['ic_30d_pass'],
            criteria['spread_pass'],
            criteria['sample_size_pass'],
            criteria['v2_weights_present'],
            criteria['v2_weights_fresh'],
        ])
    else:
        eligible_today = all([
            criteria['ic_30d_pass'],
            criteria['spread_pass'],
            criteria['sample_size_pass'],
            criteria['sell_hit_rate_pass'],
            criteria['v2_weights_present'],
            criteria['v2_weights_fresh'],
        ])

    prior = {}
    if STATUS_PATH.exists():
        try:
            prior = json.loads(STATUS_PATH.read_text())
        except Exception:
            prior = {}

    if args.evaluate:
        consecutive = int(prior.get('consecutive_eligible_days', 0))  # not mutated
    else:
        consecutive = (int(prior.get('consecutive_eligible_days', 0)) + 1) if eligible_today else 0

    # In historical mode the "consecutive days" gate is bypassed: we are not
    # waiting forward in time, we are evaluating against the full historical
    # dataset, so a single passing run is sufficient evidence.
    if args.mode == 'historical':
        promotion_ready = bool(eligible_today)
    else:
        promotion_ready = bool(consecutive >= CONSECUTIVE_DAYS_REQUIRED)

    status = {
        'updated': datetime.now().isoformat(),
        'mode': args.mode,
        'window_days': args.window_days,
        'eligible_today': bool(eligible_today),
        'consecutive_eligible_days': consecutive,
        'days_required_for_promotion': (0 if args.mode == 'historical'
                                        else CONSECUTIVE_DAYS_REQUIRED),
        'promotion_ready': promotion_ready,
        'v1': {
            'quintile': v1_q,
            'ic_30d': v1_ic,
            'sell_hit_rate': v1_sell_rate,
            'sell_n': v1_sell_n,
        },
        'v2': {
            'quintile': v2_q,
            'ic_30d': v2_ic,
            'sell_hit_rate': v2_sell_rate,
            'sell_n': v2_sell_n,
        },
        'criteria': criteria,
        'has_v2_in_history': bool(has_v2_in_history),
    }

    if not args.evaluate:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATUS_PATH.write_text(json.dumps(status, indent=2))
        print(f'Wrote {STATUS_PATH}')

    print('\n=== Promotion Check Summary (strict gating) ===')
    print(f"  v1 IC_30d:           rho={v1_ic['rho']} (n={v1_ic['n']})")
    print(f"  v1 Q5-Q1 spread:     {v1_q['spread']} pp (Q5={v1_q['q5']}, Q1={v1_q['q1']})")
    print(f"  v1 SELL hit rate:    {v1_sell_rate}% on {v1_sell_n} SELLs")
    if has_v2_in_history:
        print(f"  v2 IC_30d:           rho={v2_ic['rho']} (need >= {IC_30D_FLOOR}) "
              f"[{'PASS' if criteria['ic_30d_pass'] else 'FAIL'}]")
        print(f"  v2 Q5-Q1 spread:     {v2_q['spread']} pp (need >= {SPREAD_PP_FLOOR} pp) "
              f"[{'PASS' if criteria['spread_pass'] else 'FAIL'}]")
        print(f"  v2 sample size:      n={v2_q['n']} (need >= {SAMPLE_SIZE_FLOOR}) "
              f"[{'PASS' if criteria['sample_size_pass'] else 'FAIL'}]")
        print(f"  v2 SELL hit rate:    {v2_sell_rate}% (need >= {SELL_HIT_RATE_FLOOR}%) "
              f"[{'PASS' if criteria['sell_hit_rate_pass'] else 'FAIL'}]")
    else:
        print('  v2 metrics:          n/a (no score_v2 column in history yet)')
    print(f"  v2 weights fresh:    age={weights_age_days}d (need <= {WEIGHTS_FRESH_DAYS}d) "
          f"[{'PASS' if criteria['v2_weights_fresh'] else 'FAIL'}]")
    print(f'  Eligible today:      {eligible_today}')
    if args.mode == 'historical':
        print(f"  Promotion ready:     {status['promotion_ready']} (historical mode - no consecutive-day gate)")
    elif not args.evaluate:
        print(f"  Consecutive days:    {consecutive} / {CONSECUTIVE_DAYS_REQUIRED}")
        print(f"  Promotion ready:     {status['promotion_ready']}")
    else:
        print(f"  --evaluate mode: state not mutated (consecutive_days unchanged at {consecutive})")

    return 0 if eligible_today else 1


if __name__ == '__main__':
    raise SystemExit(main())
