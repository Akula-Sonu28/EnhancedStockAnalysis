"""Build a combined historical outcomes dataset from on-disk reports + BT Trades.

This bypasses the forward-30-day wait for v2 calibration. Two sub-builders are
unioned into one CSV:

  Sub-dataset A - reports_pairwise:
    Walk `reports/Enhanced_Stock_Report_*.xlsx`, pick the latest report per
    distinct date, then for each (date_T, symbol) in `Complete Data` look for
    the same symbol in a later report at T+7d / T+30d (with +/-2d tolerance).
    Fall back to yfinance when no neighbouring report exists. Writes per-symbol
    `hybrid_*` components when present (older reports have a partial schema).

  Sub-dataset B - bt_trades:
    Reads the `BT Trades` sheet from the latest report (a cumulative simulator
    log). Per-component scores are NULL (BT only carries the blended score),
    so component-level IC calibration will skip these rows. Returns aggregate
    score IC fully.

Output: `data/historical_outcomes.csv` with columns
    date, symbol, score, hybrid_fundamental_quality, hybrid_momentum_technical,
    hybrid_volume_strength, hybrid_multi_timeframe, hybrid_ml_signal,
    hybrid_risk_adjustment, current_price, regime, return_7d, return_30d,
    data_source

Exit codes:
    0 - dataset written
    1 - empty dataset (no eligible rows)
    2 - error
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

REPORTS_DIR = REPO_ROOT / 'reports'
DATA_DIR = REPO_ROOT / 'data'
OUTCOMES_PATH = DATA_DIR / 'historical_outcomes.csv'
PRICE_CACHE_DIR = DATA_DIR / 'cache' / 'historical_prices'

HYBRID_COLS = (
    'hybrid_fundamental_quality',
    'hybrid_momentum_technical',
    'hybrid_volume_strength',
    'hybrid_multi_timeframe',
    'hybrid_ml_signal',
    'hybrid_risk_adjustment',
    # [Rule 3a] Growth + Value factors. Absent in pre-Phase-C reports - the
    # writer fills NaN for those rows, which becomes IC=0 / weight=0 at
    # calibration time (skipped by MIN_ABS_IC gate). Present in post-Phase-C
    # reports once the recalibration plan is rolled out.
    'hybrid_growth',
    'hybrid_value',
)
SCORE_FALLBACKS = ('final_blended_score', 'overall_score',
                   'overall_score_with_value', 'hybrid_overall_score')

# Tolerance windows around T+7d / T+30d when matching a neighbouring report.
WINDOW_7D = (5, 9)
WINDOW_30D = (27, 33)

REPORT_FNAME_RE = re.compile(r'Enhanced_Stock_Report_(\d{8})_(\d{6})\.xlsx$')


def _parse_report_date(path: Path) -> Optional[datetime]:
    m = REPORT_FNAME_RE.search(path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), '%Y%m%d')
    except Exception:
        return None


def _latest_report_per_date() -> dict:
    """Return {date_str: latest_report_path} keyed by YYYYMMDD."""
    by_date: dict = {}
    for p in sorted(REPORTS_DIR.glob('Enhanced_Stock_Report_*.xlsx')):
        m = REPORT_FNAME_RE.search(p.name)
        if not m:
            continue
        date_str = m.group(1)
        time_str = m.group(2)
        # Keep the latest time stamp per date.
        prior = by_date.get(date_str)
        if prior is None or time_str > prior[1]:
            by_date[date_str] = (p, time_str)
    return {d: meta[0] for d, meta in by_date.items()}


def _read_complete_data(path: Path) -> Optional[pd.DataFrame]:
    """Read Complete Data sheet; tolerate older reports with smaller schema."""
    try:
        df = pd.read_excel(path, 'Complete Data')
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        logging.warning(f'  cannot read Complete Data from {path.name}: {e}')
        return None


def _resolve_score(df: pd.DataFrame) -> Optional[pd.Series]:
    """First non-empty score-like column among SCORE_FALLBACKS."""
    for c in SCORE_FALLBACKS:
        if c in df.columns:
            ser = pd.to_numeric(df[c], errors='coerce')
            if ser.notna().any():
                return ser
    return None


def _resolve_regime(df: pd.DataFrame) -> pd.Series:
    if 'market_regime' in df.columns:
        return df['market_regime'].astype(str).str.upper().fillna('UNKNOWN')
    return pd.Series(['UNKNOWN'] * len(df), index=df.index)


def _yfinance_close(symbol: str, target_date: datetime, max_lookback_days: int = 5) -> Optional[float]:
    """Look up close price for symbol on target_date with up to N business-day
    lookback. Cached on disk per-(symbol, date)."""
    PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = f"{symbol.upper()}_{target_date.strftime('%Y%m%d')}.json"
    cache_path = PRICE_CACHE_DIR / cache_key
    if cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text())
            return payload.get('close')
        except Exception:
            pass
    try:
        import yfinance as yf
    except ImportError:
        return None
    end = target_date + pd.Timedelta(days=2)
    start = target_date - pd.Timedelta(days=max_lookback_days)
    try:
        for attempt in range(3):
            try:
                df = yf.download(f'{symbol}.NS', start=start.strftime('%Y-%m-%d'),
                                 end=end.strftime('%Y-%m-%d'),
                                 progress=False, auto_adjust=True)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        if df is None or df.empty or 'Close' not in df.columns:
            cache_path.write_text(json.dumps({'close': None}))
            return None
        # Use last available close on or before target_date
        df = df[df.index <= pd.Timestamp(target_date) + pd.Timedelta(days=2)]
        if df.empty:
            cache_path.write_text(json.dumps({'close': None}))
            return None
        close = float(df['Close'].iloc[-1])
        cache_path.write_text(json.dumps({'close': close, 'as_of': df.index[-1].strftime('%Y-%m-%d')}))
        return close
    except Exception as e:
        logging.debug(f'  yfinance lookup failed for {symbol}@{target_date.date()}: {e}')
        return None


def _find_forward_price(symbol: str, target_dt: datetime,
                        window_days: tuple, dated_reports: dict,
                        complete_cache: dict, allow_yfinance: bool) -> Optional[float]:
    """Return the symbol's price from a later report whose date is within
    `window_days = (lo, hi)` around target_dt; else fall back to yfinance.
    `dated_reports` is {datetime: report_path}; `complete_cache` is the per-path
    Complete-Data cache."""
    lo_date = target_dt + pd.Timedelta(days=window_days[0])
    hi_date = target_dt + pd.Timedelta(days=window_days[1])
    candidate_paths = []
    for d, p in dated_reports.items():
        if pd.Timestamp(lo_date) <= pd.Timestamp(d) <= pd.Timestamp(hi_date):
            candidate_paths.append((d, p))
    candidate_paths.sort(key=lambda x: abs((x[0] - target_dt).days))
    for d, p in candidate_paths:
        df = complete_cache.get(p)
        if df is None:
            continue
        if 'symbol' not in df.columns or 'current_price' not in df.columns:
            continue
        row = df[df['symbol'].astype(str).str.upper() == symbol.upper()]
        if row.empty:
            continue
        px = pd.to_numeric(row.iloc[0].get('current_price'), errors='coerce')
        if pd.notna(px) and px > 0:
            return float(px)
    if allow_yfinance:
        # Best-effort: target_dt + midpoint of window
        mid = target_dt + pd.Timedelta(days=(window_days[0] + window_days[1]) // 2)
        return _yfinance_close(symbol, mid)
    return None


def _build_reports_pairwise(allow_yfinance: bool) -> pd.DataFrame:
    """Pairwise-join Complete Data across reports to compute realised
    forward returns. Returns DataFrame with the canonical schema."""
    if not REPORTS_DIR.exists():
        logging.warning(f'no reports/ dir at {REPORTS_DIR}')
        return pd.DataFrame()

    latest = _latest_report_per_date()
    if not latest:
        logging.warning('no reports found')
        return pd.DataFrame()

    print(f'  reports_pairwise: {len(latest)} unique-date reports detected')

    # Cache Complete Data per file once.
    dated_reports: dict = {}
    complete_cache: dict = {}
    for date_str, path in latest.items():
        try:
            dt = datetime.strptime(date_str, '%Y%m%d')
        except Exception:
            continue
        cd = _read_complete_data(path)
        if cd is None:
            continue
        dated_reports[dt] = path
        complete_cache[path] = cd

    rows = []
    for dt, path in sorted(dated_reports.items()):
        cd = complete_cache.get(path)
        if cd is None or 'symbol' not in cd.columns or 'current_price' not in cd.columns:
            continue
        score_ser = _resolve_score(cd)
        if score_ser is None:
            continue
        regime_ser = _resolve_regime(cd)
        for idx, srow in cd.iterrows():
            sym_raw = srow.get('symbol')
            if pd.isna(sym_raw):
                continue
            sym = str(sym_raw).upper().strip()
            if not sym:
                continue
            px = pd.to_numeric(srow.get('current_price'), errors='coerce')
            if pd.isna(px) or px <= 0:
                continue
            score = pd.to_numeric(score_ser.iloc[idx], errors='coerce') if idx < len(score_ser) else None
            if pd.isna(score):
                continue
            row = {
                'date': dt.strftime('%Y-%m-%d'),
                'symbol': sym,
                'score': float(score),
                'current_price': float(px),
                'regime': str(regime_ser.iloc[idx]) if idx < len(regime_ser) else 'UNKNOWN',
            }
            for c in HYBRID_COLS:
                v = pd.to_numeric(srow.get(c), errors='coerce') if c in cd.columns else None
                row[c] = None if pd.isna(v) else float(v)
            row['return_7d'] = None
            row['return_30d'] = None
            row['data_source'] = 'reports_pairwise'
            # Compute forward returns
            for horizon, win, key in (('7d', WINDOW_7D, 'return_7d'),
                                      ('30d', WINDOW_30D, 'return_30d')):
                fwd = _find_forward_price(sym, dt, win, dated_reports,
                                          complete_cache, allow_yfinance)
                if fwd is not None and fwd > 0:
                    row[key] = float((fwd - px) / px * 100.0)  # %, matches BT 'return_pct'
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        print('  reports_pairwise: no eligible rows')
    else:
        non_null_30 = df['return_30d'].notna().sum()
        non_null_7 = df['return_7d'].notna().sum()
        print(f'  reports_pairwise: {len(df)} rows, return_7d nn={non_null_7}, '
              f'return_30d nn={non_null_30}')
    return df


def _build_bt_trades() -> pd.DataFrame:
    """Read BT Trades from the latest report (cumulative simulator log)."""
    paths = sorted(REPORTS_DIR.glob('Enhanced_Stock_Report_*.xlsx'))
    if not paths:
        return pd.DataFrame()
    latest_path = paths[-1]
    try:
        bt = pd.read_excel(latest_path, 'BT Trades')
    except Exception as e:
        logging.warning(f'  bt_trades: cannot read sheet from {latest_path.name}: {e}')
        return pd.DataFrame()
    if bt.empty:
        return pd.DataFrame()
    print(f'  bt_trades: {len(bt)} trades from {latest_path.name}')
    rows = []
    for _, r in bt.iterrows():
        sym = str(r.get('symbol') or '').upper().strip()
        if not sym:
            continue
        ret_pct = pd.to_numeric(r.get('return_pct'), errors='coerce')
        score = pd.to_numeric(r.get('score'), errors='coerce')
        entry = pd.to_numeric(r.get('entry'), errors='coerce')
        rebal = r.get('rebalance_date')
        if isinstance(rebal, str):
            try:
                rebal_dt = pd.Timestamp(rebal).to_pydatetime()
            except Exception:
                continue
        elif isinstance(rebal, (datetime, pd.Timestamp)):
            rebal_dt = pd.Timestamp(rebal).to_pydatetime()
        else:
            continue
        if pd.isna(score) or pd.isna(ret_pct):
            continue
        regime = str(r.get('regime') or 'UNKNOWN').upper()
        row = {
            'date': rebal_dt.strftime('%Y-%m-%d'),
            'symbol': sym,
            'score': float(score),
            'current_price': float(entry) if pd.notna(entry) and entry > 0 else None,
            'regime': regime,
            # BT does not record per-component scores - leave them null.
        }
        for c in HYBRID_COLS:
            row[c] = None
        # Treat the BT 30d-equivalent return (typically monthly rebalance) as both 30d and 7d/4 proxy.
        row['return_30d'] = float(ret_pct)
        row['return_7d'] = float(ret_pct) / 4.0  # rough proxy for the 7d horizon
        row['data_source'] = 'bt_trades'
        rows.append(row)
    df = pd.DataFrame(rows)
    print(f'  bt_trades: {len(df)} eligible rows produced')
    return df


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-yfinance', action='store_true',
                        help='Disable yfinance fallback for missing forward prices')
    parser.add_argument('--reports-only', action='store_true',
                        help='Skip BT Trades extraction')
    parser.add_argument('--bt-only', action='store_true',
                        help='Skip reports-pairwise extraction')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='[hist build] %(message)s')

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f'Building historical outcomes -> {OUTCOMES_PATH}')
    print(f'  yfinance fallback: {"disabled" if args.no_yfinance else "enabled"}')

    parts = []
    if not args.bt_only:
        parts.append(_build_reports_pairwise(allow_yfinance=not args.no_yfinance))
    if not args.reports_only:
        parts.append(_build_bt_trades())

    parts = [p for p in parts if p is not None and not p.empty]
    if not parts:
        print('ERROR: empty dataset (no eligible rows from either source)')
        return 1

    combined = pd.concat(parts, ignore_index=True)
    expected_cols = ['date', 'symbol', 'score', *HYBRID_COLS,
                     'current_price', 'regime', 'return_7d', 'return_30d', 'data_source']
    for c in expected_cols:
        if c not in combined.columns:
            combined[c] = None
    combined = combined[expected_cols]

    combined.to_csv(OUTCOMES_PATH, index=False)
    print(f'\nWrote {len(combined)} rows to {OUTCOMES_PATH}')
    print('  per-source breakdown:')
    for src, n in combined['data_source'].value_counts().items():
        print(f'    {src:20s}: {n}')
    print('  per-regime breakdown:')
    for rg, n in combined['regime'].fillna('UNKNOWN').value_counts().items():
        print(f'    {rg:12s}: {n}')
    nn7 = combined['return_7d'].notna().sum()
    nn30 = combined['return_30d'].notna().sum()
    print(f'  realised return availability: 7d={nn7}, 30d={nn30}')
    nn_components = combined[list(HYBRID_COLS)].notna().any(axis=1).sum()
    print(f'  rows with at least one hybrid_* component: {nn_components}/{len(combined)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
