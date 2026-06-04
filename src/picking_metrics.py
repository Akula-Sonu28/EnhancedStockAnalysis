"""
Stock-picking measurement and rank helpers.

Separates *rank-surface* rows (HOLD / BUY / WATCHLIST) from forced-exit rows
(SELL / REDUCE / BOOK_PROFIT) so IC and quintile stats measure picking, not
exit timing.  Used by v2 calibration, promotion check, and allocation sort.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

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
    'hybrid_momentum_technical': 'momentum_technical',
    'hybrid_volume_strength': 'volume_strength',
    'hybrid_multi_timeframe': 'multi_timeframe',
    'hybrid_ml_signal': 'ml_signal',
    'hybrid_risk_adjustment': 'risk_adjustment',
    'hybrid_growth': 'growth',
    'hybrid_value': 'value',
}

# Forced-exit / profit-booking actions contaminate score→return IC.
_EXIT_ACTION_RE = re.compile(
    r'SELL|EXIT|REDUCE|BOOK|WEAK|SCALE[\s_]?OUT|SWAP|TRIM|CONSIDER\s+SELL',
    re.IGNORECASE,
)

_RANK_SURFACE_RE = re.compile(
    r'HOLD|WATCHLIST|NEW\s+POSITION|INCREASE|STRONG\s+BUY|\bBUY\b|'
    r'HIGH\s+MOMENTUM|CONSIDER\s+BUY|CONFIRM',
    re.IGNORECASE,
)


def filter_rank_surface(df: pd.DataFrame) -> pd.DataFrame:
    """Keep rows suitable for cross-sectional picking IC (exclude forced exits)."""
    if df is None or df.empty:
        return df
    if 'action' not in df.columns:
        return df
    act = df['action'].astype(str)
    exit_mask = act.str.contains(_EXIT_ACTION_RE, na=False)
    return df.loc[~exit_mask].copy()


def synthesise_v2_score(df: pd.DataFrame, weights: dict) -> pd.Series:
    """v2 = 50 + sum((component_i - 50) * weight_i); NaN if no components."""
    if df is None or len(df) == 0:
        return pd.Series(dtype=float)
    deviation = pd.Series(0.0, index=df.index)
    has_any = pd.Series(False, index=df.index)
    for comp_col, weight_key in WEIGHT_KEY_FROM_COMPONENT.items():
        if comp_col not in df.columns:
            continue
        w = float(weights.get(weight_key, 0.0))
        if w == 0.0:
            continue
        comp = pd.to_numeric(df[comp_col], errors='coerce')
        has_any = has_any | comp.notna()
        deviation = deviation.add(((comp - 50.0) * w).fillna(0.0), fill_value=0.0)
    score_v2 = (50.0 + deviation).clip(lower=0.0, upper=100.0)
    return score_v2.where(has_any, other=np.nan)


def spearman_ic(
    score: pd.Series,
    ret: pd.Series,
) -> Tuple[Optional[float], Optional[float], int]:
    from scipy.stats import spearmanr

    joint = pd.concat([score, ret], axis=1).dropna()
    if len(joint) < 30:
        return None, None, len(joint)
    rho, p = spearmanr(joint.iloc[:, 0], joint.iloc[:, 1])
    if pd.isna(rho):
        return None, None, len(joint)
    return float(rho), float(p), int(len(joint))


def quintile_spread(
    score: pd.Series,
    ret: pd.Series,
    n_quantiles: int = 5,
) -> Tuple[Optional[float], Optional[float], Optional[float], int]:
    """Returns (q5_mean, q1_mean, spread, n). ret in percent units."""
    joint = pd.concat([score, ret], axis=1).dropna()
    joint.columns = ['s', 'r']
    if len(joint) < 25:
        return None, None, None, len(joint)
    try:
        joint['_q'] = pd.qcut(joint['s'], n_quantiles, labels=False, duplicates='drop')
    except ValueError:
        return None, None, None, len(joint)
    q5 = float(joint[joint['_q'] == joint['_q'].max()]['r'].mean())
    q1 = float(joint[joint['_q'] == joint['_q'].min()]['r'].mean())
    return q5, q1, q5 - q1, int(len(joint))


def fill_score_v2_column(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Fill missing score_v2 from hybrid_* + calibrated weights."""
    out = df.copy()
    synth = synthesise_v2_score(out, weights)
    if 'score_v2' not in out.columns:
        out['score_v2'] = synth
    else:
        missing = out['score_v2'].isna()
        out.loc[missing, 'score_v2'] = synth.loc[missing]
    return out


