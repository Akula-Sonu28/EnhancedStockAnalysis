"""
Flow-quality stock picker (anti-chase) + volume-only shadow + rolling switch.

Pick layer (30d): flow_quality = volume_strength - lambda * momentum_technical
Time layer (7d): turbo_mtf in turbo_entry.py (never alias score_v2).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from src.picking_metrics import spearman_ic


def _cfg(cfg, key: str, default: Any) -> Any:
    if cfg is None:
        try:
            from config import get_config
            cfg = get_config()
        except Exception:
            return default
    return getattr(cfg, key, default)


def adaptive_momentum_lambda(momentum: float, cfg=None) -> float:
    """Tiered anti-chase penalty on momentum subscore."""
    mom = float(momentum) if momentum is not None and not pd.isna(momentum) else 50.0
    low = float(_cfg(cfg, 'FQ_LAMBDA_LOW', 0.3))
    mid = float(_cfg(cfg, 'FQ_LAMBDA_MID', 0.5))
    high = float(_cfg(cfg, 'FQ_LAMBDA_HIGH', 0.8))
    mid_thr = float(_cfg(cfg, 'FQ_MOM_MID_THRESHOLD', 50.0))
    high_thr = float(_cfg(cfg, 'FQ_MOM_HIGH_THRESHOLD', 65.0))
    if mom > high_thr:
        return high
    if mom > mid_thr:
        return mid
    return low


def compute_flow_quality_score(
    volume: float,
    momentum: float,
    *,
    lam: Optional[float] = None,
    cfg=None,
) -> float:
    """Raw flow_quality (higher = better pick). Not cross-sectionally z-scored."""
    vol = float(volume) if volume is not None and not pd.isna(volume) else 50.0
    mom = float(momentum) if momentum is not None and not pd.isna(momentum) else 50.0
    if lam is None:
        lam = float(_cfg(cfg, 'FQ_LAMBDA_DEFAULT', 0.5))
    return float(vol - lam * mom)


def compute_flow_quality_adapt(volume: float, momentum: float, cfg=None) -> float:
    lam = adaptive_momentum_lambda(momentum, cfg)
    return compute_flow_quality_score(volume, momentum, lam=lam, cfg=cfg)


def compute_volume_only_score(volume: float) -> float:
    v = float(volume) if volume is not None and not pd.isna(volume) else 50.0
    return v


def _vol_mom_cols(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    vol = pd.to_numeric(
        df.get('hybrid_volume_strength', df.get('volume_strength', 50)),
        errors='coerce',
    ).fillna(50.0)
    mom = pd.to_numeric(
        df.get('hybrid_momentum_technical', df.get('momentum_technical', 50)),
        errors='coerce',
    ).fillna(50.0)
    return vol, mom


def add_oracle_pick_columns(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    """Add fq_score, volume_pick_score, fq_adapt_score, oracle_pick_pct."""
    if df is None or df.empty:
        return df
    out = df.copy()
    vol, mom = _vol_mom_cols(out)
    lam = float(_cfg(cfg, 'FQ_LAMBDA_DEFAULT', 0.5))
    out['fq_score'] = (vol - lam * mom).astype(float)
    out['volume_pick_score'] = vol.astype(float)
    out['fq_adapt_score'] = [
        compute_flow_quality_adapt(v, m, cfg) for v, m in zip(vol, mom)
    ]
    pct = float(_cfg(cfg, 'ORACLE_WATCHLIST_PCT', 0.20))
    pick_col = str(_cfg(cfg, 'ORACLE_PICK_METRIC', 'fq_score')).lower()
    if pick_col in ('lowvol_mom', 'low_vol_momentum', 'quality_lvm'):
        try:
            from datetime import date
            from src.lowvol_momentum import active_lvm_score_col, compute_active_lvm_score
            out = compute_active_lvm_score(out, cfg, as_of=date.today())
            rank_src = out[active_lvm_score_col(cfg)]
        except Exception as e:
            logging.warning(f"LVM family scoring failed, falling back to fq_score: {e}")
            rank_src = out['fq_score']
    elif pick_col == 'volume_only':
        rank_src = out['volume_pick_score']
    elif pick_col == 'fq_adapt':
        rank_src = out['fq_adapt_score']
    else:
        rank_src = out['fq_score']
    out['oracle_pick_pct'] = rank_src.rank(pct=True, ascending=True)
    out['on_oracle_watchlist'] = out['oracle_pick_pct'] >= (1.0 - pct)
    return out


def resolve_active_oracle(
    history_df: Optional[pd.DataFrame],
    cfg=None,
) -> str:
    """
    Rolling switch: fq vs volume_only on recent history daily IC.
    Default fq when insufficient history.
    """
    if not bool(_cfg(cfg, 'ORACLE_ROLLING_SWITCH_ENABLED', True)):
        return str(_cfg(cfg, 'ORACLE_PICK_METRIC', 'fq_score'))

    window = int(_cfg(cfg, 'ORACLE_IC_SWITCH_WINDOW_DAYS', 21))
    if history_df is None or history_df.empty:
        return 'fq_score'
    work = history_df.copy()
    if 'date' not in work.columns or 'return_30d' not in work.columns:
        return 'fq_score'
    work['date'] = pd.to_datetime(work['date'], errors='coerce')
    cutoff = datetime.now() - timedelta(days=window)
    work = work[work['date'] >= cutoff]
    if 'fq_score' not in work.columns:
        return 'fq_score'
    ret = pd.to_numeric(work['return_30d'], errors='coerce')
    fq_ic, _, n_fq = spearman_ic(pd.to_numeric(work['fq_score'], errors='coerce'), ret)
    vol_ic, _, n_vol = spearman_ic(
        pd.to_numeric(work.get('volume_pick_score', work.get('fq_score')), errors='coerce'),
        ret,
    )
    if n_fq < 30 or fq_ic is None:
        return 'fq_score'
    if n_vol < 30 or vol_ic is None:
        return 'fq_score'
    return 'volume_only' if float(vol_ic) > float(fq_ic) else 'fq_score'


def enrich_oracle_columns(df: pd.DataFrame, cfg=None, history_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Pick columns + active_oracle label."""
    out = add_oracle_pick_columns(df, cfg)
    active = resolve_active_oracle(history_df, cfg)
    out['active_oracle'] = active
    pct = float(_cfg(cfg, 'ORACLE_WATCHLIST_PCT', 0.20))
    pick_metric = str(_cfg(cfg, 'ORACLE_PICK_METRIC', 'fq_score')).lower()
    if pick_metric in ('lowvol_mom', 'low_vol_momentum', 'quality_lvm') or active in (
        'lowvol_mom', 'low_vol_momentum', 'quality_lvm',
    ):
        from src.lowvol_momentum import active_lvm_score_col, is_quality_lvm_strategy
        out['active_oracle'] = 'quality_lvm' if is_quality_lvm_strategy(cfg) else 'lowvol_mom'
        scol = active_lvm_score_col(cfg)
        if scol in out.columns:
            src = out[scol]
        else:
            src = out['fq_score']
    elif active == 'volume_only':
        src = out['volume_pick_score']
    elif active == 'fq_adapt':
        src = out['fq_adapt_score']
    else:
        src = out['fq_score']
    out['oracle_pick_pct'] = src.rank(pct=True, ascending=True)
    out['on_oracle_watchlist'] = out['oracle_pick_pct'] >= (1.0 - pct)
    return out


