"""
Quality + LowVol→Mom ranker for backtests.

Sequential filter (research-aligned):
  1. Low-volatility pool (same as LVM)
  2. Quality / profitability gate (PIT Screener fundamentals)
  3. Momentum rank within survivors
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.lowvol_momentum import (
    _above_sma50,
    _cfg,
    _return_12m_col,
    _sector_col,
    _volatility_col,
)


def _pit_lookup(symbol: str, as_of: Optional[date], price: float) -> dict:
    if as_of is None:
        return {}
    try:
        from backtest.data.fundamentals_pit import get_fundamental_lookup
        return get_fundamental_lookup().lookup(symbol, as_of, price=price)
    except Exception:
        return {}


def _has_real_pit(symbol: str, as_of: Optional[date]) -> bool:
    if as_of is None:
        return False
    try:
        from backtest.data.fundamentals_pit import get_fundamental_lookup
        return get_fundamental_lookup().has_real_filing(symbol, as_of)
    except Exception:
        return False


def _pit_value_trap(symbol: str, as_of: Optional[date], price: float) -> bool:
    if as_of is None:
        return False
    try:
        from backtest.data.fundamentals_pit import get_fundamental_lookup
        return get_fundamental_lookup().is_value_trap(symbol, as_of, price=price)
    except Exception:
        return False


def _quality_composite(
    roe: pd.Series,
    earn_g: pd.Series,
    rev_g: pd.Series,
    de: pd.Series,
) -> pd.Series:
    """Higher is better. Uses percentile ranks on the pool."""
    roe_r = roe.rank(pct=True, ascending=True).fillna(0.0)
    eg_r = earn_g.rank(pct=True, ascending=True).fillna(0.0)
    rg_r = rev_g.rank(pct=True, ascending=True).fillna(0.0)
    de_r = de.rank(pct=True, ascending=False).fillna(0.0)
    return roe_r * 35 + eg_r * 25 + rg_r * 20 + de_r * 20


def compute_quality_lvm_score(
    df: pd.DataFrame,
    cfg=None,
    as_of: Optional[date] = None,
    require_real_pit: Optional[bool] = None,
) -> pd.DataFrame:
    """
    Quality + LowVol→Mom ranking.

    Adds: quality_lvm_score, quality_lvm_rank, quality_lvm_eligible
    """
    if df is None:
        return df
    if df.empty:
        out = df.copy()
        out['quality_lvm_score'] = pd.Series(dtype=float)
        out['quality_lvm_rank'] = pd.Series(dtype=float)
        out['quality_lvm_eligible'] = pd.Series(dtype=bool)
        return out

    out = df.copy()
    pool_size = int(_cfg(cfg, 'LVM_LOWVOL_POOL_SIZE', 40))
    quality_pool = int(_cfg(cfg, 'LVM_QUALITY_POOL_SIZE', 30))
    from src.lowvol_momentum import lvm_top_n
    top_n = lvm_top_n(cfg)
    require_sma50 = bool(_cfg(cfg, 'LVM_REQUIRE_ABOVE_SMA50', True))
    sector_cap = int(_cfg(cfg, 'LVM_SECTOR_CAP', 3))
    min_roe = float(_cfg(cfg, 'LVM_QUALITY_MIN_ROE', 10.0))
    max_de = float(_cfg(cfg, 'LVM_QUALITY_MAX_DEBT_TO_EQUITY', 150.0))
    min_earn_g = float(_cfg(cfg, 'LVM_QUALITY_MIN_EARNINGS_GROWTH', -100.0))
    exclude_traps = bool(_cfg(cfg, 'LVM_QUALITY_EXCLUDE_VALUE_TRAPS', True))
    if require_real_pit is None:
        require_real_pit = bool(_cfg(cfg, 'LVM_QUALITY_REQUIRE_REAL_PIT', False))

    vol = _volatility_col(out)
    ret_12m = _return_12m_col(out)
    above_sma = _above_sma50(out)
    sectors = _sector_col(out)
    prices = pd.to_numeric(
        out.get('current_price', out.get('price', pd.Series(dtype=float))),
        errors='coerce',
    )

    roe_vals = []
    earn_g_vals = []
    rev_g_vals = []
    de_vals = []
    trap_vals = []
    real_pit_vals = []
    for idx, row in out.iterrows():
        sym = str(row.get('symbol', ''))
        px = float(prices.get(idx, 0) or 0)
        if 'pit_roe' in out.columns and pd.notna(row.get('pit_roe')):
            pit = {
                'roe': row.get('pit_roe'),
                'earnings_growth': row.get('pit_earnings_growth'),
                'revenue_growth': row.get('pit_revenue_growth'),
                'debt_to_equity': row.get('pit_debt_to_equity'),
            }
            trap = bool(row.get('pit_value_trap', False))
            has_real = bool(row.get('pit_has_real_filing', True))
        else:
            pit = _pit_lookup(sym, as_of, px)
            trap = _pit_value_trap(sym, as_of, px) if exclude_traps else False
            has_real = _has_real_pit(sym, as_of)
        roe_vals.append(float(pit.get('roe', 0) or 0))
        earn_g_vals.append(float(pit.get('earnings_growth', 0) or 0))
        rev_g_vals.append(float(pit.get('revenue_growth', 0) or 0))
        de_vals.append(float(pit.get('debt_to_equity', 999) or 999))
        trap_vals.append(trap)
        real_pit_vals.append(has_real)

    out['_pit_roe'] = roe_vals
    out['_pit_eg'] = earn_g_vals
    out['_pit_rg'] = rev_g_vals
    out['_pit_de'] = de_vals
    out['_pit_trap'] = trap_vals
    out['_pit_real'] = real_pit_vals
    out['_lvm_vol'] = vol
    out['_lvm_ret'] = ret_12m

    eligible_mask = pd.Series(True, index=out.index)
    if require_sma50:
        eligible_mask &= above_sma
    eligible_mask &= vol < 900
    if exclude_traps:
        eligible_mask &= ~out['_pit_trap'].astype(bool)
    eligible_mask &= out['_pit_roe'] >= min_roe
    eligible_mask &= out['_pit_de'] <= max_de
    eligible_mask &= out['_pit_eg'] >= min_earn_g
    if require_real_pit:
        eligible_mask &= out['_pit_real'].astype(bool)

    eligible = out[eligible_mask].copy()
    if len(eligible) < pool_size:
        pool = eligible
    else:
        pool = eligible.nsmallest(pool_size, '_lvm_vol')

    if pool.empty:
        out['quality_lvm_score'] = 0.0
        out['quality_lvm_rank'] = 0.0
        out['quality_lvm_eligible'] = False
        out.drop(
            columns=[c for c in out.columns if c.startswith('_')],
            inplace=True,
            errors='ignore',
        )
        return out

    pool = pool.copy()
    pool['_qual'] = _quality_composite(
        pool['_pit_roe'], pool['_pit_eg'], pool['_pit_rg'], pool['_pit_de'],
    )
    if len(pool) > quality_pool:
        pool = pool.nlargest(quality_pool, '_qual')

    pool['_lvm_mom_rank'] = pool['_lvm_ret'].rank(ascending=False, method='min')

    if sector_cap > 0:
        pool['_sector'] = sectors.reindex(pool.index)
        keep = []
        sector_counts: dict = {}
        for idx in pool.sort_values('_lvm_mom_rank').index:
            sec = str(pool.at[idx, '_sector'])
            sector_counts.setdefault(sec, 0)
            if sector_counts[sec] < sector_cap:
                keep.append(idx)
                sector_counts[sec] += 1
        pool = pool.loc[keep]

    selected = pool.nlargest(top_n, '_lvm_ret')
    selected_idx = set(selected.index)

    qual_all = _quality_composite(
        out['_pit_roe'], out['_pit_eg'], out['_pit_rg'], out['_pit_de'],
    )
    qual_pct = qual_all.rank(pct=True, ascending=True)
    ret_pct = ret_12m.rank(pct=True, ascending=True)
    raw_score = qual_pct * 50 + ret_pct * 50

    out['quality_lvm_score'] = raw_score.fillna(0.0)
    for idx in selected_idx:
        out.at[idx, 'quality_lvm_score'] = float(out.at[idx, 'quality_lvm_score']) + 100.0

    out['quality_lvm_rank'] = out['quality_lvm_score'].rank(pct=True, ascending=True)
    out['quality_lvm_eligible'] = out.index.isin(selected_idx)

    out.drop(columns=[c for c in out.columns if c.startswith('_')], inplace=True, errors='ignore')
    return out