def _cfg(cfg, key: str, default: Any) -> Any:
    if cfg is None:
        try:
            from config import get_config
            cfg = get_config()
        except Exception:
            return default
    return getattr(cfg, key, default)


def resolve_picking_rank_value(row: Dict[str, Any], cfg=None) -> float:
    """Single-row rank for sorting (higher = stronger pick)."""
    driver = str(_cfg(cfg, 'PICKING_RANK_DRIVER', 'auto')).lower()
    entry = str(_cfg(cfg, 'ENTRY_DRIVER', 'turbo_mtf')).lower()

    if driver in ('lowvol_mom', 'low_vol_momentum', 'quality_lvm'):
        for k in ('quality_lvm_score', 'lowvol_mom_score', 'picking_rank'):
            v = row.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass

    if driver in ('turbo', 'turbo_mtf') or (
        driver == 'auto' and entry in ('turbo_mtf', 'turbo')
    ):
        for k in ('picking_rank', 'turbo_score'):
            v = row.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass

    if driver in ('v2', 'v2_synth', 'auto'):
        for k in ('picking_rank', 'hybrid_overall_score_v2', 'score_v2', 'overall_score_v2'):
            v = row.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass

    for k in ('final_blended_score', 'hybrid_overall_score', 'overall_score_with_value', 'overall_score'):
        v = row.get(k)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 50.0


