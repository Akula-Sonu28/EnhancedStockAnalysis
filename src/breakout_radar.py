"""
Breakout Radar — Path 2 (Balanced) coil / ignition scanner.

Finds AIAENG-style setups: strong MTF + moderate momentum coiling under resistance,
or same-day volume ignition. Used for Excel 'Breakout Radar' sheet and fast-track entry.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from src.vmq_strategy import _f, _cfg


TIER_IGNITE = 'B-IGNITE'
TIER_READY = 'A+-READY'
TIER_COIL = 'A-COIL'
TIER_MOM_POP = 'C-MOM-POP'


def _g(row: Dict[str, Any], *keys, default=None):
    for k in keys:
        v = row.get(k)
        if v is not None and pd.notna(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return default


def _dist_20d_high_pct(row: Dict[str, Any]) -> Optional[float]:
    d = row.get('dist_20d_high_pct')
    if d is not None and pd.notna(d):
        return float(d)
    cp = _g(row, 'current_price')
    h = _g(row, 'high_20d', 'enhanced_20d_high')
    if cp and h and h > 0:
        return float(max(0.0, (h - cp) / h * 100))
    h52 = _g(row, '52_week_high')
    if cp and h52 and h52 > 0:
        return float(max(0.0, (h52 - cp) / h52 * 100))
    return None


def classify_breakout_tier(row: Dict[str, Any], cfg=None) -> Tuple[str, float, List[str]]:
    """Return (tier, score, reasons). Empty tier = not on radar."""
    blended = _g(row, 'final_blended_score', 'overall_score_with_value', default=0)
    v2 = _g(row, 'hybrid_overall_score_v2', 'score_v2', default=0)
    mom = _g(row, 'hybrid_momentum_technical', default=0)
    mtf = _g(row, 'hybrid_multi_timeframe', default=0)
    fund = _g(row, 'hybrid_fundamental_quality', default=0)
    rsi = _g(row, 'real_rsi', 'enhanced_rsi_14', default=50)
    chg1 = _g(row, 'enhanced_price_change_1d', 'price_change_1d', default=0)
    chg5 = _g(row, 'enhanced_price_change_5d', 'price_change_5d', default=0)
    volr = _g(row, 'enhanced_volume_ratio', 'volume_ratio', default=1.0)
    wick = _g(row, 'rejection_wick_pct', default=0)
    dist20 = _dist_20d_high_pct(row)

    rsi_max = _f(_cfg(cfg, 'TURBO_ENTRY_RSI_MAX', 75.0))
    ignite_vol = _f(_cfg(cfg, 'BREAKOUT_IGNITE_VOL_RATIO', 2.5))
    ignite_ret = _f(_cfg(cfg, 'BREAKOUT_IGNITE_1D_MIN', 2.5))
    coil_dist = _f(_cfg(cfg, 'BREAKOUT_COIL_DIST_20D_MAX', 4.0))

    reasons: List[str] = []

    if rsi > rsi_max + 5:
        return '', 0.0, [f'RSI {rsi:.0f} too extended']

    # Tier B — ignition day (AIAENG May 26 replay)
    if (
        chg1 >= ignite_ret
        and volr >= ignite_vol
        and mtf >= 65
        and blended >= 55
        and rsi <= rsi_max + 2
        and wick <= _f(_cfg(cfg, 'TURBO_ENTRY_REJECTION_WICK_PCT', 8.0))
    ):
        score = volr * 12 + chg1 * 2 + mtf * 0.25
        reasons = [f'ignition +{chg1:.1f}% vol {volr:.1f}x mtf {mtf:.0f}']
        return TIER_IGNITE, score, reasons

    # Tier A+ — about to flip BUY, tight to highs
    if (
        58 <= blended <= 66
        and 50 <= mom <= 58
        and mtf >= 70
        and fund >= 65
        and rsi <= 72
        and 0.9 <= volr <= 2.5
        and dist20 is not None
        and dist20 <= coil_dist
    ):
        score = mtf * 0.35 + v2 * 0.25 + mom * 0.2 + max(0, 4 - dist20) * 5
        reasons = [f'coil ready {dist20:.1f}% from 20d high mtf {mtf:.0f}']
        return TIER_READY, score, reasons

    # Tier A — classic coil (AIAENG May 25)
    if (
        52 <= blended <= 64
        and 42 <= mom <= 54
        and mtf >= 65
        and fund >= 68
        and rsi <= 68
        and 0.8 <= volr <= 2.2
        and abs(chg1) <= 2.5
        and dist20 is not None
        and dist20 <= coil_dist + 1
    ):
        score = mtf * 0.4 + fund * 0.15 + max(0, 5 - dist20) * 4
        reasons = [f'coil {dist20:.1f}% below high mom {mom:.0f} mtf {mtf:.0f}']
        return TIER_COIL, score, reasons

    # Tier C — value + MTF, needs mom pop
    if (
        fund >= 75
        and 48 <= mom <= 56
        and mtf >= 68
        and v2 >= 60
        and 60 <= blended <= 72
        and rsi <= 70
    ):
        score = mtf * 0.3 + v2 * 0.3 + fund * 0.1
        reasons = [f'value+mtf mom pop needed fund {fund:.0f} mom {mom:.0f}']
        return TIER_MOM_POP, score, reasons

    return '', 0.0, []


def enrich_row_with_radar_fields(row: Dict[str, Any], hist=None, cfg=None) -> Dict[str, Any]:
    """Add dist_20d_high_pct and radar tier fields to a stock row."""
    out = dict(row)
    if hist is not None and not getattr(hist, 'empty', True):
        try:
            h = hist.dropna(subset=['Close'])
            if len(h) >= 20:
                cp = float(h['Close'].iloc[-1])
                h20 = float(h['High'].tail(20).max())
                out['high_20d'] = h20
                out['dist_20d_high_pct'] = float(max(0.0, (h20 - cp) / h20 * 100)) if h20 > 0 else 0.0
        except Exception:
            pass
    tier, score, reasons = classify_breakout_tier(out, cfg)
    out['breakout_tier'] = tier
    out['breakout_radar_score'] = score
    out['breakout_radar_reason'] = '; '.join(reasons)
    return out


def scan_dataframe(
    df: pd.DataFrame,
    held_symbols: Optional[Set[str]] = None,
    cfg=None,
    max_rows: int = 25,
) -> pd.DataFrame:
    """Scan universe for breakout radar candidates (excludes current holdings)."""
    if df is None or df.empty:
        return pd.DataFrame()
    held = {str(s).upper() for s in (held_symbols or set())}
    rows: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        d = r.to_dict()
        sym = str(d.get('symbol', '')).upper()
        if not sym or sym in held:
            continue
        rec = str(d.get('final_recommendation', ''))
        if 'SELL' in rec.upper() and 'BUY' not in rec.upper():
            continue
        tier, score, reasons = classify_breakout_tier(d, cfg)
        if not tier:
            continue
        rows.append({
            'symbol': sym,
            'company_name': d.get('company_name', sym),
            'breakout_tier': tier,
            'breakout_radar_score': round(score, 1),
            'breakout_radar_reason': '; '.join(reasons),
            'final_blended_score': _g(d, 'final_blended_score'),
            'hybrid_overall_score_v2': _g(d, 'hybrid_overall_score_v2'),
            'hybrid_momentum_technical': _g(d, 'hybrid_momentum_technical'),
            'hybrid_multi_timeframe': _g(d, 'hybrid_multi_timeframe'),
            'hybrid_fundamental_quality': _g(d, 'hybrid_fundamental_quality'),
            'real_rsi': _g(d, 'real_rsi', 'enhanced_rsi_14'),
            'enhanced_price_change_1d': _g(d, 'enhanced_price_change_1d', 'price_change_1d'),
            'enhanced_price_change_5d': _g(d, 'enhanced_price_change_5d', 'price_change_5d'),
            'enhanced_volume_ratio': _g(d, 'enhanced_volume_ratio', 'volume_ratio', default=1.0),
            'dist_20d_high_pct': _dist_20d_high_pct(d),
            'current_price': _g(d, 'current_price'),
            'final_recommendation': rec[:60],
            'monday_trigger': _monday_trigger_text(tier, cfg),
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    tier_order = {TIER_IGNITE: 0, TIER_READY: 1, TIER_COIL: 2, TIER_MOM_POP: 3}
    out['_tier_ord'] = out['breakout_tier'].map(tier_order).fillna(9)
    out = out.sort_values(['_tier_ord', 'breakout_radar_score'], ascending=[True, False])
    out = out.drop(columns=['_tier_ord']).head(max_rows)
    return out


def _monday_trigger_text(tier: str, cfg=None) -> str:
    vol = _f(_cfg(cfg, 'BREAKOUT_IGNITE_VOL_RATIO', 2.5))
    ret = _f(_cfg(cfg, 'BREAKOUT_IGNITE_1D_MIN', 2.5))
    if tier == TIER_IGNITE:
        return f'Active: vol>={vol}x and +{ret}% day'
    return f'Watch Mon: vol>={vol}x, +{ret}% day, break 20d high'


def pick_fast_track_symbol(radar_df: pd.DataFrame, cfg=None) -> Optional[Dict[str, Any]]:
    """Best fast-track candidate: B-IGNITE first, then A+-READY."""
    if radar_df is None or radar_df.empty:
        return None
    for tier in (TIER_IGNITE, TIER_READY):
        sub = radar_df[radar_df['breakout_tier'] == tier]
        if not sub.empty:
            return sub.iloc[0].to_dict()
    return None
