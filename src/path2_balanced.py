"""
Path 2 (Balanced) strategy layer.

1. Soften rank-based SELLs to CONSIDER when P&L is flat/small (-3% to +3%).
2. Fast-track one half-size BREAKOUT NEW per week from Breakout Radar.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set

import pandas as pd

from src.breakout_radar import pick_fast_track_symbol, scan_dataframe, TIER_IGNITE, TIER_READY
from src.vmq_strategy import _f, _cfg, count_new_positions_this_week


def count_breakout_new_this_week(history_df: pd.DataFrame, as_of: Optional[datetime] = None) -> int:
    if history_df is None or history_df.empty:
        return 0
    as_of = as_of or datetime.now()
    cutoff = as_of - timedelta(days=7)
    h = history_df.copy()
    h['date'] = pd.to_datetime(h['date'], errors='coerce')
    mask = (h['date'] >= cutoff) & (
        h['action'].astype(str).str.contains('BREAKOUT NEW', na=False)
        | h['reason'].astype(str).str.contains('BREAKOUT FAST-TRACK', na=False)
    )
    return int(mask.sum())


def soften_rank_sells(allocation_df: pd.DataFrame, cfg=None) -> int:
    """
    Path 2: rank/score SELL -> CONSIDER (25%) when P&L in soft band.
    VMQ / emergency exits unchanged. Skipped when rank-SELL disabled for stack.
    """
    if allocation_df is None or allocation_df.empty:
        return 0
    if not bool(_cfg(cfg, 'PATH2_BALANCED_ENABLED', True)):
        return 0
    if bool(_cfg(cfg, 'ORACLE_STACK_ALIGN', True)) and bool(
        _cfg(cfg, 'ORACLE_DISABLE_RANK_SELL_ALL', True)
    ):
        return 0

    soft_min = _f(_cfg(cfg, 'PATH2_SOFT_SELL_PNL_MIN', -0.03))
    soft_max = _f(_cfg(cfg, 'PATH2_SOFT_SELL_PNL_MAX', 0.03))
    count = 0

    for idx, row in allocation_df[allocation_df.get('is_current_holding') == True].iterrows():
        act = str(allocation_df.at[idx, 'action_recommendation']).upper().strip()
        if act != 'SELL':
            continue
        er = str(allocation_df.at[idx, 'exit_reason']).upper()
        if any(k in er for k in (
            'VMQ HARD', 'VMQ SWING', 'VMQ DAY', 'EMERGENCY', 'THESIS BREAK',
            'STOP LOSS', 'CIRCUIT BREAKER', 'CRISIS', 'HARD STOP', 'SWING STOP',
        )):
            continue
        pnl = row.get('current_profit_pct')
        try:
            pnl_f = float(pnl) if pnl is not None and pd.notna(pnl) else None
        except (TypeError, ValueError):
            pnl_f = None
        if pnl_f is None:
            continue
        if soft_min <= pnl_f <= soft_max:
            allocation_df.at[idx, 'action_recommendation'] = 'CONSIDER SELLING'
            allocation_df.at[idx, 'profit_booking_pct'] = float(
                _cfg(cfg, 'PATH2_CONSIDER_TRIM_PCT', 0.25)
            )
            allocation_df.at[idx, 'exit_reason'] = (
                f"Path2 soft trim: P&L {pnl_f*100:+.1f}% in [{soft_min*100:.0f},{soft_max*100:.0f}]% band"
            )
            count += 1
    return count


def apply_fast_track_entry(
    allocation_df: pd.DataFrame,
    results_df: pd.DataFrame,
    history_df: pd.DataFrame,
    held_symbols: Set[str],
    total_target_portfolio: float,
    cfg=None,
) -> Dict[str, Any]:
    """
    Promote top Breakout Radar name to BREAKOUT NEW (half size) if slot open.
    Bypasses value-trap for B-IGNITE / A+-READY only.
    """
    stats = {'promoted': False, 'symbol': '', 'reason': ''}
    if not bool(_cfg(cfg, 'PATH2_BALANCED_ENABLED', True)):
        return stats
    if not bool(_cfg(cfg, 'BREAKOUT_FAST_TRACK_ENABLED', True)):
        return stats
    try:
        from src.flow_quality_oracle import oracle_pause_new_entries
        _paused, _why = oracle_pause_new_entries(cfg)
        if _paused:
            stats['reason'] = f'oracle pause: {_why}'
            return stats
    except Exception:
        pass

    max_breakout = int(_cfg(cfg, 'BREAKOUT_MAX_NEW_PER_WEEK', 1))
    if count_breakout_new_this_week(history_df) >= max_breakout:
        stats['reason'] = f'breakout cap {max_breakout}/week'
        return stats

    radar_df = scan_dataframe(results_df, held_symbols=held_symbols, cfg=cfg, max_rows=15)
    if radar_df.empty:
        stats['reason'] = 'no radar candidates'
        return stats

    cand = pick_fast_track_symbol(radar_df, cfg)
    if not cand:
        stats['reason'] = 'no B-IGNITE or A+-READY'
        return stats

    sym = str(cand['symbol']).upper()
    tier = str(cand.get('breakout_tier', ''))
    if tier not in (TIER_IGNITE, TIER_READY):
        stats['reason'] = f'{sym} tier {tier} not fast-track eligible'
        return stats

    # Oracle stack: breakout fast-track must pass fq watchlist + turbo gate
    if bool(_cfg(cfg, 'ORACLE_STACK_ALIGN', True)):
        _row_match = results_df[
            results_df['symbol'].astype(str).str.upper() == sym
        ] if results_df is not None and not results_df.empty else pd.DataFrame()
        if _row_match.empty:
            stats['reason'] = f'{sym} not in results_df'
            return stats
        row_dict = _row_match.iloc[0].to_dict()
        if not bool(row_dict.get('on_oracle_watchlist', False)):
            stats['reason'] = f'{sym} not on oracle watchlist'
            return stats
        from src.turbo_entry import evaluate_turbo_entry_gate
        turbo_result = evaluate_turbo_entry_gate(
            row_dict, cfg, new_this_week=count_new_positions_this_week(history_df),
        )
        if not turbo_result.allowed:
            stats['reason'] = f'{sym} turbo block: {"; ".join(turbo_result.reasons)}'
            return stats

    rsi = _f(cand.get('real_rsi'), 50)
    if rsi > _f(_cfg(cfg, 'TURBO_ENTRY_RSI_MAX', 75.0)):
        stats['reason'] = f'{sym} RSI {rsi:.0f} extended'
        return stats

    # Find or create allocation row
    if 'symbol' not in allocation_df.columns:
        stats['reason'] = 'no allocation df'
        return stats

    sym_col = allocation_df['symbol'].astype(str).str.upper()
    idx_list = allocation_df.index[sym_col == sym].tolist()

    half_mult = _f(_cfg(cfg, 'BREAKOUT_FAST_TRACK_SIZE_MULT', 0.5))
    max_pct = _f(_cfg(cfg, 'MAX_ALLOCATION_PCT', 0.07))
    target_amt = float(total_target_portfolio or 0) * max_pct * half_mult
    price = _f(cand.get('current_price'), 0)
    if price <= 0:
        stats['reason'] = f'{sym} invalid price'
        return stats
    qty = max(1, int(target_amt / price))
    invest = round(qty * price, 2)

    reason = (
        f"BREAKOUT FAST-TRACK ({tier}): {cand.get('breakout_radar_reason', '')} "
        f"[half size {half_mult*100:.0f}%]"
    )

    if idx_list:
        idx = idx_list[0]
    else:
        idx = len(allocation_df)
        allocation_df.loc[idx, 'symbol'] = sym

    # Merge score/sector fields from results_df so Excel rotation sort does not break
    if results_df is not None and not results_df.empty and 'symbol' in results_df.columns:
        _match = results_df[results_df['symbol'].astype(str).str.upper() == sym]
        if not _match.empty:
            _src = _match.iloc[0]
            for _col in (
                'company_name', 'sector', 'final_blended_score', 'overall_score',
                'overall_score_with_value', 'hybrid_overall_score_v2',
                'hybrid_momentum_technical', 'hybrid_multi_timeframe',
                'hybrid_fundamental_quality', 'risk_category', 'final_recommendation',
                'enhanced_rsi_14', 'real_rsi', 'volatility', 'undervaluation_score',
            ):
                if _col in _src.index and _col in allocation_df.columns:
                    allocation_df.at[idx, _col] = _src[_col]
                elif _col in _src.index:
                    allocation_df[_col] = _src[_col]
                    allocation_df.at[idx, _col] = _src[_col]
            _bl = _f(_src.get('final_blended_score', _src.get('overall_score_with_value', 0)))
            if 'overall_score' in allocation_df.columns:
                allocation_df.at[idx, 'overall_score'] = _bl
            if 'final_blended_score' in allocation_df.columns:
                allocation_df.at[idx, 'final_blended_score'] = _bl

    allocation_df.at[idx, 'symbol'] = sym
    allocation_df.at[idx, 'action_recommendation'] = 'BREAKOUT NEW'
    allocation_df.at[idx, 'action_type'] = 'BREAKOUT NEW'
    allocation_df.at[idx, 'is_current_holding'] = False
    allocation_df.at[idx, 'investment_amount'] = invest
    allocation_df.at[idx, 'suggested_quantity'] = qty
    allocation_df.at[idx, 'current_price'] = price
    allocation_df.at[idx, 'exit_reason'] = reason
    allocation_df.at[idx, 'vmq_status'] = 'BREAKOUT'
    allocation_df.at[idx, 'vmq_reason'] = reason
    allocation_df.at[idx, 'breakout_tier'] = tier
    if 'INVEST ₹' in allocation_df.columns:
        allocation_df.at[idx, 'INVEST ₹'] = invest
    if 'BUY QTY' in allocation_df.columns:
        allocation_df.at[idx, 'BUY QTY'] = qty

    stats['promoted'] = True
    stats['symbol'] = sym
    stats['tier'] = tier
    stats['invest'] = invest
    stats['reason'] = reason
    return stats