def add_picking_rank_column(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    """Add `picking_rank` for allocation / entry sorting."""
    if df is None or df.empty:
        return df
    out = df.copy()
    driver = str(_cfg(cfg, 'PICKING_RANK_DRIVER', 'auto')).lower()
    entry = str(_cfg(cfg, 'ENTRY_DRIVER', 'turbo_mtf')).lower()

    rank = pd.Series(np.nan, index=out.index, dtype=float)

    if driver in ('lowvol_mom', 'low_vol_momentum', 'quality_lvm'):
        try:
            from src.lowvol_momentum import (
                active_lvm_score_col,
                compute_active_lvm_score,
            )
            scol = active_lvm_score_col(cfg)
            if scol not in out.columns:
                out = compute_active_lvm_score(out, cfg)
            if scol in out.columns:
                rank = pd.to_numeric(out[scol], errors='coerce')
        except Exception as e:
            logging.warning(f"LVM family scoring failed in picking_rank: {e}")

    if driver in ('flow_quality', 'fq', 'oracle_pick'):
        try:
            from src.flow_quality_oracle import enrich_oracle_columns
            out = enrich_oracle_columns(out, cfg)
        except Exception:
            pass
        active = str(out.get('active_oracle', pd.Series(['fq_score'])).iloc[0] if len(out) else 'fq_score')
        col = 'volume_pick_score' if active == 'volume_only' else (
            'fq_adapt_score' if active == 'fq_adapt' else 'fq_score'
        )
        if col in out.columns:
            rank = pd.to_numeric(out[col], errors='coerce')

    if driver in ('turbo', 'turbo_mtf') or (
        driver == 'auto' and entry in ('turbo_mtf', 'turbo')
    ):
        if 'turbo_score' in out.columns:
            rank = pd.to_numeric(out['turbo_score'], errors='coerce')

    if driver in ('v2', 'v2_synth') or (driver == 'auto' and rank.isna().all()):
        for col in ('hybrid_overall_score_v2', 'score_v2', 'overall_score_v2'):
            if col in out.columns:
                v2 = pd.to_numeric(out[col], errors='coerce')
                rank = rank.fillna(v2)

    for col in ('final_blended_score', 'hybrid_overall_score', 'overall_score_with_value', 'overall_score'):
        if col in out.columns:
            rank = rank.fillna(pd.to_numeric(out[col], errors='coerce'))

    out['picking_rank'] = rank.fillna(50.0)
    return out


def oracle_stack_align_enabled(cfg=None) -> bool:
    """When True, holdings exit rank and sector trim use oracle stack scores."""
    return bool(_cfg(cfg, 'ORACLE_STACK_ALIGN', True))


def qmst_enabled(cfg=None) -> bool:
    """Master switch for QMST layer labels, history fields, and report badge."""
    return bool(_cfg(cfg, 'QMST_ENABLED', True))


def holdings_rank_metric_label(cfg=None) -> str:
    """Human label for holdings rank metric in REASON strings."""
    if qmst_enabled(cfg) and oracle_stack_align_enabled(cfg):
        return 'Pick rank'
    return 'Score'


def format_rank_metric_clause(rank_score: float, cfg=None) -> str:
    """Single metric clause for holdings REASON, e.g. 'Pick rank: -32.8'."""
    try:
        val = float(rank_score)
    except (TypeError, ValueError):
        val = 50.0
    return f"{holdings_rank_metric_label(cfg)}: {val:.1f}"


def format_holdings_reason(
    rank: int,
    total: int,
    pick_rank: float,
    oracle_aligned: bool = True,
    prefix: str = '',
    extra_parts: Optional[Tuple[str, ...]] = None,
) -> str:
    """Format holdings REASON with correct Pick rank vs Score label."""
    label = 'Pick rank' if oracle_aligned else 'Score'
    try:
        rank_val = float(pick_rank)
    except (TypeError, ValueError):
        rank_val = 50.0
    parts: List[str] = []
    if prefix:
        parts.append(prefix)
    parts.append(f"(Rank #{rank}/{total})")
    parts.append(f"{label}: {rank_val:.1f}")
    if extra_parts:
        parts.extend(extra_parts)
    return ' | '.join(parts)


def resolve_holdings_rank_score(row: Dict[str, Any], cfg=None) -> float:
    """Rank score for holdings 30/50/20 rule and sector overweight trim."""
    if oracle_stack_align_enabled(cfg):
        for k in ('picking_rank', 'lowvol_mom_score', 'fq_score', 'turbo_score'):
            v = row.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        vol = row.get('hybrid_volume_strength', row.get('volume_strength'))
        mom = row.get('hybrid_momentum_technical', row.get('momentum_technical'))
        if vol is not None or mom is not None:
            try:
                from src.flow_quality_oracle import compute_flow_quality_adapt
                return float(compute_flow_quality_adapt(
                    vol if vol is not None else 50.0,
                    mom if mom is not None else 50.0,
                    cfg,
                ))
            except Exception:
                pass
        return resolve_picking_rank_value(row, cfg)
    for k in ('overall_score', 'final_blended_score', 'hybrid_overall_score'):
        v = row.get(k)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 50.0


def enrich_results_df_oracle_stack(
    df: pd.DataFrame,
    cfg=None,
    history_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Add fq_score, turbo_score, picking_rank, NSE shadow, stack display labels."""
    if df is None or df.empty or not oracle_stack_align_enabled(cfg):
        return df
    try:
        from src.flow_quality_oracle import enrich_oracle_columns
        from src.turbo_entry import enrich_dataframe_with_turbo

        out = enrich_oracle_columns(df, cfg, history_df)
        out = enrich_dataframe_with_turbo(out, cfg)
        out = add_picking_rank_column(out, cfg)
        try:
            from src.nse_flow_data import enrich_nse_flow_shadow_columns
            out = enrich_nse_flow_shadow_columns(out, cfg)
        except Exception:
            pass
        return apply_oracle_stack_display_labels(out, cfg)
    except Exception:
        return df


def resolve_validation_score(stock_data: Dict[str, Any], cfg=None) -> float:
    """Score for recommendation_history validation (oracle rank when aligned)."""
    if oracle_stack_align_enabled(cfg):
        return resolve_holdings_rank_score(stock_data, cfg)
    for k in ('final_blended_score', 'overall_score_with_value', 'overall_score'):
        v = stock_data.get(k)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 50.0


def derive_single_stock_stack_label(row: Dict[str, Any], cfg=None) -> str:
    """Per-stock oracle label before cross-sectional watchlist is applied."""
    if not oracle_stack_align_enabled(cfg):
        return str(row.get('final_recommendation', row.get('phase2_recommendation', '🟡 HOLD')))
    try:
        from src.turbo_entry import compute_turbo_score
        turbo = compute_turbo_score(row, cfg)
        fq = resolve_holdings_rank_score(row, cfg)
        turbo_min = float(_cfg(cfg, 'VMQ_TURBO_MIN', 65.0)) - 5.0
        if turbo >= turbo_min and fq >= 50.0:
            return '🎯 ORACLE+TURBO ELIGIBLE'
        if fq >= 45.0:
            return '📋 ORACLE CANDIDATE'
        return '⚪ OUT OF ORACLE POOL'
    except Exception:
        return '⚪ OUT OF ORACLE POOL'


def apply_oracle_stack_display_labels(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    """Replace final_recommendation with stack labels; preserve v1_audit_recommendation."""
    if df is None or df.empty or not oracle_stack_align_enabled(cfg):
        return df
    out = df.copy()
    if 'v1_audit_recommendation' not in out.columns:
        if 'phase2_recommendation' in out.columns:
            out['v1_audit_recommendation'] = out['phase2_recommendation']
        elif 'final_recommendation' in out.columns:
            out['v1_audit_recommendation'] = out['final_recommendation'].copy()
        else:
            out['v1_audit_recommendation'] = '📊 V1 AUDIT N/A'
    turbo_min = float(_cfg(cfg, 'VMQ_TURBO_MIN', 65.0)) - 5.0
    labels = []
    for _, row in out.iterrows():
        watch = bool(row.get('on_oracle_watchlist', False))
        turbo = pd.to_numeric(row.get('turbo_score'), errors='coerce')
        if watch and pd.notna(turbo) and float(turbo) >= turbo_min:
            labels.append('🎯 ORACLE+TURBO POOL')
        elif watch:
            labels.append('📋 ORACLE WATCHLIST')
        else:
            labels.append('⚪ OUT OF ORACLE POOL')
    out['oracle_stack_recommendation'] = labels
    out['final_recommendation'] = labels
    return out


def effective_allocation_score(row: Dict[str, Any], cfg=None) -> float:
    """Display/rank score for allocation rows (oracle rank when aligned)."""
    if oracle_stack_align_enabled(cfg):
        for k in ('picking_rank', 'fq_score', 'turbo_score'):
            v = row.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
    for k in (
        'risk_adjusted_score', 'final_blended_score', 'overall_score',
        'hybrid_overall_score', 'improved_score_used',
    ):
        v = row.get(k)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            try:
                f = float(v)
                if f > 0:
                    return f
            except (TypeError, ValueError):
                pass
    return 50.0


def classify_sell_category(row: Dict[str, Any]) -> str:
    """
    Human-readable sell driver for action plan / Excel SELL WHY column.
    Priority-ordered: VMQ > unified hard-stop > rank/rebalance > other.
    """
    act = str(row.get('action_recommendation', row.get('ACTION', ''))).upper()
    if 'LVM ROTATION' in act:
        return 'LVM_ROTATION'
    if 'SWAP' in act:
        return 'SWAP_ROTATION'
    if 'CONSIDER' in act and 'SELL' in act:
        _base = classify_sell_category({**row, 'action_recommendation': 'SELL'})
        if _base != 'OTHER':
            return f'CONSIDER_{_base}'

    reason = ' '.join(
        str(row.get(k, '') or '')
        for k in ('vmq_reason', 'exit_reason', 'action_reason', 'REASON', 'exit_strategy')
    ).upper()
    tier = str(row.get('hard_stop_tier', '') or '').upper()

    if 'VMQ HARD STOP' in reason or (tier == 'HARD_STOP' and 'VMQ' in reason):
        return 'VMQ_HARD_STOP'
    if 'VMQ SWING STOP' in reason or 'SWING STOP' in reason:
        return 'VMQ_SWING_STOP'
    if 'VMQ DAY-3' in reason or 'DAY-3 FAIL' in reason:
        return 'VMQ_DAY3_FAIL'
    if 'VMQ DAY-5' in reason or 'DAY-5 FAIL' in reason:
        return 'VMQ_DAY5_FAIL'
    if 'VMQ TRAIL' in reason or tier == 'TRAILING_STOP':
        return 'VMQ_TRAIL_STOP'
    if tier in ('EMERGENCY', 'HARD_STOP', 'SOFT_STOP') or 'HARD STOP' in reason:
        return 'UNIFIED_HARD_STOP'
    if tier == 'THESIS_BREAK' or 'THESIS BREAK' in reason:
        return 'THESIS_BREAK'
    if 'EMERGENCY EXIT' in reason or tier == 'EMERGENCY':
        return 'EMERGENCY_EXIT'
    if 'UNDERPERFORMER' in reason or 'CUT LOSSES' in reason or 'WEAK FUNDAMENTALS' in reason:
        return 'RANK_BOTTOM_EXIT'
    if 'REBALANCE' in reason or 'CONSIDER' in act:
        return 'RANK_REBALANCE'
    if 'HOLD STEADY' in reason and 'SELL' in act:
        return 'PORTFOLIO_CATEGORY_SELL'
    if 'ORACLE_NO_RANK_SELL' in reason or 'CORE_NO_RANK_SELL' in reason:
        return 'RANK_DISABLED_HOLD'
    if 'PROFIT PROTECTED' in reason:
        return 'PROFIT_PROTECTED_HOLD'
    if 'SELL' in act:
        return 'OTHER_SELL'
    return 'NOT_SELL'


SELL_CATEGORY_LABELS = {
    'SWAP_ROTATION': 'Swap rotation (sell weak → fund stronger pick)',
    'VMQ_HARD_STOP': 'VMQ hard stop (loss beyond -8%)',
    'VMQ_SWING_STOP': 'VMQ swing stop (loss beyond -5%)',
    'VMQ_DAY3_FAIL': 'VMQ day-3 validation fail',
    'VMQ_DAY5_FAIL': 'VMQ day-5 validation fail',
    'VMQ_TRAIL_STOP': 'VMQ trailing stop from peak',
    'UNIFIED_HARD_STOP': 'Unified hard/soft stop (P&L + score)',
    'THESIS_BREAK': 'Thesis break (fundamentals deteriorated)',
    'EMERGENCY_EXIT': 'Emergency exit (deep loss + weak score)',
    'RANK_BOTTOM_EXIT': 'Rank bottom 20% (legacy rank trim)',
    'RANK_REBALANCE': 'Rank rebalance / consider trim',
    'PORTFOLIO_CATEGORY_SELL': 'Portfolio category trim (40/30/20/10 overflow — conflicts with rank HOLD)',
    'RANK_DISABLED_HOLD': 'Rank sell disabled (oracle stack — should HOLD)',
    'OTHER_SELL': 'Other sell signal',
    'NOT_SELL': 'Not a sell action',
    'LVM_ROTATION': 'LVM rotation (not in active Top-N roster — rotate out)',
}


def populate_sell_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Add sell_category column from action + exit_reason."""
    if df is None or df.empty:
        return df
    out = df.copy()
    out['sell_category'] = out.apply(
        lambda r: classify_sell_category(r.to_dict() if hasattr(r, 'to_dict') else dict(r)),
        axis=1,
    )
    return out


def backfill_allocation_from_results(
    allocation_df: pd.DataFrame,
    results_df: pd.DataFrame,
    cfg=None,
) -> pd.DataFrame:
    """Fill sector, volatility, and effective scores from analysis results."""
    if allocation_df is None or allocation_df.empty or results_df is None or results_df.empty:
        return allocation_df
    out = allocation_df.copy()
    if 'symbol' not in out.columns or 'symbol' not in results_df.columns:
        return out

    _res = results_df.copy()
    _res['_sym_u'] = _res['symbol'].astype(str).str.upper()
    _res_idx = _res.set_index('_sym_u', drop=False)

    for idx, row in out.iterrows():
        sym = str(row.get('symbol', '')).upper()
        if sym not in _res_idx.index:
            continue
        src = _res_idx.loc[sym]
        if isinstance(src, pd.DataFrame):
            src = src.iloc[0]

        if 'sector' not in out.columns:
            out['sector'] = 'Unknown'
        _cur_sector = str(out.at[idx, 'sector']).strip().lower()
        if _cur_sector in ('', 'unknown', 'nan', '0', 'none'):
            for _sec_src in ('sector', 'industry', 'sector_name'):
                _sec_val = src.get(_sec_src)
                if _sec_val is not None and str(_sec_val).strip().lower() not in (
                    '', 'unknown', 'nan', '0', 'none',
                ):
                    out.at[idx, 'sector'] = str(_sec_val).strip()
                    break

        for _sc_col in ('overall_score',):
            if _sc_col not in out.columns:
                continue
            cur = pd.to_numeric(out.at[idx, _sc_col], errors='coerce')
            if pd.isna(cur) or float(cur) <= 0:
                for _fb in ('final_blended_score', 'risk_adjusted_score', 'hybrid_overall_score'):
                    fb = pd.to_numeric(src.get(_fb), errors='coerce')
                    if pd.notna(fb) and float(fb) > 0:
                        out.at[idx, _sc_col] = float(fb)
                        break

        _v6 = pd.to_numeric(src.get('volatility_6m'), errors='coerce')
        if pd.notna(_v6) and float(_v6) > 0:
            if 'volatility_6m' in out.columns:
                if pd.isna(pd.to_numeric(out.at[idx, 'volatility_6m'], errors='coerce')):
                    out.at[idx, 'volatility_6m'] = float(_v6)
            if 'volatility' in out.columns:
                _vc = pd.to_numeric(out.at[idx, 'volatility'], errors='coerce')
                if pd.isna(_vc) or float(_vc) <= 0:
                    out.at[idx, 'volatility'] = float(_v6)

        for _pc in ('picking_rank', 'fq_score', 'turbo_score', 'lowvol_mom_score', 'quality_lvm_score'):
            if _pc in out.columns and pd.isna(pd.to_numeric(out.at[idx, _pc], errors='coerce')):
                if _pc in src.index and pd.notna(pd.to_numeric(src.get(_pc), errors='coerce')):
                    out.at[idx, _pc] = src.get(_pc)

        for _ecol in ('lowvol_mom_eligible', 'quality_lvm_eligible'):
            if _ecol not in out.columns:
                out[_ecol] = False
            if _ecol in src.index:
                _lvm_val = src.get(_ecol)
                if _lvm_val is not None and not (isinstance(_lvm_val, float) and np.isnan(_lvm_val)):
                    out.at[idx, _ecol] = bool(_lvm_val)

        for _hyb in HYBRID_COLS:
            if _hyb not in out.columns:
                out[_hyb] = np.nan
            _hc = pd.to_numeric(out.at[idx, _hyb], errors='coerce')
            if pd.isna(_hc) or float(_hc) == 50.0:
                _sv = pd.to_numeric(src.get(_hyb), errors='coerce')
                if pd.notna(_sv) and float(_sv) != 50.0:
                    out.at[idx, _hyb] = float(_sv)

    if 'sector' in out.columns:
        out['sector'] = out['sector'].apply(
            lambda s: 'Unknown' if s is None or (isinstance(s, float) and np.isnan(s))
            else (str(s).strip() or 'Unknown')
        )
    return out


def evaluate_picking_panel(
    df: pd.DataFrame,
    *,
    score_col: str = 'score',
    ret_col: str = 'return_30d',
    rank_surface_only: bool = True,
    weights: Optional[dict] = None,
) -> dict:
    """IC + quintile spread on a history/outcomes dataframe."""
    if df is None or df.empty:
        return {'status': 'EMPTY', 'n': 0}

    work = df.copy()
    if rank_surface_only:
        work = filter_rank_surface(work)

    if weights and score_col == 'score_v2':
        work = fill_score_v2_column(work, weights)
    elif weights and score_col != 'score_v2':
        work['score_v2'] = synthesise_v2_score(work, weights)
        score_col = 'score_v2'

    if score_col not in work.columns:
        return {'status': 'NO_SCORE_COL', 'n': len(work)}

    score = pd.to_numeric(work[score_col], errors='coerce')
    ret = pd.to_numeric(work.get(ret_col), errors='coerce')
    rho, p, n = spearman_ic(score, ret)
    q5, q1, spread, _ = quintile_spread(score, ret)

    return {
        'status': 'OK' if n >= 30 else 'INSUFFICIENT',
        'score_col': score_col,
        'n': n,
        'ic_rho': rho,
        'ic_p': p,
        'q5_mean_pct': q5,
        'q1_mean_pct': q1,
        'spread_pp': spread,
        'rank_surface_rows': len(work),
    }
