"""
Turbo MTF primary entry driver — timing-first stock selection.

Replaces value-heavy v1 rank for NEW POSITION with:
  1. Turbo/v2 composite score (DUAL_STRATEGY_PROFILES['turbo_mtf'] weights)
  2. MTF + momentum floors
  3. Short-window price confirmation (1d/5d only — never 20d fallback)
  4. Extended-entry guards (RSI chase, rejection wick)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.vmq_strategy import VMQEntryResult, count_new_positions_this_week, is_value_trap, _f, _cfg


COMP_MAP = {
    'hybrid_fundamental_quality': 'fundamental_quality',
    'hybrid_momentum_technical': 'momentum_technical',
    'hybrid_volume_strength': 'volume_strength',
    'hybrid_multi_timeframe': 'multi_timeframe',
    'hybrid_ml_signal': 'ml_signal',
    'hybrid_risk_adjustment': 'risk_adjustment',
    'hybrid_growth': 'growth',
    'hybrid_value': 'value',
}

_PRICE_1D_KEYS = (
    'enhanced_price_change_1d',
    'price_change_1d',
    'enhanced_tech_price_change_1d',
)
_PRICE_5D_KEYS = (
    'enhanced_price_change_5d',
    'price_change_5d',
    'enhanced_tech_price_change_5d',
)
_RSI_KEYS = ('real_rsi', 'enhanced_rsi_14', 'rsi14', 'enhanced_rsi')
_REJECTION_KEYS = ('rejection_wick_pct', 'enhanced_rejection_wick_pct')


@dataclass
class TurboEntryResult:
    allowed: bool
    status: str  # PASS, WATCHLIST, CONFIRM_WAIT
    turbo_score: float
    confirm_ret: float
    reasons: List[str] = field(default_factory=list)


def _first_float(row: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[float]:
    for key in keys:
        v = row.get(key)
        if v is not None and pd.notna(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def sync_price_change_aliases(row: Dict[str, Any]) -> Dict[str, Any]:
    """Unify enhanced_tech_* and enhanced_* price-change fields onto canonical keys."""
    out = dict(row)
    chg_1d = _first_float(out, _PRICE_1D_KEYS)
    chg_5d = _first_float(out, _PRICE_5D_KEYS)
    if chg_1d is not None:
        out.setdefault('enhanced_price_change_1d', chg_1d)
        out.setdefault('price_change_1d', chg_1d)
    if chg_5d is not None:
        out.setdefault('enhanced_price_change_5d', chg_5d)
        out.setdefault('price_change_5d', chg_5d)
    return out


def get_rsi(row: Dict[str, Any]) -> float:
    v = _first_float(row, _RSI_KEYS)
    return v if v is not None else 50.0


def get_confirm_return_pct(row: Dict[str, Any]) -> float:
    """
    Short-window price confirm % for entry timing.

    Uses 1d and 5d only. If the latest session is down, that overrides a
    still-positive 5d move (post-spike reversal). Never falls back to 20d.
    """
    row = sync_price_change_aliases(row)
    chg_1d = _first_float(row, _PRICE_1D_KEYS)
    chg_5d = _first_float(row, _PRICE_5D_KEYS)

    if chg_1d is not None and chg_1d < 0:
        return chg_1d
    if chg_5d is not None:
        return chg_5d
    if chg_1d is not None:
        return chg_1d
    return 0.0


def get_chase_5d_pct(row: Dict[str, Any]) -> Optional[float]:
    row = sync_price_change_aliases(row)
    return _first_float(row, _PRICE_5D_KEYS)


def get_rejection_wick_pct(row: Dict[str, Any]) -> Optional[float]:
    return _first_float(row, _REJECTION_KEYS)


def evaluate_extended_entry_guards(row: Dict[str, Any], cfg=None) -> List[str]:
    """ATGL-style guards: extended RSI, chase after spike, bearish rejection wick."""
    row = sync_price_change_aliases(row)
    rsi = get_rsi(row)
    chg_5d = get_chase_5d_pct(row)
    wick = get_rejection_wick_pct(row)

    rsi_hard = _f(_cfg(cfg, 'TURBO_ENTRY_RSI_HARD_BLOCK', 75.0))
    rsi_max = _f(_cfg(cfg, 'TURBO_ENTRY_RSI_MAX', 75.0))
    chase_max = _f(_cfg(cfg, 'TURBO_ENTRY_CHASE_5D_MAX', 15.0))
    wick_max = _f(_cfg(cfg, 'TURBO_ENTRY_REJECTION_WICK_PCT', 8.0))

    reasons: List[str] = []
    if rsi > rsi_hard:
        reasons.append(f'RSI {rsi:.0f}>{rsi_hard:.0f} hard block')
    elif rsi > rsi_max:
        reasons.append(f'RSI {rsi:.0f}>{rsi_max:.0f} extended')
    if chg_5d is not None and chg_5d > chase_max and rsi > rsi_max:
        reasons.append(f'chase 5d +{chg_5d:.1f}%>{chase_max:.0f}% at RSI {rsi:.0f}')
    if wick is not None and wick > wick_max:
        reasons.append(f'rejection wick {wick:.1f}%>{wick_max:.0f}%')
    return reasons


def _turbo_mtf_weights(cfg=None) -> Dict[str, float]:
    """Turbo MTF weights: oracle_weights.json tau_entry, else DUAL_STRATEGY_PROFILES."""
    import os
    import json

    data_dir = str(_cfg(cfg, 'DATA_DIR', 'data'))
    path = os.path.join(data_dir, 'oracle_weights.json')
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as fp:
                ow = json.load(fp)
            w = (ow.get('tau_entry') or {}).get('weights') or {}
            if w:
                return {str(k): float(v) for k, v in w.items()}
        except Exception:
            pass
    profiles = _cfg(cfg, 'DUAL_STRATEGY_PROFILES', {}) or {}
    return (profiles.get('turbo_mtf') or {}).get('weights') or {}


def compute_turbo_score_v2_reference(row: Dict[str, Any]) -> float:
    """Audit-only: what turbo_score used to return when aliasing live v2."""
    return _f(row.get('hybrid_overall_score_v2', row.get('score_v2', 0)))


def compute_turbo_score(row: Dict[str, Any], cfg=None) -> float:
    """Turbo MTF score: always recompute from tau_entry weights (never alias score_v2)."""
    weights = _turbo_mtf_weights(cfg)
    if not weights:
        return _f(row.get('final_blended_score', row.get('overall_score', 50)))
    score = 50.0
    for col, wkey in COMP_MAP.items():
        w = float(weights.get(wkey, 0.0))
        if w == 0.0:
            continue
        comp = _f(row.get(col, 50), 50)
        score += (comp - 50.0) * w
    return float(np.clip(score, 0, 100))


def evaluate_turbo_entry_gate(
    row: Dict[str, Any],
    cfg=None,
    new_this_week: int = 0,
) -> TurboEntryResult:
    """
    Turbo MTF + short-window confirm entry gate.
    PASS → allocate NEW POSITION
    CONFIRM_WAIT → WATCHLIST until price confirms
    WATCHLIST → blocked (turbo/value/churn)
    """
    row = sync_price_change_aliases(row)

    if str(_cfg(cfg, 'ENTRY_DRIVER', 'turbo_mtf')).lower() not in ('turbo_mtf', 'turbo'):
        legacy = _legacy_vmq_entry(row, cfg, new_this_week)
        return TurboEntryResult(
            legacy.allowed,
            legacy.status,
            compute_turbo_score(row, cfg),
            get_confirm_return_pct(row),
            legacy.reasons,
        )

    turbo = compute_turbo_score(row, cfg)
    mom = _f(row.get('hybrid_momentum_technical', 0))
    mtf = _f(row.get('hybrid_multi_timeframe', 0))
    fund = _f(row.get('hybrid_fundamental_quality', 0))
    vs = _f(row.get('hybrid_volume_strength', 0))
    confirm = get_confirm_return_pct(row)

    v2_min = _f(_cfg(cfg, 'TURBO_ENTRY_V2_MIN', _cfg(cfg, 'VMQ_V2_BUY_THRESHOLD', 60.0)))
    mtf_min = _f(_cfg(cfg, 'TURBO_ENTRY_MTF_MIN', 55.0))
    mom_min = _f(_cfg(cfg, 'TURBO_ENTRY_MOM_MIN', 50.0))
    vs_min = _f(_cfg(cfg, 'TURBO_ENTRY_VS_MIN', 0.0))
    confirm_min = _f(_cfg(cfg, 'ENTRY_CONFIRM_3D_MIN_RET', 0.0))
    confirm_strong = _f(_cfg(cfg, 'ENTRY_CONFIRM_3D_STRONG_RET', 2.0))
    max_new = int(_cfg(cfg, 'VMQ_MAX_NEW_PER_WEEK', 3))
    v1_floor = _f(_cfg(cfg, 'ENTRY_V1_SCORE_FLOOR', 55.0))
    v1_score = _f(row.get('final_blended_score', row.get('overall_score', 0)))
    rsi_hard = _f(_cfg(cfg, 'TURBO_ENTRY_RSI_HARD_BLOCK', 75.0))

    reasons: List[str] = []
    value_trap = is_value_trap(fund, mom, cfg)
    turbo_strong = turbo >= v2_min + 5 and mom >= mom_min + 5

    if turbo < v2_min:
        reasons.append(f'turbo {turbo:.1f}<{v2_min:.0f}')
    if mtf < mtf_min:
        reasons.append(f'mtf {mtf:.0f}<{mtf_min:.0f}')
    if mom < mom_min:
        reasons.append(f'mom {mom:.0f}<{mom_min:.0f}')
    if vs_min > 0 and vs < vs_min:
        reasons.append(f'volume_strength {vs:.0f}<{vs_min:.0f}')
    if value_trap and not turbo_strong:
        reasons.append(f'value_trap fund={fund:.0f} mom={mom:.0f}')
    if v1_score > 0 and v1_score < v1_floor:
        reasons.append(f'v1 floor {v1_score:.1f}<{v1_floor:.0f}')
    if new_this_week >= max_new:
        reasons.append(f'churn cap {new_this_week}/{max_new}')

    if reasons:
        return TurboEntryResult(False, 'WATCHLIST', turbo, confirm, reasons)

    extended = evaluate_extended_entry_guards(row, cfg)
    hard_extended = [r for r in extended if 'hard block' in r]
    soft_extended = [r for r in extended if 'hard block' not in r]

    if hard_extended:
        return TurboEntryResult(False, 'WATCHLIST', turbo, confirm, hard_extended)

    if confirm < confirm_min:
        wait_reasons = soft_extended + [
            f'short confirm {confirm:.1f}%<{confirm_min:.0f}% (wait for price)',
        ]
        return TurboEntryResult(False, 'CONFIRM_WAIT', turbo, confirm, wait_reasons)

    if soft_extended:
        return TurboEntryResult(False, 'CONFIRM_WAIT', turbo, confirm, soft_extended)

    pass_reasons: List[str] = []
    if confirm >= confirm_strong:
        pass_reasons.append(f'short confirm strong +{confirm:.1f}%')
    else:
        pass_reasons.append(f'short confirm ok +{confirm:.1f}%')

    return TurboEntryResult(True, 'PASS', turbo, confirm, pass_reasons)


def _legacy_vmq_entry(row: Dict[str, Any], cfg, new_this_week: int) -> VMQEntryResult:
    from src.vmq_strategy import evaluate_entry_gate
    return evaluate_entry_gate(row, cfg, new_this_week=new_this_week)


def enrich_dataframe_with_turbo(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    """Add turbo_score (recomputed), score_v2_ref, entry_confirm_ret."""
    if df is None or df.empty:
        return df
    out = df.copy()
    turbo_scores = []
    v2_refs = []
    confirm_rets = []
    for _, row in out.iterrows():
        d = sync_price_change_aliases(row.to_dict())
        turbo_scores.append(compute_turbo_score(d, cfg))
        v2_refs.append(compute_turbo_score_v2_reference(d))
        confirm_rets.append(get_confirm_return_pct(d))
    out['turbo_score'] = turbo_scores
    out['turbo_score_recomputed'] = turbo_scores
    out['score_v2_ref'] = v2_refs
    out['entry_confirm_ret'] = confirm_rets
    return out


def apply_turbo_entry_to_allocation_df(
    allocation_df: pd.DataFrame,
    history_df: pd.DataFrame,
    cfg=None,
) -> Dict[str, int]:
    """Apply turbo entry driver (delegates to VMQ apply shape for integration)."""
    from src.vmq_strategy import apply_vmq_to_allocation_df

    stats = apply_vmq_to_allocation_df(allocation_df, history_df, cfg)
    return stats
