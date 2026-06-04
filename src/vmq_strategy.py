"""
VMQ (Validated Momentum-Quality) strategy gates.

Pattern-derived entry/validation rules (no IC gate). Blocks value-trap entries,
caps weekly churn, and exits failed 3-day / 5-day / trailing-stop positions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class VMQEntryResult:
    allowed: bool
    status: str
    reasons: List[str] = field(default_factory=list)


def _f(val, default=0.0) -> float:
    try:
        v = float(val)
        return default if (np.isnan(v) or np.isinf(v)) else v
    except (TypeError, ValueError):
        return default


def _cfg(cfg, key: str, default):
    return getattr(cfg, key, default) if cfg is not None else default


def _parse_day3_active_regimes(cfg=None) -> set:
    raw = _cfg(cfg, 'VMQ_DAY3_ACTIVE_REGIMES', 'bear,high_vol')
    if isinstance(raw, (list, tuple, set)):
        items = raw
    else:
        items = str(raw).split(',')
    return {
        str(x).strip().upper().replace('-', '_')
        for x in items
        if str(x).strip()
    }


def day3_validation_active(
    market_regime: str = '',
    vix_level: Optional[float] = None,
    cfg=None,
) -> bool:
    """Return True when day-3/day-5 early validation should run for this context."""
    if not _cfg(cfg, 'VMQ_DAY3_ENABLED', False):
        return False
    if not _cfg(cfg, 'VMQ_DAY3_REGIME_GATED', True):
        return True

    active = _parse_day3_active_regimes(cfg)
    vix_min = _f(_cfg(cfg, 'VMQ_DAY3_VIX_MIN', 25.0))
    if vix_level is not None and _f(vix_level) >= vix_min:
        if 'HIGH_VOL' in active or 'HIGH_VIX' in active:
            return True

    regime_up = str(market_regime or '').upper().strip()
    if not regime_up:
        return 'SIDEWAYS' in active or 'BEAR' in active

    aliases = {
        'BEARISH': 'BEAR',
        'VOLATILE': 'HIGH_VOL',
    }
    regime_norm = aliases.get(regime_up, regime_up)
    if regime_norm in active:
        return True
    if regime_norm == 'BEAR' and 'BEAR' in active:
        return True
    return False


def _normalize_pnl_pct(pnl: float) -> float:
    """Return P&L as percentage points (-8.2 for -8.2%)."""
    if abs(pnl) <= 1.5:
        return pnl * 100.0
    return pnl


def should_skip_day3_validation(
    pnl_pct: float,
    cfg=None,
    turbo_score: Optional[float] = None,
    mtf_score: Optional[float] = None,
) -> Tuple[bool, str]:
    """Skip early day-3/5 when position is a winner or trend/turbo still intact."""
    if not _cfg(cfg, 'VMQ_DAY3_SMART_SKIP', True):
        if pnl_pct > 0:
            return True, f'pnl {pnl_pct:.1f}%>0 (legacy skip)'
        return False, ''

    skip_pnl = _f(_cfg(cfg, 'VMQ_DAY3_SKIP_PNL_MIN', 5.0))
    if pnl_pct > skip_pnl:
        return True, f'pnl {pnl_pct:.1f}%>{skip_pnl:.0f}%'

    if _cfg(cfg, 'VMQ_DAY3_SKIP_IF_TURBO_PASS', True):
        turbo_min = _f(_cfg(cfg, 'VMQ_TURBO_MIN', 65.0))
        turbo = _f(turbo_score, default=-1.0)
        if turbo_score is not None and turbo >= turbo_min:
            return True, f'turbo {turbo:.1f}>={turbo_min:.0f} PASS'

    mtf_min = _f(_cfg(cfg, 'VMQ_DAY3_SKIP_MTF_MIN', 52.0))
    mtf = _f(mtf_score, default=-1.0)
    if mtf_score is not None and mtf >= mtf_min:
        return True, f'mtf {mtf:.1f}>={mtf_min:.0f} intact'

    return False, ''


def _entry_score(row: Dict[str, Any]) -> float:
    for key in (
        'final_blended_score', 'overall_score', 'improved_overall_score',
        'hybrid_overall_score', 'score', 'OVERALL', 'SCORE',
    ):
        v = _f(row.get(key, 0))
        if v > 0:
            return v
    return 0.0


def is_value_trap(fund: float, mom: float, cfg=None) -> bool:
    f_min = _f(_cfg(cfg, 'VMQ_VALUE_TRAP_FUND_MIN', 75.0))
    m_max = _f(_cfg(cfg, 'VMQ_VALUE_TRAP_MOM_MAX', 55.0))
    return fund >= f_min and mom < m_max


def evaluate_entry_gate(
    row: Dict[str, Any],
    cfg=None,
    reason_text: str = '',
    new_this_week: int = 0,
) -> VMQEntryResult:
    """Phase 0: static entry gate for NEW POSITION candidates."""
    if not _cfg(cfg, 'VMQ_ENABLED', True):
        return VMQEntryResult(True, 'PASS', [])

    from src.qmst_pick_gates import evaluate_pick_gates
    pick = evaluate_pick_gates(row, cfg)
    if not pick.allowed:
        return VMQEntryResult(False, 'BLOCK', list(pick.reasons))

    score = _entry_score(row)
    score_v2 = _f(row.get('hybrid_overall_score_v2', row.get('score_v2', score)))
    mom = _f(row.get('hybrid_momentum_technical', 0))
    fund = _f(row.get('hybrid_fundamental_quality', 0))
    mom_floor = _f(_cfg(cfg, 'VMQ_ENTRY_MOM_FLOOR', 45.0))
    score_min = _f(_cfg(cfg, 'VMQ_ENTRY_SCORE_MIN', 0.0))
    gap_max = _f(_cfg(cfg, 'VMQ_V1_V2_GAP_MAX', 15.0))
    max_new = int(_cfg(cfg, 'VMQ_MAX_NEW_PER_WEEK', 3))
    require_v2_buy = bool(_cfg(cfg, 'VMQ_REQUIRE_V2_BUY', False))
    v2_buy_thr = _f(_cfg(cfg, 'VMQ_V2_BUY_THRESHOLD', 60.0))
    require_turbo = bool(_cfg(cfg, 'VMQ_REQUIRE_TURBO_PASS', True))
    turbo_min = _f(_cfg(cfg, 'VMQ_TURBO_MIN', 65.0))

    reasons: List[str] = []
    reason_text = str(reason_text or row.get('final_recommendation', '') or '')

    if mom < mom_floor:
        reasons.append(f'momentum {mom:.0f}<{mom_floor:.0f}')
    if score_min > 0 and score < score_min:
        reasons.append(f'score {score:.1f}<{score_min:.0f}')
    if is_value_trap(fund, mom, cfg):
        reasons.append(f'value_trap fund={fund:.0f} mom={mom:.0f}')
    if 'SIDEWAYS-Q1' in reason_text and is_value_trap(fund, mom, cfg):
        reasons.append('SIDEWAYS-Q1+value_trap')
    gap = abs(score - score_v2) if score_v2 > 0 and score > 0 else 0.0
    if score_v2 > 0 and score > 0 and gap > gap_max:
        reasons.append(f'v1-v2 gap {gap:.1f}>{gap_max:.0f}')
    if require_v2_buy and score_v2 > 0 and score_v2 < v2_buy_thr:
        reasons.append(f'v2 {score_v2:.1f}<{v2_buy_thr:.0f} (turbo proxy HOLD)')
    turbo = _f(row.get('turbo_score', row.get('turbo_score_recomputed', 0)))
    if require_turbo and turbo > 0 and turbo < turbo_min:
        reasons.append(f'turbo {turbo:.1f}<{turbo_min:.0f}')
    if new_this_week >= max_new:
        reasons.append(f'churn cap {new_this_week}/{max_new} this week')

    if reasons:
        return VMQEntryResult(False, 'BLOCK', reasons)
    return VMQEntryResult(True, 'PASS', [])


def count_new_positions_this_week(history_df: pd.DataFrame, as_of: Optional[datetime] = None) -> int:
    if history_df is None or history_df.empty:
        return 0
    as_of = as_of or datetime.now()
    cutoff = as_of - timedelta(days=7)
    df = history_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    mask = (
        df['date'] >= cutoff
    ) & df['action'].astype(str).str.contains('NEW POSITION', na=False)
    return int(mask.sum())


def get_entry_info(symbol: str, history_df: pd.DataFrame) -> Tuple[Optional[datetime], float]:
    """Most recent NEW POSITION for symbol (VMQ validation window anchor)."""
    if history_df is None or history_df.empty:
        return None, 0.0
    sym = str(symbol or '').upper()
    h = history_df[history_df['symbol'].astype(str).str.upper() == sym].copy()
    if h.empty:
        return None, 0.0
    h['date'] = pd.to_datetime(h['date'], errors='coerce')
    buys = h[h['action'].astype(str).str.contains('NEW POSITION', na=False)]
    if buys.empty:
        return None, 0.0
    row = buys.sort_values('date').iloc[-1]
    ep = _f(row.get('price', 0))
    ed = row['date']
    return (ed if pd.notna(ed) else None), ep


def _days_since_entry(
    entry_date: Optional[datetime],
    as_of: Optional[datetime] = None,
) -> Optional[int]:
    if entry_date is None:
        return None
    ref = pd.Timestamp(as_of or datetime.now()).to_pydatetime()
    ent = pd.Timestamp(entry_date).to_pydatetime()
    return (ref - ent).days


def _in_validation_window(
    entry_date: Optional[datetime],
    cfg=None,
    as_of: Optional[datetime] = None,
) -> bool:
    days = _days_since_entry(entry_date, as_of)
    if days is None:
        return False
    max_days = int(_cfg(cfg, 'VMQ_VALIDATION_MAX_DAYS', 21))
    return days <= max_days


def price_return_days(
    history_df: pd.DataFrame,
    symbol: str,
    entry_date: datetime,
    entry_price: float,
    days: int,
) -> Optional[float]:
    if entry_price <= 0 or entry_date is None:
        return None
    sym = str(symbol).upper()
    h = history_df[history_df['symbol'].astype(str).str.upper() == sym].copy()
    h['date'] = pd.to_datetime(h['date'], errors='coerce')
    h['price'] = pd.to_numeric(h['price'], errors='coerce')
    cutoff = pd.Timestamp(entry_date) + pd.Timedelta(days=days)
    post = h[(h['date'] >= pd.Timestamp(entry_date)) & (h['date'] <= cutoff)].sort_values('date')
    if post.empty:
        return None
    px = float(post.iloc[-1]['price'])
    if px <= 0:
        return None
    return (px / entry_price - 1.0) * 100.0


def peak_price_since_entry(
    history_df: pd.DataFrame,
    symbol: str,
    entry_date: datetime,
    entry_price: float,
) -> float:
    sym = str(symbol).upper()
    peak = entry_price
    if history_df is None or history_df.empty or entry_date is None:
        return peak
    h = history_df[history_df['symbol'].astype(str).str.upper() == sym].copy()
    h['date'] = pd.to_datetime(h['date'], errors='coerce')
    h['price'] = pd.to_numeric(h['price'], errors='coerce')
    post = h[h['date'] >= pd.Timestamp(entry_date)]
    if not post.empty:
        peak = max(peak, float(post['price'].max()))
    return peak


def evaluate_holding_validation(
    symbol: str,
    entry_price: float,
    entry_date: Optional[datetime],
    current_price: float,
    current_pnl_pct: float,
    history_df: pd.DataFrame,
    cfg=None,
    sleeve: str = 'TACTICAL',
    action_recommendation: str = '',
    as_of: Optional[datetime] = None,
    market_regime: str = '',
    vix_level: Optional[float] = None,
    enable_day3_validation: Optional[bool] = None,
    turbo_score: Optional[float] = None,
    mtf_score: Optional[float] = None,
) -> Optional[Tuple[str, str]]:
    """
    Phase 1-3: validation exits for held positions.
    Day-3/5 only for recent NEW POSITION entries; CORE skips early validation.
    """
    if not _cfg(cfg, 'VMQ_ENABLED', True):
        return None

    pnl_pct = _normalize_pnl_pct(current_pnl_pct)
    sleeve_up = str(sleeve).upper()
    is_core = sleeve_up == 'CORE'
    fail_3d = _f(_cfg(cfg, 'VMQ_VALIDATION_FAIL_3D', -2.0))
    fail_5d = _f(_cfg(cfg, 'VMQ_VALIDATION_FAIL_5D', 0.0))
    swing_stop = _f(_cfg(cfg, 'VMQ_SWING_STOP_PCT', -5.0))
    hard_stop = _f(_cfg(cfg, 'VMQ_HARD_STOP_PCT', -8.0))
    trail_pct = _f(_cfg(cfg, 'VMQ_TRAIL_STOP_PCT', 0.08))

    if pnl_pct <= hard_stop:
        return ('SELL', f'VMQ HARD STOP: loss {pnl_pct:.1f}% <= {hard_stop:.0f}%')

    if not is_core and pnl_pct <= swing_stop:
        return ('SELL', f'VMQ SWING STOP: loss {pnl_pct:.1f}% <= {swing_stop:.0f}%')

    act_up = str(action_recommendation or '').upper()
    if 'WEAK SELL' in act_up and not is_core and pnl_pct < 0:
        return ('SELL', 'VMQ WEAK SELL: TACTICAL fast exit')

    run_day3 = (
        enable_day3_validation
        if enable_day3_validation is not None
        else True
    )
    in_window = _in_validation_window(entry_date, cfg, as_of=as_of)
    if (
        run_day3
        and day3_validation_active(market_regime, vix_level, cfg)
        and in_window
        and entry_price > 0
        and entry_date is not None
        and not is_core
    ):
        skip, _skip_reason = should_skip_day3_validation(
            pnl_pct, cfg, turbo_score=turbo_score, mtf_score=mtf_score,
        )
        if not skip and history_df is not None:
            days_held = _days_since_entry(entry_date, as_of) or 0
            r3 = price_return_days(history_df, symbol, entry_date, entry_price, 3)
            r5 = price_return_days(history_df, symbol, entry_date, entry_price, 5)
            if days_held >= 3 and r3 is not None and r3 < fail_3d:
                return ('SELL', f'VMQ DAY-3 FAIL: {r3:.1f}% < {fail_3d:.0f}% vs entry')
            if days_held >= 5 and r5 is not None and r5 < fail_5d:
                return ('SELL', f'VMQ DAY-5 FAIL: {r5:.1f}% < {fail_5d:.0f}% vs entry')

    if entry_date is not None and entry_price > 0:
        peak = peak_price_since_entry(history_df, symbol, entry_date, entry_price)
        if peak > 0 and current_price > 0:
            dd_from_peak = (current_price / peak) - 1.0
            if dd_from_peak <= -trail_pct and pnl_pct > hard_stop:
                return ('SELL', f'VMQ TRAIL STOP: {dd_from_peak*100:.1f}% from peak ₹{peak:.2f}')

    return None


def _exit_priority(reason: str, pnl_pct: float) -> Tuple[int, float]:
    """Lower sort key = higher priority to exit."""
    r = reason.upper()
    if 'HARD STOP' in r:
        return (0, pnl_pct)
    if 'SWING STOP' in r:
        return (1, pnl_pct)
    if 'DAY-3' in r or 'DAY-5' in r:
        return (2, pnl_pct)
    if 'TRAIL' in r:
        return (3, pnl_pct)
    if 'WEAK SELL' in r:
        return (4, pnl_pct)
    return (5, pnl_pct)


def apply_vmq_to_allocation_df(
    allocation_df: pd.DataFrame,
    history_df: pd.DataFrame,
    cfg=None,
    market_regime: str = '',
    vix_level: Optional[float] = None,
) -> Dict[str, int]:
    """
    Apply VMQ gates to allocation_df in place.
    Returns stats dict for logging.
    """
    stats = {'entry_blocked': 0, 'increase_blocked': 0, 'exit_forced': 0, 'watchlist': 0, 'exit_capped': 0}
    if allocation_df is None or allocation_df.empty:
        return stats
    if not _cfg(cfg, 'VMQ_ENABLED', True):
        return stats

    if 'vmq_status' not in allocation_df.columns:
        allocation_df['vmq_status'] = ''
    if 'vmq_reason' not in allocation_df.columns:
        allocation_df['vmq_reason'] = ''

    new_this_week = count_new_positions_this_week(history_df)
    approved_this_run = 0
    max_new = int(_cfg(cfg, 'VMQ_MAX_NEW_PER_WEEK', 3))
    max_exits = int(_cfg(cfg, 'VMQ_MAX_EXITS_PER_RUN', 5))
    pending_exits: List[Tuple[int, str, str, float]] = []

    def _invest_amount(row_obj) -> float:
        for col in ('investment_amount', 'INVEST ₹', 'invest_amount'):
            v = row_obj.get(col)
            if v is not None and pd.notna(v):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return 0.0

    def _apply_turbo_entry_block(idx, row_dict, block_prefix: str, stat_key: str) -> bool:
        """Run turbo entry gate; mutate row to blocked state. Returns True if blocked."""
        from src.lowvol_momentum import active_lvm_eligible_col, is_lvm_strategy
        if (bool(_cfg(cfg, 'LVM_BYPASS_TURBO_GATE', True))
                and is_lvm_strategy(cfg)
                and row_dict.get(active_lvm_eligible_col(cfg), False)):
            return False
        driver = str(_cfg(cfg, 'ENTRY_DRIVER', 'turbo_mtf')).lower()
        if driver in ('turbo_mtf', 'turbo'):
            from src.turbo_entry import evaluate_turbo_entry_gate
            result = evaluate_turbo_entry_gate(
                row_dict, cfg, new_this_week=new_this_week + approved_this_run,
            )
            allowed = result.allowed
            status = result.status
            reasons = result.reasons
            allocation_df.at[idx, 'turbo_score'] = result.turbo_score
            allocation_df.at[idx, 'entry_confirm_ret'] = result.confirm_ret
        else:
            result = evaluate_entry_gate(
                row_dict, cfg,
                reason_text=str(row_dict.get('exit_reason', row_dict.get('REASON', ''))),
                new_this_week=new_this_week + approved_this_run,
            )
            allowed = result.allowed
            status = result.status
            reasons = result.reasons

        if allowed:
            return False

        _watch_reason = '; '.join(reasons)
        _watch_label = 'CONFIRM WAIT' if status == 'CONFIRM_WAIT' else 'WATCHLIST'
        if block_prefix == 'INCREASE':
            allocation_df.at[idx, 'action_recommendation'] = 'HOLD'
            allocation_df.at[idx, 'action_type'] = 'HOLD'
            block_msg = f"TURBO BLOCK (INCREASE): {_watch_reason}"
        else:
            allocation_df.at[idx, 'action_recommendation'] = _watch_label
            allocation_df.at[idx, 'action_type'] = _watch_label
            block_msg = (
                f"TURBO BLOCK: {_watch_reason}" if driver in ('turbo_mtf', 'turbo')
                else f"VMQ BLOCK: {_watch_reason}"
            )
        allocation_df.at[idx, 'investment_amount'] = 0
        allocation_df.at[idx, 'suggested_quantity'] = 0
        if 'INVEST ₹' in allocation_df.columns:
            allocation_df.at[idx, 'INVEST ₹'] = 0
        if 'BUY QTY' in allocation_df.columns:
            allocation_df.at[idx, 'BUY QTY'] = 0
        allocation_df.at[idx, 'vmq_status'] = status
        allocation_df.at[idx, 'vmq_reason'] = _watch_reason
        allocation_df.at[idx, 'exit_reason'] = block_msg
        allocation_df.at[idx, 'action_reason'] = block_msg
        stats[stat_key] += 1
        stats['watchlist'] += 1
        return True

    for idx, row in allocation_df.iterrows():
        sym = str(row.get('symbol', '')).upper()
        act = str(row.get('action_recommendation', row.get('ACTION', ''))).upper()
        action_type = str(row.get('action_type', '')).upper()
        is_holding = bool(row.get('is_current_holding', False))
        is_new = (
            not is_holding
            and 'WATCHLIST' not in act
            and 'WATCHLIST' not in action_type
            and (
                'NEW POSITION' in act
                or 'NEW POSITION' in action_type
                or ('BUY' in act and 'SELL' not in act)
            )
        )

        if is_new and not is_holding:
            row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
            if not _apply_turbo_entry_block(idx, row_dict, 'NEW', 'entry_blocked'):
                approved_this_run += 1
                allocation_df.at[idx, 'vmq_status'] = 'PASS'
                allocation_df.at[idx, 'vmq_reason'] = 'entry_gate'

        is_increase = (
            is_holding
            and (
                'INCREASE' in act
                or 'INCREASE' in action_type
            )
            and _invest_amount(row) > 0
        )
        if is_increase:
            row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
            _apply_turbo_entry_block(idx, row_dict, 'INCREASE', 'increase_blocked')

        if is_holding:
            entry_date, entry_price = get_entry_info(sym, history_df)
            cur_px = _f(row.get('current_price', 0))
            pnl = row.get('current_profit_pct', 0)
            try:
                pnl_f = float(pnl) if pnl is not None and pd.notna(pnl) else 0.0
            except (TypeError, ValueError):
                pnl_f = 0.0
            sleeve = str(row.get('sleeve', 'TACTICAL') or 'TACTICAL')
            turbo = row.get('turbo_score', row.get('turbo_score_recomputed'))
            mtf = row.get('hybrid_multi_timeframe')
            try:
                turbo_f = float(turbo) if turbo is not None and pd.notna(turbo) else None
            except (TypeError, ValueError):
                turbo_f = None
            try:
                mtf_f = float(mtf) if mtf is not None and pd.notna(mtf) else None
            except (TypeError, ValueError):
                mtf_f = None
            override = evaluate_holding_validation(
                sym, entry_price, entry_date, cur_px, pnl_f,
                history_df, cfg, sleeve=sleeve,
                action_recommendation=str(row.get('action_recommendation', '')),
                market_regime=market_regime,
                vix_level=vix_level,
                turbo_score=turbo_f,
                mtf_score=mtf_f,
            )
            if override:
                new_act, reason = override
                pending_exits.append((idx, sym, reason, _normalize_pnl_pct(pnl_f)))

    if pending_exits:
        pending_exits.sort(key=lambda x: _exit_priority(x[2], x[3]))
        allowed = pending_exits[:max_exits]
        capped = pending_exits[max_exits:]
        for idx, _sym, reason, _pnl in allowed:
            allocation_df.at[idx, 'action_recommendation'] = 'SELL'
            allocation_df.at[idx, 'exit_reason'] = reason
            allocation_df.at[idx, 'action_reason'] = reason
            allocation_df.at[idx, 'vmq_status'] = 'EXIT'
            allocation_df.at[idx, 'vmq_reason'] = reason
            allocation_df.at[idx, 'profit_booking_pct'] = 1.0
            allocation_df.at[idx, 'priority'] = 'HIGH'
            stats['exit_forced'] += 1
        stats['exit_capped'] = len(capped)
        for idx, sym, reason, _pnl in capped:
            if str(allocation_df.at[idx, 'action_recommendation']).upper() == 'SELL':
                allocation_df.at[idx, 'action_recommendation'] = 'CONSIDER SELLING'
                allocation_df.at[idx, 'profit_booking_pct'] = 0.25
                allocation_df.at[idx, 'vmq_reason'] = f'VMQ capped (max {max_exits}/run): {reason}'
                allocation_df.at[idx, 'exit_reason'] = (
                    f"VMQ deferred — exit cap {max_exits}/run | {reason[:50]}"
                )

    return stats
