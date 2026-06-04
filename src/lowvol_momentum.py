"""
LowVol→Mom stock picker — two-pass cross-sectional rank.

Pass 1: From the universe, select the N lowest-volatility stocks (12m daily return std).
Pass 2: From that pool, rank by 12-month price return (descending).

Backed by 18-year NSE academic research (BacktestIndia multi-factor: 14.61% CAGR)
and 4/4 out-of-sample Nifty-beat periods in project backtests.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

import numpy as np
import pandas as pd

LVM_MOMENTUM_INPUT_COLS = (
    'price_change_1y',
    'enhanced_price_change_1y',
    'price_change_6m',
    'enhanced_price_change_60d',
    'price_change_3m',
    'enhanced_price_change_30d',
)


def _cfg(cfg, key: str, default: Any) -> Any:
    if cfg is None:
        try:
            from config import get_config
            cfg = get_config()
        except Exception:
            return default
    return getattr(cfg, key, default)


def _volatility_col(df: pd.DataFrame) -> pd.Series:
    """Best available volatility proxy (lower = less volatile)."""
    for col in ('volatility_6m', 'volatility', 'enhanced_volatility_20d'):
        if col in df.columns:
            return pd.to_numeric(df[col], errors='coerce').fillna(999.0)
    if 'hybrid_risk_adjustment' in df.columns:
        ra = pd.to_numeric(df['hybrid_risk_adjustment'], errors='coerce').fillna(50.0)
        return 100.0 - ra
    return pd.Series(999.0, index=df.index)


def _return_12m_col(df: pd.DataFrame) -> pd.Series:
    """Best available 12-month return proxy (higher = better momentum).

    Fallback chain: price_change_1y (exact) → enhanced_price_change_1y →
    price_change_6m * 1.5 + price_change_3m (approximate: 1.5 extrapolates
    6m to ~9m equivalent, combined with 3m for a rough 12m proxy;
    used only when annual data is unavailable).
    """
    for col in ('price_change_1y', 'enhanced_price_change_1y'):
        if col in df.columns:
            return pd.to_numeric(df[col], errors='coerce').fillna(-999.0)
    r6 = None
    for col in ('price_change_6m', 'enhanced_price_change_60d'):
        if col in df.columns:
            r6 = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            break
    r3 = None
    for col in ('price_change_3m', 'enhanced_price_change_30d'):
        if col in df.columns:
            r3 = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            break
    if r6 is not None and r3 is not None:
        return r6 * 1.5 + r3
    if r6 is not None:
        return r6
    if r3 is not None:
        return r3 * 2
    logging.warning(
        '[LVM] _return_12m_col: no momentum columns found — '
        'all returns defaulted to 0.0; LVM rankings will be arbitrary',
    )
    return pd.Series(0.0, index=df.index)


def is_lvm_momentum_degraded(df: pd.DataFrame) -> bool:
    """True when momentum inputs are missing or flat (unreliable LVM picks)."""
    if df is None or df.empty:
        return True
    if not any(c in df.columns for c in LVM_MOMENTUM_INPUT_COLS):
        return True
    ret = _return_12m_col(df)
    valid = pd.to_numeric(ret, errors='coerce').dropna()
    if valid.empty:
        return True
    uniq = valid.unique()
    if len(uniq) <= 1 and float(uniq[0]) == 0.0:
        return True
    return False


def _above_sma50(df: pd.DataFrame) -> pd.Series:
    """True if current price is above 50-day SMA."""
    price = pd.to_numeric(
        df.get('current_price', df.get('price', pd.Series(dtype=float))),
        errors='coerce',
    )
    sma50 = pd.to_numeric(
        df.get('enhanced_sma_50', df.get('sma_50', df.get('legacy_sma_50', pd.Series(dtype=float)))),
        errors='coerce',
    )
    if price.isna().all() or sma50.isna().all():
        return pd.Series(True, index=df.index)
    return price >= sma50


def _sector_col(df: pd.DataFrame) -> pd.Series:
    """Best available sector column."""
    for col in ('sector', 'sector_classification', 'industry'):
        if col in df.columns:
            return df[col].fillna('Unknown')
    return pd.Series('Unknown', index=df.index)


def compute_lowvol_mom_score(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    """
    Two-pass LowVol→Mom ranking.

    Adds columns: lowvol_mom_score, lowvol_mom_rank, lowvol_mom_eligible
    Returns the enriched DataFrame (copy).
    """
    if df is None:
        return df
    if df.empty:
        out = df.copy()
        out['lowvol_mom_score'] = pd.Series(dtype=float)
        out['lowvol_mom_rank'] = pd.Series(dtype=float)
        out['lowvol_mom_eligible'] = pd.Series(dtype=bool)
        return out

    out = df.copy()
    pool_size = int(_cfg(cfg, 'LVM_LOWVOL_POOL_SIZE', 40))
    top_n = lvm_top_n(cfg)
    require_sma50 = bool(_cfg(cfg, 'LVM_REQUIRE_ABOVE_SMA50', True))
    sector_cap = int(_cfg(cfg, 'LVM_SECTOR_CAP', 3))

    vol = _volatility_col(out)
    ret_12m = _return_12m_col(out)
    above_sma = _above_sma50(out)
    sectors = _sector_col(out)

    out['_lvm_vol'] = vol
    out['_lvm_ret'] = ret_12m
    out['_lvm_above_sma'] = above_sma

    eligible_mask = pd.Series(True, index=out.index)
    if require_sma50:
        eligible_mask &= above_sma
    eligible_mask &= vol < 900

    eligible = out[eligible_mask].copy()

    if len(eligible) < pool_size:
        pool = eligible
    else:
        pool = eligible.nsmallest(pool_size, '_lvm_vol')

    if pool.empty:
        out['lowvol_mom_score'] = 0.0
        out['lowvol_mom_rank'] = 0.0
        out['lowvol_mom_eligible'] = False
        out.drop(columns=['_lvm_vol', '_lvm_ret', '_lvm_above_sma'], inplace=True)
        return out

    pool = pool.copy()
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

    vol_pct = vol.rank(pct=True, ascending=False)
    ret_pct = ret_12m.rank(pct=True, ascending=True)
    raw_score = vol_pct * 50 + ret_pct * 50

    out['lowvol_mom_score'] = raw_score.fillna(0.0)

    for idx in selected_idx:
        out.at[idx, 'lowvol_mom_score'] = float(out.at[idx, 'lowvol_mom_score']) + 100.0

    out['lowvol_mom_rank'] = out['lowvol_mom_score'].rank(pct=True, ascending=True)
    out['lowvol_mom_eligible'] = out.index.isin(selected_idx)

    out.drop(columns=['_lvm_vol', '_lvm_ret', '_lvm_above_sma'], inplace=True, errors='ignore')
    return out


def lvm_stability_audit(
    df: pd.DataFrame,
    cfg=None,
    n_trials: int = 50,
    noise_pct: float = 0.02,
    top_n_display: int = 15,
) -> str:
    """Run perturbation test on LVM picks and return a formatted action panel.

    Perturbs current_price by ±noise_pct across n_trials, recomputes
    LVM Top N each time, and reports how often each stock is selected.
    """
    if df is None or df.empty:
        return ''

    import numpy as _np
    from collections import Counter as _Counter

    _np.random.seed(42)
    counts: _Counter = _Counter()
    ecol = active_lvm_eligible_col(cfg)
    base = compute_active_lvm_score(df.copy(), cfg)
    base_picks = set(base.loc[base[ecol].fillna(False).astype(bool), 'symbol'].tolist())

    pool_size = int(_cfg(cfg, 'LVM_LOWVOL_POOL_SIZE', 40))
    sector_cap = int(_cfg(cfg, 'LVM_SECTOR_CAP', 3))

    for _ in range(n_trials):
        p = df.copy()
        noise = _np.random.uniform(1 - noise_pct, 1 + noise_pct, len(p))
        p['current_price'] = pd.to_numeric(p['current_price'], errors='coerce') * noise
        from datetime import date as _audit_date
        trial = compute_active_lvm_score(p, cfg, as_of=_audit_date.today())
        for s in trial.loc[trial[ecol].fillna(False).astype(bool), 'symbol']:
            counts[s] += 1

    candidates = [s for s, _ in counts.most_common(top_n_display + 5)]
    for s in base_picks:
        if s not in candidates:
            candidates.append(s)
    candidates = candidates[:top_n_display]

    vol = _volatility_col(df)
    price = pd.to_numeric(df.get('current_price', pd.Series(dtype=float)), errors='coerce').fillna(0)
    sma50 = pd.to_numeric(
        df.get('enhanced_sma_50', df.get('sma_50', df.get('legacy_sma_50', pd.Series(dtype=float)))),
        errors='coerce',
    ).fillna(0)
    sectors = _sector_col(df)

    eligible_mask = (price >= sma50) & (vol < 900)
    eligible = df[eligible_mask]
    pool = eligible.nsmallest(pool_size, 'volatility_6m') if 'volatility_6m' in eligible.columns else eligible
    pool_max_vol = float(vol.reindex(pool.index).max()) if not pool.empty else 30.0
    pool_sectors = sectors.reindex(pool.index).value_counts().to_dict()

    per_stock = 110_000
    lines = []
    sep = '=' * 130
    lines.append(sep)
    lines.append(f'  {"#":>2}  {"TIER":<12} {"SYMBOL":<14} {"PRICE":>8} {"SHARES":>7} '
                 f'{"INVEST ₹":>10} {"STOP-10%":>9} {"ENTRY BAND":>12}  '
                 f'{"STAB":>5}  RISK')
    lines.append(sep)

    rows_data = []
    for sym in candidates:
        row = df[df['symbol'] == sym]
        if row.empty:
            continue
        r = row.iloc[0]
        idx = row.index[0]
        p = float(price.get(idx, 0))
        v = float(vol.get(idx, 999))
        sec = str(sectors.get(idx, '?'))
        pct_above = round(((p / sma50.get(idx, 1)) - 1) * 100, 1) if sma50.get(idx, 0) > 0 else 0

        stab = counts.get(sym, 0)
        if stab >= n_trials:
            tier = 'ROCK SOLID'
        elif stab >= n_trials * 0.9:
            tier = 'VERY STABLE'
        elif stab >= n_trials * 0.7:
            tier = 'STABLE'
        elif stab >= n_trials * 0.4:
            tier = 'BORDERLINE'
        else:
            tier = 'FRAGILE'

        shares = int(per_stock / p) if p > 0 else 0
        invest = shares * p
        stop = round(p * 0.9, 1)
        entry = f'{int(p * 0.97)}\u2013{int(p * 1.01)}'

        reasons = []
        if v > pool_max_vol - 1.0:
            reasons.append('VOL↑')
        if abs(pct_above) < 3:
            reasons.append(f'SMA50 {pct_above:+.1f}%')
        sec_count = pool_sectors.get(sec, 0)
        if sec_count > sector_cap:
            reasons.append(f'SEC {sec_count}/{sector_cap}')
        fragile_str = ' | '.join(reasons) if reasons else '\u2014'

        marker = '\u2713' if sym in base_picks else ' '
        rows_data.append((stab, sym))
        lines.append(
            f'{marker} {len(rows_data):>2}  {tier:<12} {sym:<14} {p:>8.1f} {shares:>7} '
            f'{invest:>10,.0f} {stop:>9.1f} {entry:>12}  '
            f'{stab:>3}/{n_trials}  {fragile_str}'
        )

    lines.append(sep)
    lines.append(f'  VOL↑ = near volatility cutoff | SMA50 = near 50-day avg | SEC = sector crowding')
    return '\n'.join(lines)


LVM_PICK_METRICS = frozenset({'lowvol_mom', 'low_vol_momentum', 'quality_lvm'})


def lvm_top_n(cfg=None) -> int:
    return max(1, int(_cfg(cfg, 'LVM_TOP_N', 20)))


def lvm_fund_n(cfg=None) -> int:
    """How many LVM names to fund monthly (≤ screen list)."""
    screen = lvm_top_n(cfg)
    fund = max(1, int(_cfg(cfg, 'LVM_FUND_N', 12)))
    return min(fund, screen)


def lvm_top_label(cfg=None) -> str:
    """User-facing label, e.g. 'LVM Top 20'."""
    return f'LVM Top {lvm_top_n(cfg)}'


def lvm_fund_label(cfg=None) -> str:
    return f'LVM Fund Top {lvm_fund_n(cfg)}'


def lvm_sheet_name(cfg=None) -> str:
    """Excel/dashboard sheet label for current LVM family picker."""
    n = lvm_top_n(cfg)
    if is_quality_lvm_strategy(cfg):
        return f'Quality-LVM Top {n}'
    return f'LowVol-Mom Top {n}'


def is_lvm_strategy(cfg=None) -> bool:
    pick = str(_cfg(cfg, 'ORACLE_PICK_METRIC', 'fq_score')).lower()
    return pick in LVM_PICK_METRICS


def is_quality_lvm_strategy(cfg=None) -> bool:
    return str(_cfg(cfg, 'ORACLE_PICK_METRIC', 'fq_score')).lower() == 'quality_lvm'


def active_lvm_eligible_col(cfg=None) -> str:
    return 'quality_lvm_eligible' if is_quality_lvm_strategy(cfg) else 'lowvol_mom_eligible'


def active_lvm_score_col(cfg=None) -> str:
    return 'quality_lvm_score' if is_quality_lvm_strategy(cfg) else 'lowvol_mom_score'


def compute_active_lvm_score(df: pd.DataFrame, cfg=None, as_of=None) -> pd.DataFrame:
    """Production pick ranker: baseline LVM or Quality+LVM per ORACLE_PICK_METRIC."""
    degraded_in = is_lvm_momentum_degraded(df) if df is not None and not df.empty else True
    if is_quality_lvm_strategy(cfg):
        from datetime import date as _date
        from src.quality_lowvol_momentum import compute_quality_lvm_score
        require_real = bool(_cfg(cfg, 'LVM_QUALITY_REQUIRE_REAL_PIT', True))
        if as_of is None:
            as_of = _date.today()
        out = compute_quality_lvm_score(
            df, cfg, as_of=as_of, require_real_pit=require_real,
        )
    else:
        out = compute_lowvol_mom_score(df, cfg)
    if degraded_in or is_lvm_momentum_degraded(df):
        out.attrs['_lvm_data_degraded'] = True
        logging.warning(
            '[LVM] Data degraded: momentum columns missing or flat — '
            'eligible flags unreliable',
        )
    else:
        out.attrs['_lvm_data_degraded'] = False
    return out


def lvm_eligible_symbols(results_df: pd.DataFrame, cfg=None) -> set:
    """Full LVM screen list (LVM_TOP_N) — used for rotation membership."""
    if results_df is None or results_df.empty:
        return set()
    work = results_df
    ecol = active_lvm_eligible_col(cfg)
    if ecol not in work.columns:
        work = compute_active_lvm_score(work, cfg)
    mask = work[ecol].fillna(False).astype(bool)
    return set(work.loc[mask, 'symbol'].astype(str).str.upper().tolist())


def lvm_fund_symbols(results_df: pd.DataFrame, cfg=None) -> set:
    """Top LVM_FUND_N names by active LVM score — monthly equal-weight book."""
    screen = lvm_eligible_symbols(results_df, cfg)
    if not screen:
        return set()
    picks = _lvm_pick_rows(results_df, screen, cfg)
    if picks.empty:
        return set()
    n = lvm_fund_n(cfg)
    return set(picks.head(n)['symbol'].astype(str).str.upper().tolist())


def apply_lvm_rotation_to_allocation(
    allocation_df: pd.DataFrame,
    lvm_syms: set,
    cfg=None,
) -> Tuple[pd.DataFrame, int]:
    """Mark active non-LVM holdings for rotation sell. Returns (df, count)."""
    if allocation_df is None or allocation_df.empty or not lvm_syms:
        return allocation_df, 0
    out = allocation_df.copy()
    rotated = 0
    for idx, row in out.iterrows():
        sym = str(row.get('symbol', '')).upper()
        if not sym or sym in lvm_syms:
            continue
        if not bool(row.get('is_current_holding', False)):
            continue
        cur_val = float(pd.to_numeric(row.get('current_value', 0), errors='coerce') or 0)
        if cur_val <= 0:
            continue
        act = str(row.get('action_recommendation', '')).upper().strip()
        if act in ('SELL',) or 'EXIT' in act or 'SWAP' in act:
            continue
        if 'LVM ROTATION' in act:
            continue
        rotateable = (
            not act
            or 'HOLD' in act
            or 'KEEP' in act
            or 'INCREASE' in act
            or 'BUY' in act
            or 'NEW POSITION' in act
            or 'MOMENTUM' in act
        )
        if not rotateable:
            continue
        from src.lvm_action_plan import lvm_rotation_reason, sanitize_reason_fragment
        prev_reason = sanitize_reason_fragment(row.get('exit_reason', '') or row.get('action_reason', ''))
        out.at[idx, 'action_recommendation'] = 'SELL (LVM ROTATION)'
        out.at[idx, 'action_type'] = 'SELL (LVM ROTATION)'
        out.at[idx, 'keep_stock'] = False
        out.at[idx, 'investment_amount'] = 0
        out.at[idx, 'suggested_quantity'] = 0
        out.at[idx, 'exit_strategy'] = '🔄 LVM ROTATION'
        out.at[idx, 'exit_reason'] = lvm_rotation_reason(lvm_top_label(cfg), prev_reason)
        if 'sell_category' in out.columns:
            out.at[idx, 'sell_category'] = 'LVM_ROTATION'
        if 'SELL WHY' in out.columns:
            out.at[idx, 'SELL WHY'] = 'LVM_ROTATION'
        out.at[idx, 'priority'] = 'HIGH'
        rotated += 1
    return out, rotated


def _lvm_pick_rows(results_df: pd.DataFrame, lvm_syms: set, cfg=None) -> pd.DataFrame:
    if results_df is None or results_df.empty:
        return pd.DataFrame()
    work = results_df.copy()
    ecol = active_lvm_eligible_col(cfg)
    if ecol not in work.columns:
        work = compute_active_lvm_score(work, cfg)
    mask = work['symbol'].astype(str).str.upper().isin(lvm_syms)
    picks = work[mask].copy()
    if picks.empty:
        return picks
    scol = active_lvm_score_col(cfg)
    rank_col = scol if scol in picks.columns else 'symbol'
    return picks.sort_values(rank_col, ascending=False)


def fund_lvm_picks_equal_weight(
    allocation_df: pd.DataFrame,
    results_df: pd.DataFrame,
    lvm_syms: set,
    total_available: float,
    min_invest: float,
    cfg=None,
) -> Tuple[pd.DataFrame, float, int, int, float]:
    """
    Equal-weight fund all LVM Top-N picks.
    Returns (allocation_df, total_allocated, buy_count, increase_count, remaining_budget).
    """
    out = allocation_df.copy()
    picks = _lvm_pick_rows(results_df, lvm_syms, cfg)
    if picks.empty or total_available <= 0:
        return out, 0.0, 0, 0, float(total_available)

    n = len(picks)
    per_stock = total_available / n
    remaining = float(total_available)
    total_allocated = 0.0
    buy_count = 0
    increase_count = 0

    for _, pick in picks.iterrows():
        sym = str(pick.get('symbol', '')).upper()
        if not sym:
            continue
        price = float(pd.to_numeric(pick.get('current_price', 0), errors='coerce') or 0)
        if price <= 0:
            continue

        target = per_stock
        mask = out['symbol'].astype(str).str.upper() == sym
        is_held = bool(mask.any()) and float(
            pd.to_numeric(out.loc[mask, 'current_value'].iloc[0], errors='coerce') or 0
        ) > 0

        if is_held:
            idx = out.index[mask][0]
            cur_val = float(pd.to_numeric(out.at[idx, 'current_value'], errors='coerce') or 0)
            add_budget = max(0.0, target - cur_val)
            if add_budget < min_invest:
                out.at[idx, 'action_recommendation'] = 'HOLD'
                out.at[idx, 'keep_stock'] = True
                out.at[idx, 'exit_reason'] = f'{lvm_fund_label(cfg)} — at target weight'
                continue
            shares = int(add_budget / price)
            actual = shares * price
            if actual < min_invest or shares < 1:
                out.at[idx, 'action_recommendation'] = 'HOLD'
                continue
            out.at[idx, 'action_recommendation'] = 'INCREASE (LVM)'
            out.at[idx, 'investment_amount'] = actual
            out.at[idx, 'suggested_quantity'] = shares
            out.at[idx, 'keep_stock'] = True
            out.at[idx, 'exit_reason'] = f'{lvm_fund_label(cfg)} — rebalance up to equal weight'
            total_allocated += actual
            remaining -= actual
            increase_count += 1
        else:
            shares = int(target / price)
            actual = shares * price
            if actual < min_invest or shares < 1:
                continue
            src = pick.to_dict()
            new_row = dict(src)
            new_row.update({
                'symbol': sym,
                'company_name': pick.get('company_name', sym),
                'sector': pick.get('sector', 'Unknown'),
                'current_price': price,
                'current_value': 0,
                'current_quantity': 0,
                'investment_amount': actual,
                'suggested_quantity': shares,
                'action_recommendation': 'NEW POSITION (LVM)',
                'action_type': 'NEW POSITION',
                'keep_stock': True,
                'is_current_holding': False,
                'exit_reason': f'{lvm_fund_label(cfg)} — equal-weight new entry',
                'exit_strategy': '🆕 LVM NEW',
                'overall_score': float(
                    pick.get(active_lvm_score_col(cfg), pick.get('overall_score', 0)) or 0
                ),
                active_lvm_eligible_col(cfg): True,
            })
            if mask.any():
                idx = out.index[mask][0]
                for k, v in new_row.items():
                    if k in out.columns:
                        out.at[idx, k] = v
            else:
                out = pd.concat([out, pd.DataFrame([new_row])], ignore_index=True)
            total_allocated += actual
            remaining -= actual
            buy_count += 1

    return out, total_allocated, buy_count, increase_count, remaining
