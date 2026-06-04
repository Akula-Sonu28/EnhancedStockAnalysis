"""Unified action-plan scenarios — entry, exit, and monitor — for all priority sections."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

import pandas as pd

from src.exit_scenarios import (
    build_exit_scenarios,
    build_hold_monitor,
    format_exit_scenario_lines,
    format_hold_monitor_lines,
)
from src.new_entry_scenarios import (
    build_entry_scenarios,
    format_entry_scenario_lines,
    format_swap_target_entry_ref,
)

ENTRY_MODES = {
    'buynew': 'NEW',
    'increase': 'ADD',
    'watch': 'WATCH',
    'radar': 'WATCH',
    'swap_buy': 'NEW',
}

EXIT_SECTIONS = frozenset({'exit', 'sell', 'consider', 'book', 'reduce', 'swap_sell'})


def _row_dict(row: Any) -> Dict[str, Any]:
    if hasattr(row, 'to_dict'):
        return row.to_dict()
    return dict(row)


def _lookup_allocation_row(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    sym = str(symbol or '').strip().upper()
    if not sym or df is None or getattr(df, 'empty', True) or 'symbol' not in df.columns:
        return None
    mask = df['symbol'].astype(str).str.strip().str.upper() == sym
    if not mask.any():
        return None
    return df.loc[mask].iloc[0].to_dict()


def _normalize_radar_row(row: Dict[str, Any], allocation_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    out = dict(row)
    sym = str(out.get('symbol', out.get('stock', ''))).upper()
    if allocation_df is not None:
        alloc = _lookup_allocation_row(allocation_df, sym)
        if alloc:
            out = {**alloc, **{k: v for k, v in out.items() if v not in (None, '', 'nan')}}
    if not out.get('PRICE') and out.get('current_price'):
        out['PRICE'] = out['current_price']
    if not out.get('symbol') and sym:
        out['symbol'] = sym
    return out


def scenario_payload_for_section(
    row: Dict[str, Any],
    section_id: str,
    cfg=None,
    *,
    new_buy_syms: Optional[Set[str]] = None,
    swap_target: str = '',
    allocation_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Build dashboard payloads: entryScenarios, exitScenarios, entryScenariosRef."""
    out: Dict[str, Any] = {}
    rd = _row_dict(row)
    syms = new_buy_syms or set()

    if section_id == 'swap':
        ex = build_exit_scenarios(rd, 'swap_sell', cfg)
        out['exitScenarios'] = {
            'symbol': ex['symbol'],
            'lines': format_exit_scenario_lines(ex),
            'structured': ex,
        }
        tgt = str(swap_target or rd.get('rotation_target', '')).strip().upper()
        if tgt:
            ref = format_swap_target_entry_ref(tgt, syms)
            if ref:
                out['entryScenariosRef'] = ref.strip()
            else:
                tgt_row = _lookup_allocation_row(allocation_df, tgt) if allocation_df is not None else None
                if tgt_row:
                    sc = build_entry_scenarios(tgt_row, cfg)
                    out['entryScenarios'] = {
                        'symbol': sc['symbol'],
                        'lines': format_entry_scenario_lines(sc, mode='NEW'),
                        'structured': sc,
                    }
        return out

    if section_id in EXIT_SECTIONS:
        ex = build_exit_scenarios(rd, section_id, cfg)
        out['exitScenarios'] = {
            'symbol': ex['symbol'],
            'lines': format_exit_scenario_lines(ex),
            'structured': ex,
        }
        return out

    if section_id in ENTRY_MODES:
        if section_id == 'swap_buy':
            tgt = str(swap_target or rd.get('symbol', '')).upper()
            ref = format_swap_target_entry_ref(tgt, syms)
            if ref:
                out['entryScenariosRef'] = ref.strip()
                return out
        mode = ENTRY_MODES[section_id]
        if section_id == 'radar':
            rd = _normalize_radar_row(rd, allocation_df)
        sc = build_entry_scenarios(rd, cfg)
        out['entryScenarios'] = {
            'symbol': sc['symbol'],
            'lines': format_entry_scenario_lines(sc, mode=mode),
            'structured': sc,
        }
        return out

    if section_id == 'hold':
        _lvm_mode = False
        try:
            from config import get_config as _gc_lvm
            from src.lowvol_momentum import is_lvm_strategy
            _lvm_mode = is_lvm_strategy(_gc_lvm())
        except Exception:
            pass
        mon = build_hold_monitor(rd, cfg)
        out['monitorScenarios'] = {
            'symbol': mon['symbol'],
            'lines': format_hold_monitor_lines(mon, lvm_mode=_lvm_mode),
            'structured': mon,
        }
    return out


def print_action_scenario_block(
    row: Any,
    section_id: str,
    cfg=None,
    *,
    new_buy_syms: Optional[Set[str]] = None,
    swap_target: str = '',
    allocation_df: Optional[pd.DataFrame] = None,
) -> None:
    """Print scenario lines for one action-plan row (terminal)."""
    payload = scenario_payload_for_section(
        _row_dict(row),
        section_id,
        cfg,
        new_buy_syms=new_buy_syms,
        swap_target=swap_target,
        allocation_df=allocation_df,
    )
    for key in ('exitScenarios', 'entryScenarios', 'monitorScenarios'):
        block = payload.get(key)
        if block and block.get('lines'):
            for line in block['lines']:
                print(line)
    if payload.get('entryScenariosRef'):
        print(payload['entryScenariosRef'])
