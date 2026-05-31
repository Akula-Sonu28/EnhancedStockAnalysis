#!/usr/bin/env python3
"""Sanity-check market regime detection against live Nifty / India VIX data.

Runs MarketRegimeDetector, recomputes signals for audit, shows VMQ day-3 gate
status, and optionally spot-checks historical dates.

Usage:
    python3 scripts/verify_regime.py
    python3 scripts/verify_regime.py --period-days 180 --spot-checks 5
    python3 scripts/verify_regime.py --date 2026-05-29
    python3 scripts/verify_regime.py --json-out data/regime_verification.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config import get_config  # noqa: E402
from market_regime_detector import MarketRegimeDetector  # noqa: E402
from src.vmq_strategy import day3_validation_active  # noqa: E402


DEFAULT_SPOT_DATES = [
    '2024-09-27',
    '2025-01-15',
    '2025-03-15',
    '2026-05-29',
]


def _label_from_score(score: float, bull_thr: float = 0.5, bear_thr: float = -0.5) -> str:
    if score > bull_thr:
        return 'BULL'
    if score < bear_thr:
        return 'BEAR'
    return 'SIDEWAYS'


def _manual_audit(det: MarketRegimeDetector, period_days: int) -> Dict[str, Any]:
    """Recompute regime signals on Nifty window (transparent audit trail)."""
    nifty = det._get_index_data(det.nifty_symbol, period_days)
    if nifty is None or len(nifty) < 50:
        return {'status': 'NO_DATA'}

    trend = float(det._calculate_trend_signal(nifty))
    momentum = float(det._calculate_momentum_signal(nifty))
    volatility = float(det._calculate_volatility_signal(nifty))
    breadth = float(det._calculate_breadth_signal(nifty))
    vix = float(det._get_vix_level())

    weights = dict(det.base_weights)
    if vix > 25:
        weights['volatility'] += 0.15
        weights['trend'] -= 0.15

    raw = (
        trend * weights['trend']
        + momentum * weights['momentum']
        + volatility * weights['volatility']
        + breadth * weights['breadth']
    )
    raw = float(max(-1.0, min(1.0, raw)))
    adjusted = raw
    if vix > 35:
        adjusted = min(adjusted, 0.0)
    elif vix > 30:
        adjusted = min(adjusted, 0.3)

    close = nifty['Close']
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma100 = float(close.rolling(100).mean().iloc[-1])
    cur = float(close.iloc[-1])
    n = len(close)
    ret_1m = (cur / float(close.iloc[max(0, n - 21)]) - 1.0) * 100.0
    ret_3m = (cur / float(close.iloc[max(0, n - 63)]) - 1.0) * 100.0

    return {
        'status': 'OK',
        'nifty_close': cur,
        'above_ma20': cur > ma20,
        'above_ma50': cur > ma50,
        'above_ma100': cur > ma100,
        'nifty_change_1m_pct': ret_1m,
        'nifty_change_3m_pct': ret_3m,
        'trend_signal': trend,
        'momentum_signal': momentum,
        'volatility_signal': volatility,
        'breadth_signal': breadth,
        'weights': weights,
        'raw_regime_score': raw,
        'vix_adjusted_score': adjusted,
        'simple_label': _label_from_score(adjusted),
        'vix_level': vix,
    }


def _vmq_day3_status(regime: str, vix_level: Optional[float], cfg) -> Dict[str, Any]:
    enabled = bool(getattr(cfg, 'VMQ_DAY3_ENABLED', False))
    active = day3_validation_active(regime, vix_level, cfg) if enabled else False
    gated = bool(getattr(cfg, 'VMQ_DAY3_REGIME_GATED', True))
    return {
        'vmq_day3_enabled': enabled,
        'vmq_day3_regime_gated': gated,
        'day3_validation_active': active,
        'active_regimes': str(getattr(cfg, 'VMQ_DAY3_ACTIVE_REGIMES', 'bear,high_vol')),
        'vix_min_for_high_vol': float(getattr(cfg, 'VMQ_DAY3_VIX_MIN', 25.0)),
        'interpretation': (
            'Early day-3/day-5 exits ON'
            if active
            else 'Early day-3/day-5 exits OFF (hard/swing/trail still ON)'
        ),
    }


def _spot_check(det: MarketRegimeDetector, date_str: str) -> Optional[Dict[str, Any]]:
    """Historical check using Nifty slice + backtest simplified label."""
    import yfinance as yf
    from backtest_engine import BacktestEngine

    end = pd.Timestamp(date_str) + pd.Timedelta(days=1)
    hist = yf.Ticker('^NSEI').history(start='2023-01-01', end=end.strftime('%Y-%m-%d'))
    if hist.empty:
        return None
    sub = hist[hist.index <= date_str].tail(220)
    if len(sub) < 50:
        return None

    backtest_regime = BacktestEngine._detect_regime_from_data(sub)
    trend = float(det._calculate_trend_signal(sub))
    momentum = float(det._calculate_momentum_signal(sub))
    volatility = float(det._calculate_volatility_signal(sub))
    breadth = float(det._calculate_breadth_signal(sub))
    score = float(max(-1.0, min(1.0, trend * 0.35 + momentum * 0.25 + volatility * 0.20 + breadth * 0.20)))
    close = sub['Close']
    n = len(close)
    ret_3m = (float(close.iloc[-1]) / float(close.iloc[max(0, n - 63)]) - 1.0) * 100.0

    return {
        'date': date_str,
        'nifty_close': float(close.iloc[-1]),
        'nifty_change_3m_pct': ret_3m,
        'signals': {'trend': trend, 'momentum': momentum, 'volatility': volatility, 'breadth': breadth},
        'nifty_only_score': score,
        'nifty_only_label': _label_from_score(score),
        'backtest_label': backtest_regime,
    }


def _print_live_report(result: Dict[str, Any], audit: Dict[str, Any], vmq: Dict[str, Any]) -> None:
    print('=' * 72)
    print('  REGIME VERIFICATION (live MarketRegimeDetector)')
    print('=' * 72)
    print(f"  Timestamp          : {result.get('analysis_timestamp', datetime.now().isoformat())}")
    print(f"  Regime             : {result.get('regime')} ({result.get('regime_strength')})")
    print(f"  Regime score       : {float(result.get('regime_score', 0)):.4f}")
    print(f"  Confidence         : {float(result.get('regime_confidence', 0)):.4f}")
    print(f"  Index agreement    : {result.get('index_agreement')}")
    print(f"  VIX                : {float(result.get('vix_level', 0)):.2f}  ({result.get('market_sentiment')})")
    print(f"  Risk level         : {result.get('risk_level')}")
    print(f"  Nifty close        : {float(result.get('current_nifty', 0)):,.2f}")
    print(f"  Nifty 1m / 3m      : {float(result.get('nifty_change_1m', 0)):+.2f}% / "
          f"{float(result.get('nifty_change_3m', 0)):+.2f}%")

    if audit.get('status') == 'OK':
        print('\n  --- Signal audit (manual recompute) ---')
        print(f"  vs MA20/50/100     : {audit['above_ma20']}/{audit['above_ma50']}/{audit['above_ma100']}")
        print(f"  Trend / Mom / Vol / Breadth : "
              f"{audit['trend_signal']:+.2f} / {audit['momentum_signal']:+.2f} / "
              f"{audit['volatility_signal']:+.2f} / {audit['breadth_signal']:+.2f}")
        print(f"  Raw score          : {audit['raw_regime_score']:+.4f}")
        print(f"  VIX-adj score      : {audit['vix_adjusted_score']:+.4f}  →  {audit['simple_label']}")
        live_regime = str(result.get('regime', '')).upper()
        audit_label = audit['simple_label']
        match = 'OK' if live_regime == audit_label else f'MISMATCH (live={live_regime}, audit={audit_label})'
        print(f"  Live vs audit      : {match}")

    print('\n  --- VMQ day-3/day-5 gate ---')
    print(f"  Regime gated       : {vmq['vmq_day3_regime_gated']}")
    print(f"  Day-3/5 enabled    : {vmq.get('vmq_day3_enabled', False)}")
    print(f"  Day-3/5 active now : {vmq['day3_validation_active']}")
    print(f"  Meaning            : {vmq['interpretation']}")
    print('=' * 72)


def _print_spot_checks(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    print('\n  HISTORICAL SPOT CHECKS (Nifty-only score; live detector may differ)')
    print('  ' + '-' * 68)
    for row in rows:
        sig = row['signals']
        print(
            f"  {row['date']}  Nifty {row['nifty_close']:,.0f}  "
            f"3m {row['nifty_change_3m_pct']:+.1f}%  "
            f"score {row['nifty_only_score']:+.2f} → {row['nifty_only_label']:8s}  "
            f"(backtest {row['backtest_label']})  "
            f"[t/m/v/b {sig['trend']:+.1f}/{sig['momentum']:+.1f}/"
            f"{sig['volatility']:+.1f}/{sig['breadth']:+.1f}]"
        )


def build_report(
    period_days: int = 180,
    spot_dates: Optional[List[str]] = None,
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = get_config()
    det = MarketRegimeDetector()

    if as_of_date:
        spot = _spot_check(det, as_of_date)
        return {
            'mode': 'historical',
            'as_of_date': as_of_date,
            'spot_check': spot,
            'generated': datetime.now().isoformat(timespec='seconds'),
        }

    result = det.detect_regime(period_days=period_days)
    audit = _manual_audit(det, period_days)
    vmq = _vmq_day3_status(str(result.get('regime', '')), result.get('vix_level'), cfg)

    spots: List[Dict[str, Any]] = []
    for ds in spot_dates or DEFAULT_SPOT_DATES:
        row = _spot_check(det, ds)
        if row:
            spots.append(row)

    return {
        'mode': 'live',
        'generated': datetime.now().isoformat(timespec='seconds'),
        'period_days': period_days,
        'regime': result,
        'audit': audit,
        'vmq_day3': vmq,
        'spot_checks': spots,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify market regime vs Nifty/VIX data')
    parser.add_argument('--period-days', type=int, default=180, help='Lookback for live detector')
    parser.add_argument('--date', type=str, default=None, help='Historical spot-check date YYYY-MM-DD')
    parser.add_argument('--no-spot-checks', action='store_true',
                        help='Skip historical spot-check table')
    parser.add_argument('--json-out', type=str, default='',
                        help='Write JSON report path (e.g. data/regime_verification.json)')
    args = parser.parse_args()

    spot_dates = [] if args.no_spot_checks or args.date else DEFAULT_SPOT_DATES

    report = build_report(
        period_days=args.period_days,
        spot_dates=spot_dates,
        as_of_date=args.date,
    )

    if args.date:
        spot = report.get('spot_check')
        if not spot:
            print(f'ERROR: insufficient Nifty data for {args.date}')
            return 2
        _print_spot_checks([spot])
    else:
        _print_live_report(report['regime'], report['audit'], report['vmq_day3'])
        _print_spot_checks(report.get('spot_checks', []))

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
        print(f"\n  JSON: {out.resolve()}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