def build_entry_watchlist_mask(df: pd.DataFrame, cfg=None) -> pd.Series:
    """True for names eligible for NEW (oracle watchlist), not v1 BUY label."""
    if df is None or df.empty:
        return pd.Series(dtype=bool)
    pct = float(_cfg(cfg, 'ORACLE_WATCHLIST_PCT', 0.20))
    if 'on_oracle_watchlist' in df.columns:
        return df['on_oracle_watchlist'].fillna(False)
    out = add_oracle_pick_columns(df, cfg)
    return out['oracle_pick_pct'] >= (1.0 - pct)


def read_walkforward_verdict(data_dir: str = 'data') -> str:
    path = os.path.join(data_dir, 'walkforward_v2_validation_fixed_turbo.json')
    if not os.path.exists(path):
        path = os.path.join(data_dir, 'walkforward_v2_validation.json')
    if not os.path.exists(path):
        return ''
    try:
        with open(path, encoding='utf-8') as fp:
            data = json.load(fp)
        verdict = data.get('verdict')
        if isinstance(verdict, dict):
            return str(verdict.get('verdict', ''))
        return str(verdict or '')
    except Exception:
        return ''


def oracle_pause_new_entries(
    cfg=None,
    walkforward_verdict: Optional[str] = None,
    regime: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Returns (paused, reason). Pauses fq+turbo NEW entries only.

    V2_SHADOW_MODE does NOT pause entries — it only keeps v1/v2 rank off the
    action surface. Entry uses flow_quality watchlist + recomputed turbo.
    """
    if not bool(_cfg(cfg, 'ORACLE_ENTRY_LIVE', True)):
        return True, 'ORACLE_ENTRY_LIVE=false'

    if bool(_cfg(cfg, 'ORACLE_PAUSE_NEW_ON_HOLD_SHADOW', True)):
        wf = (walkforward_verdict or read_walkforward_verdict(
            str(_cfg(cfg, 'DATA_DIR', 'data'))
        )).upper()
        blocked = ('HOLD_SHADOW', 'ESCALATE_TIER_C', 'ESCALATE', 'DEMOTE')
        if wf and any(b in wf for b in blocked):
            return True, f'walkforward={wf}'

    if bool(_cfg(cfg, 'ORACLE_PAUSE_NEW_IN_BEAR', True)):
        reg = str(regime or '').upper()
        if reg == 'BEAR':
            return True, 'regime=BEAR'

    return False, ''


def dist_20d_high_pct(row: Dict[str, Any]) -> Optional[float]:
    for key in ('dist_20d_high_pct', 'distance_from_20d_high_pct', 'pct_from_20d_high'):
        v = row.get(key)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    high = row.get('high_20d', row.get('rolling_high_20d'))
    price = row.get('current_price', row.get('price'))
    try:
        if high and price and float(high) > 0:
            return (float(price) / float(high) - 1.0) * 100.0
    except (TypeError, ValueError):
        pass
    return None


def passes_chase_extension_filter(row: Dict[str, Any], cfg=None) -> bool:
    """Block entries too far below 20d high (chase / extension)."""
    if not bool(_cfg(cfg, 'ORACLE_DIST_20D_HIGH_FILTER', True)):
        return True
    dist = dist_20d_high_pct(row if isinstance(row, dict) else row.to_dict())
    floor = float(_cfg(cfg, 'ORACLE_DIST_20D_HIGH_MIN_PCT', -12.0))
    if dist is None:
        return True
    return dist >= floor
