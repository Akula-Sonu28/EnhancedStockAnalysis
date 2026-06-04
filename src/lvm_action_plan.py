"""Shared LVM action-plan helpers (terminal + dashboard parity)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from src.lowvol_momentum import (
    compute_active_lvm_score,
    is_lvm_momentum_degraded,
    lvm_eligible_symbols,
    lvm_fund_label,
    lvm_fund_n,
    lvm_fund_symbols,
    lvm_top_label,
    lvm_top_n,
)

LVM_DEGRADED_MSG = (
    'Missing momentum columns (price_change_1y, legacy_sma_50). '
    'Re-run analysis to fix. Do NOT trade based on this report\'s LVM picks.'
)


def format_allocation_pnl(row: Any, default: str = '') -> str:
    """Format P&L for action-plan lines (avoid 'nan P&L=0.0%').
    
    Returns blank when:
    - P&L is NaN/None
    - P&L is near 0 AND avg_cost is missing/zero (indicates no cost basis data)
    
    Returns +0.0% only when avg_cost exists and P&L is genuinely near breakeven.
    """
    if row is None:
        return default
    d = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
    for col in ('P&L %', 'pnl_pct', 'current_profit_pct', 'P&L'):
        raw = d.get(col)
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            continue
        try:
            v = float(raw)
        except (TypeError, ValueError):
            continue
        if col == 'current_profit_pct' and abs(v) <= 1.5:
            v *= 100.0
        # Distinguish between "no P&L data" (show blank) vs "actual 0% P&L" (show +0.0%)
        # If P&L is near zero AND avg_cost is missing/zero, treat as missing data
        if abs(v) < 0.05:
            avg_cost = d.get('avg_cost', d.get('Avg. cost', 0))
            try:
                avg_cost = float(avg_cost) if avg_cost is not None and not pd.isna(avg_cost) else 0
            except (TypeError, ValueError):
                avg_cost = 0
            if avg_cost <= 0:
                return default
        return f'{v:+.1f}%'
    return default


def sanitize_reason_fragment(reason: Any) -> str:
    """Strip NaN/empty REASON before concatenating into action-plan text."""
    if reason is None or (isinstance(reason, float) and pd.isna(reason)):
        return ''
    s = str(reason).strip()
    if s.lower() in ('', 'nan', 'none'):
        return ''
    return s


def lvm_rotation_reason(label: str, prior_reason: Any = '') -> str:
    """Standard LVM rotation REASON without trailing '| nan'."""
    prior = sanitize_reason_fragment(prior_reason)
    base = f'Not in {label} — rotate out'
    return f'{base} | {prior}' if prior else base


def actionable_sell_mask(actions: pd.Series) -> pd.Series:
    """SELL rows for tax/harvest (excludes CONSIDER SELLING)."""
    act = actions.astype(str).str.upper()
    return act.str.contains('SELL', na=False) & ~act.str.contains('CONSIDER', na=False)


def sell_proceeds_inr(
    sell_df: pd.DataFrame,
    book_col: str = 'BOOK ₹',
    value_col: str = 'MY VALUE ₹',
) -> pd.Series:
    """Proceeds per sell row: BOOK ₹ if set, else MY VALUE ₹ (full exit)."""
    bk = pd.to_numeric(sell_df.get(book_col), errors='coerce').fillna(0)
    val = pd.to_numeric(sell_df.get(value_col), errors='coerce').fillna(0)
    return bk.where(bk > 0, val)


def compute_tax_harvest_totals(
    sell_df: pd.DataFrame,
    book_col: str = 'BOOK ₹',
    value_col: str = 'MY VALUE ₹',
    pnl_col: str = 'P&L %',
    tax_col: str = 'TAX ₹',
) -> Optional[Dict[str, float]]:
    """Realised P&L on actionable sells from proceeds and P&L %."""
    if sell_df is None or sell_df.empty or pnl_col not in sell_df.columns:
        return None
    bk = sell_proceeds_inr(sell_df, book_col=book_col, value_col=value_col)
    if float(bk.sum()) <= 0:
        return None
    pnl_pct = pd.to_numeric(sell_df.get(pnl_col), errors='coerce').fillna(0)
    unit = pnl_pct / (100.0 if pnl_pct.abs().max() > 1 else 1.0)
    cost = bk / (1.0 + unit).replace(0, 1.0)
    pnl_inr = bk - cost
    losses = float(pnl_inr[pnl_inr < 0].sum())
    gains = float(pnl_inr[pnl_inr > 0].sum())
    tax = float(pd.to_numeric(sell_df.get(tax_col), errors='coerce').fillna(0).sum())
    return {
        'losses': losses,
        'gains': gains,
        'net_pnl': gains + losses,
        'tax': tax,
    }


def apply_lvm_rotation_display_fields(
    allocation_df: pd.DataFrame,
    row_index: Any,
    row: Any,
    lvm_label: str,
    value_col: str = 'MY VALUE ₹',
) -> None:
    """In-memory LVM rotation: ACTION, REASON, SELL WHY, BOOK for tax block."""
    allocation_df.at[row_index, 'ACTION'] = 'SELL (LVM ROTATION)'
    prior = row.get('REASON', '') if hasattr(row, 'get') else ''
    allocation_df.at[row_index, 'REASON'] = lvm_rotation_reason(lvm_label, prior)
    if 'SELL WHY' in allocation_df.columns:
        allocation_df.at[row_index, 'SELL WHY'] = 'LVM_ROTATION'
    cur_val = float(pd.to_numeric(row.get(value_col, 0), errors='coerce') or 0)
    if cur_val > 0 and 'BOOK ₹' in allocation_df.columns:
        allocation_df.at[row_index, 'BOOK ₹'] = cur_val
    if 'BOOK %' in allocation_df.columns:
        allocation_df.at[row_index, 'BOOK %'] = 1.0


def fallback_holding_row_extras(
    holding: Any,
    action: str,
    current_value: float,
    quantity: float,
    avg_cost: float,
) -> Dict[str, Any]:
    """Tax/booking fields for emergency allocation fallback rows."""
    extras: Dict[str, Any] = {
        'profit_booking_pct': None,
        'profit_booking_amount': 0.0,
        'tax_type': None,
        'estimated_tax': 0.0,
        'post_tax_proceeds': 0.0,
        'exit_reason': '',
        'action_reason': '',
    }
    act_u = str(action or '').upper()
    cv = float(current_value or 0)
    q = float(quantity or 0)
    ac = float(avg_cost or 0)
    invested = ac * q if ac > 0 and q > 0 else cv
    if 'SELL' in act_u and cv > 0:
        extras['profit_booking_pct'] = 1.0
        extras['profit_booking_amount'] = cv
        gain = cv - invested if invested > 0 else 0.0
        if gain > 0:
            extras['tax_type'] = 'STCG (est.)'
            extras['estimated_tax'] = round(gain * 0.20, 0)
            extras['post_tax_proceeds'] = cv - extras['estimated_tax']
        else:
            extras['tax_type'] = 'NO_TAX (LOSS)'
            extras['post_tax_proceeds'] = cv
    return extras


def resolve_lvm_universe(
    complete_df: pd.DataFrame,
    cfg=None,
    as_of: Optional[date] = None,
) -> Tuple[Set[str], Set[str], pd.DataFrame, Optional[str]]:
    """Return (screen_syms, fund_syms, scored_df, degraded_reason or None)."""
    if complete_df is None or complete_df.empty:
        return set(), set(), complete_df, LVM_DEGRADED_MSG
    if is_lvm_momentum_degraded(complete_df):
        work = complete_df.copy()
        work.attrs['_lvm_data_degraded'] = True
        return set(), set(), work, LVM_DEGRADED_MSG
    work = compute_active_lvm_score(complete_df.copy(), cfg, as_of=as_of or date.today())
    if work.attrs.get('_lvm_data_degraded') or is_lvm_momentum_degraded(complete_df):
        return set(), set(), work, LVM_DEGRADED_MSG
    return (
        lvm_eligible_symbols(work, cfg),
        lvm_fund_symbols(work, cfg),
        work,
        None,
    )


def _price_and_value(
    sym: str,
    allocation_df: Optional[pd.DataFrame],
    complete_df: Optional[pd.DataFrame],
    val_col: str = 'MY VALUE ₹',
) -> Tuple[float, float]:
    sym_u = sym.upper()
    cur_val = 0.0
    price = 0.0
    if allocation_df is not None and not allocation_df.empty and 'symbol' in allocation_df.columns:
        row = allocation_df[allocation_df['symbol'].astype(str).str.upper() == sym_u]
        if not row.empty:
            r = row.iloc[0]
            price = float(pd.to_numeric(
                r.get('PRICE', r.get('current_price', 0)), errors='coerce',
            ) or 0)
            cur_val = float(pd.to_numeric(
                r.get(val_col, r.get('current_value', 0)), errors='coerce',
            ) or 0)
    if price <= 0 and complete_df is not None and not complete_df.empty:
        crow = complete_df[complete_df['symbol'].astype(str).str.upper() == sym_u]
        if not crow.empty:
            cr = crow.iloc[0]
            price = float(pd.to_numeric(
                cr.get('current_price', cr.get('PRICE', 0)), errors='coerce',
            ) or 0)
    return price, cur_val


def compute_lvm_p5_actions(
    fund_syms: Set[str],
    total_available: float,
    allocation_df: Optional[pd.DataFrame] = None,
    complete_df: Optional[pd.DataFrame] = None,
    min_invest: float = 5000.0,
    val_col: str = 'MY VALUE ₹',
    price_by_sym: Optional[Dict[str, float]] = None,
) -> Tuple[List[Dict[str, Any]], float, float, Set[str], Set[str]]:
    """
    Equal-weight rebalance plan for LVM_FUND_N names.

    Returns (actions, target_per_stock, held_funded_value, held_syms, new_syms).
    """
    if not fund_syms:
        return [], 0.0, 0.0, set(), set()

    held_syms: Set[str] = set()
    held_value = 0.0
    if allocation_df is not None and not allocation_df.empty:
        act_col = 'ACTION' if 'ACTION' in allocation_df.columns else 'action_recommendation'
        for _, r in allocation_df.iterrows():
            sym = str(r.get('symbol', '')).upper()
            if sym not in fund_syms:
                continue
            val = float(pd.to_numeric(r.get(val_col, r.get('current_value', 0)), errors='coerce') or 0)
            act = str(r.get(act_col, '')).upper()
            if val > 0 and ('HOLD' in act or 'KEEP' in act or 'INCREASE' in act or 'LVM' in act):
                held_syms.add(sym)
                held_value += val

    n = max(1, len(fund_syms))
    target_per = (held_value + float(total_available or 0)) / n
    new_syms = fund_syms - held_syms
    actions: List[Dict[str, Any]] = []

    extras = {str(k).upper(): float(v) for k, v in (price_by_sym or {}).items() if v}

    for sym in sorted(fund_syms):
        price, cur_val = _price_and_value(sym, allocation_df, complete_df, val_col=val_col)
        if price <= 0:
            price = extras.get(sym.upper(), 0.0)
        if price <= 0:
            continue
        deficit = target_per - cur_val
        if cur_val <= 0:
            label = 'BUY NEW'
            buy_amt = target_per
        elif deficit > min_invest:
            label = 'INCREASE'
            buy_amt = deficit
        else:
            label = 'AT WEIGHT'
            buy_amt = 0.0
        shares = int(buy_amt / price) if buy_amt > 0 else 0
        invest = shares * price
        actions.append({
            'sym': sym,
            'action': label,
            'price': price,
            'shares': shares,
            'invest': invest,
            'cur_val': cur_val,
            'target': target_per,
        })

    return actions, target_per, held_value, held_syms, new_syms


def lvm_context_labels(cfg=None) -> Dict[str, str]:
    return {
        'screen': lvm_top_label(cfg),
        'fund': lvm_fund_label(cfg),
        'screen_n': str(lvm_top_n(cfg)),
        'fund_n': str(lvm_fund_n(cfg)),
    }


def lvm_p5_capital_and_buys(
    totals: dict,
    portfolio_amount: float,
    fund_syms: Set[str],
    allocation_df: pd.DataFrame,
    complete_df: Optional[pd.DataFrame] = None,
    *,
    val_col: str = 'MY VALUE ₹',
    min_invest: float = 5000.0,
    price_by_sym: Optional[Dict[str, float]] = None,
) -> Tuple[float, float, float]:
    """Terminal Priority 5 capital line: sell proceeds, buy total, total available."""
    sell_proceeds = (
        float(totals.get('sellTotal', 0) or 0)
        + float(totals.get('exitTotal', 0) or 0)
        + float(totals.get('lvmRotTotal', 0) or 0)
    )
    total_available = sell_proceeds + float(portfolio_amount or 0)
    actions, _, _, _, _ = compute_lvm_p5_actions(
        fund_syms,
        total_available,
        allocation_df,
        complete_df,
        min_invest=min_invest,
        val_col=val_col,
        price_by_sym=price_by_sym,
    )
    buy_total = sum(
        float(a.get('invest', 0) or 0)
        for a in actions
        if a.get('action') in ('BUY NEW', 'INCREASE')
    )
    return sell_proceeds, buy_total, total_available


def portfolio_value_for_rsi_sizing(
    allocation_df: Optional[pd.DataFrame] = None,
    *,
    val_col: str = 'MY VALUE ₹',
    fallback_inr: float = 1_150_000.0,
    min_trade_inr: float = 5000.0,
) -> float:
    """Per-trade RSI pullback budget (~1% of portfolio mark-to-market)."""
    pv = 0.0
    if allocation_df is not None and not allocation_df.empty:
        for col in (val_col, 'current_value', 'MY VALUE ₹'):
            if col in allocation_df.columns:
                pv = float(pd.to_numeric(allocation_df[col], errors='coerce').fillna(0).sum())
                if pv > 0:
                    break
    if pv <= 0:
        pv = float(fallback_inr)
    return max(min_trade_inr, pv * 0.01)
