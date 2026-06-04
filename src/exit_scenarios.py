"""Exit and monitor scenarios for action-plan sell / hold sections."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pandas as pd

from src.new_entry_scenarios import _first_float, _round_inr, build_entry_scenarios


def _urgency_for_section(section_id: str, action: str, reason: str) -> str:
    act = str(action or '').upper()
    rsn = str(reason or '').upper()
    if section_id in ('sell', 'swap_sell') or 'HARD STOP' in rsn or 'EXIT NOW' in act:
        return 'hard'
    if section_id in ('consider',):
        return 'soft'
    if section_id in ('book', 'reduce', 'exit'):
        return 'partial'
    return 'soft'


def _partial_range(row: Dict[str, Any], action: str) -> tuple:
    act = str(action or '')
    m = re.search(r'(\d+)-(\d+)%', act)
    if m:
        return int(m.group(1)), int(m.group(2))
    bk = _first_float(row, 'BOOK %', 'book_pct')
    if bk is not None and 0 < bk <= 1:
        pct = int(bk * 100)
        return max(5, pct - 5), pct
    if 'REDUCE' in act.upper():
        return 25, 35
    return 50, 60


def build_exit_scenarios(row: Dict[str, Any], section_id: str, cfg=None) -> Dict[str, Any]:
    """Build E1/E2/E3 exit execution levels from an allocation row."""
    action = str(row.get('ACTION', ''))
    reason = str(row.get('REASON', row.get('vmq_reason', row.get('exit_reason', ''))))
    price = _first_float(row, 'PRICE', 'current_price', 'price') or 0.0
    qty = int(_first_float(row, 'QTY', 'MY QTY', 'quantity', 'buy_qty') or 0)
    pnl = _first_float(row, 'P&L %', 'pnl_pct')

    base = build_entry_scenarios(row, cfg)
    support = base.get('support') or (price * 0.93 if price > 0 else 0.0)
    resistance = _round_inr(price * 1.02) if price > 0 else 0.0
    resistance_hi = _round_inr(price * 1.04) if price > 0 else 0.0

    lo, hi = _partial_range(row, action)
    urgency = _urgency_for_section(section_id, action, reason)

    return {
        'symbol': str(row.get('symbol', row.get('SYMBOL', ''))).upper(),
        'section_id': section_id,
        'price': _round_inr(price),
        'qty': qty,
        'pnl_pct': pnl,
        'support': support,
        'resistance': resistance,
        'resistance_hi': resistance_hi,
        'urgency': urgency,
        'partial_lo': lo,
        'partial_hi': hi,
        'action': action,
        'reason': reason,
    }


def format_exit_scenario_lines(sc: Dict[str, Any]) -> List[str]:
    """Human-readable E1/E2/E3 block for terminal / dashboard."""
    if sc.get('price', 0) <= 0:
        return [f"  {sc.get('symbol', '?')}: exit scenarios unavailable (no price)"]

    sym = sc.get('symbol', '?')
    lines: List[str] = [f"  EXIT SCENARIOS — {sym} (pick ONE execution path):"]
    urgency = sc.get('urgency', 'soft')

    if urgency == 'hard':
        lines.extend([
            '  E1 OPEN: execute at market open — hard exit / stop breached',
            (
                f"  E2 LIMIT: optional limit near ₹{sc['price']:,.2f} "
                f"(same session only if illiquid)"
            ),
            '  E3 SKIP: do not defer — exit required this week',
        ])
        lines.append(
            f"  Ideal: exit {sym} at open (E1) unless liquidity needs E2 limit"
        )
    elif urgency == 'partial':
        qty = sc.get('qty') or 0
        lo, hi = sc.get('partial_lo', 50), sc.get('partial_hi', 60)
        q_lo = max(1, int(qty * lo / 100)) if qty else 0
        q_hi = max(1, int(qty * hi / 100)) if qty else 0
        lines.extend([
            (
                f"  E1 SCALE: sell {lo}–{hi}% at open "
                f"({q_lo}–{q_hi} sh if full size {qty})"
            ),
            (
                f"  E2 BOUNCE: limit into ₹{sc['resistance']:,.2f}–"
                f"₹{sc['resistance_hi']:,.2f} strength"
            ),
            (
                f"  E3 DEFER: skip trim if close holds above ₹{sc['support']:,.2f} "
                f"— thesis still OK"
            ),
        ])
        lines.append(
            f"  Ideal: partial exit on E1 or E2 · defer only if E3 support holds"
        )
    else:
        lines.extend([
            '  E1 OPEN: sell at open if gap down or weak pre-market',
            (
                f"  E2 BOUNCE: limit sell into ₹{sc['resistance']:,.2f}–"
                f"₹{sc['resistance_hi']:,.2f} bounce"
            ),
            (
                f"  E3 DEFER: skip trim if close holds above ₹{sc['support']:,.2f} "
                f"— review next run"
            ),
        ])
        lines.append(
            f"  Ideal: soft trim on E2 if extended · E1 if breakdown · E3 if support holds"
        )
    return lines


def build_hold_monitor(row: Dict[str, Any], cfg=None) -> Dict[str, Any]:
    base = build_entry_scenarios(row, cfg)
    return {
        'symbol': base.get('symbol', '?'),
        'support': base.get('support', 0),
        'price': base.get('price', 0),
        'breakdown': base.get('breakdown', 0),
    }


def format_hold_monitor_lines(sc: Dict[str, Any], lvm_mode: bool = False) -> List[str]:
    sym = sc.get('symbol', '?')
    price = sc.get('price', 0)
    if price <= 0:
        return [f"  {sym}: monitor levels unavailable (no price)"]
    if lvm_mode:
        stop = round(price * 0.90, 2)
        from datetime import datetime, timedelta
        today = datetime.now()
        next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        while next_month.weekday() >= 5:
            next_month += timedelta(days=1)
        rebal_str = next_month.strftime('%a %d %b')
        return [
            f"  M1 Hold: LVM monthly hold — no action unless -10% stop triggers",
            f"  M2 Review: GTT stop ₹{stop:,.2f} (-10%) — only mid-month exit",
            f"  M3 Alert: Rebalance {rebal_str} — rotate if dropped from Top 10",
        ]
    return [
        f"  MONITOR — {sym} (no trade this week unless level breaks):",
        f"  M1 HOLD: close above ₹{sc['support']:,.2f} — keep position",
        f"  M2 REVIEW: close below ₹{sc['support']:,.2f} — revisit next run",
        (
            f"  M3 ALERT: close below ₹{sc['breakdown']:,.2f} — "
            f"thesis broken; expect SELL path"
        ),
    ]
