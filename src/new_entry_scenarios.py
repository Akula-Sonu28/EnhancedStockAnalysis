"""Monday-style entry scenarios for NEW POSITION / swap targets in the action plan."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from src.turbo_entry import get_chase_5d_pct, get_rsi, sync_price_change_aliases


def _first_float(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        v = row.get(key)
        if v is not None and pd.notna(v):
            try:
                f = float(v)
                if f > 0 or key.lower().endswith('pct') or 'change' in key.lower():
                    return f
            except (TypeError, ValueError):
                pass
    return None


def _round_inr(x: float) -> float:
    return round(float(x), 2)


def build_entry_scenarios(row: Dict[str, Any], cfg=None) -> Dict[str, Any]:
    """Build S1/S2/S3 levels and share counts from an allocation or analysis row."""
    row = sync_price_change_aliases(dict(row))
    price = _first_float(row, 'PRICE', 'current_price', 'price') or 0.0
    invest = _first_float(row, 'INVEST ₹', 'investment_amount', 'invest_amount') or 0.0
    full_qty = int(_first_float(row, 'BUY QTY', 'suggested_quantity', 'buy_qty') or 0)
    if full_qty <= 0 and price > 0 and invest > 0:
        full_qty = max(1, int(invest / price))
    half_qty = max(1, full_qty // 2) if full_qty > 0 else 0

    support = _first_float(row, 'SUPPORT', 'support_level')
    if support is None or support <= 0 or support >= price * 0.985:
        support = price * 0.93 if price > 0 else 0.0
    support = _round_inr(support)

    hold_floor = _round_inr(price * 0.99) if price > 0 else 0.0
    pullback_lo = _round_inr(max(support, price * 0.93) if price > 0 else support)
    pullback_hi = _round_inr(min(price * 0.97, price * 0.995) if price > 0 else 0.0)
    if pullback_hi < pullback_lo and price > 0:
        pullback_hi = _round_inr(price * 0.97)
    breakdown = _round_inr(support * 0.98 if support > 0 else price * 0.91)

    rsi = get_rsi(row)
    chg_5d = get_chase_5d_pct(row)
    chg_5d = float(chg_5d) if chg_5d is not None else 0.0
    chase_warning = rsi > 70 or chg_5d > 10.0

    swing_pct = float(getattr(cfg, 'VMQ_SWING_STOP_PCT', -5.0) if cfg else -5.0)
    hard_pct = float(getattr(cfg, 'VMQ_HARD_STOP_PCT', -8.0) if cfg else -8.0)

    return {
        'symbol': str(row.get('symbol', row.get('SYMBOL', ''))).upper(),
        'price': _round_inr(price),
        'invest': _round_inr(invest),
        'full_qty': full_qty,
        'half_qty': half_qty,
        'support': support,
        'hold_floor': hold_floor,
        'pullback_lo': pullback_lo,
        'pullback_hi': pullback_hi,
        'breakdown': breakdown,
        'rsi': rsi,
        'chg_5d': chg_5d,
        'chase_warning': chase_warning,
        'swing_pct': swing_pct,
        'hard_pct': hard_pct,
    }


def format_entry_scenario_lines(sc: Dict[str, Any], mode: str = 'NEW') -> List[str]:
    """Human-readable scenario block for terminal action plan."""
    if sc.get('price', 0) <= 0:
        return [f"  {sc.get('symbol', '?')}: entry scenarios unavailable (no price)"]

    sym = sc.get('symbol', '?')
    mode = (mode or 'NEW').upper()
    headers = {
        'NEW': f"  ENTRY SCENARIOS — {sym} (rank size is ceiling; pick ONE scenario):",
        'ADD': f"  ADD SCENARIOS — {sym} (add-on size is ceiling; pick ONE scenario):",
        'WATCH': f"  WATCH SCENARIOS — {sym} (gate blocked — plan entry if trigger clears):",
    }
    ideals = {
        'NEW': f"  Ideal: sell source on schedule · buy {sym} on S2 (or half on S1) · no buy on S3",
        'ADD': f"  Ideal: add {sym} on S2 pullback · half on S1 only if trend intact · skip on S3",
        'WATCH': f"  Ideal: monitor until gate clears · then buy on S2 · no full chase on S1",
    }
    lines: List[str] = [headers.get(mode, headers['NEW'])]
    if sc.get('chase_warning'):
        lines.append(
            f"  ⚠ Extended: RSI {sc['rsi']:.0f}, 5d {sc['chg_5d']:+.1f}% — avoid full market chase"
        )
    half_val = sc['half_qty'] * sc['price']
    full_at_pb = sc['full_qty'] * sc['pullback_hi'] if sc['full_qty'] else 0
    lines.extend([
        (
            f"  S1 HOLD: open holds above ₹{sc['hold_floor']:,.2f} → "
            f"buy {sc['half_qty']} sh (~₹{half_val:,.0f}) half-size only"
        ),
        (
            f"  S2 PULLBACK: ₹{sc['pullback_lo']:,.2f}–{sc['pullback_hi']:,.2f} "
            f"(retest) → buy {sc['full_qty']} sh limit (~₹{full_at_pb:,.0f} at top of band)"
        ),
        (
            f"  S3 BREAK: daily close below ₹{sc['breakdown']:,.2f} → skip NEW "
            f"(thesis / support broken)"
        ),
        (
            f"  Stops from fill: swing {sc['swing_pct']:+.0f}% · hard {sc['hard_pct']:+.0f}% · "
            f"thesis line ₹{sc['support']:,.2f}"
        ),
        ideals.get(mode, ideals['NEW']),
    ])
    return lines


def print_entry_scenarios_for_row(row: Dict[str, Any], cfg=None) -> None:
    for line in format_entry_scenario_lines(build_entry_scenarios(row, cfg)):
        print(line)


def new_buy_symbols_from_df(df, value_col: str, invest_col: str) -> set:
    """Symbols with INVEST > 0 and no existing position (PRIORITY 5 BUY NEW)."""
    if df is None or getattr(df, 'empty', True) or 'symbol' not in df.columns:
        return set()
    v = df[value_col] if value_col in df.columns else 0
    i = df[invest_col] if invest_col in df.columns else 0
    mask = (pd.Series(v).fillna(0) == 0) & (pd.Series(i).fillna(0) > 0)
    return set(df.loc[mask, 'symbol'].astype(str).str.strip().str.upper())


def format_swap_target_entry_ref(target_sym: str, new_buy_symbols: set) -> Optional[str]:
    """Cross-reference when full scenarios will print under PRIORITY 5."""
    sym = str(target_sym or '').strip().upper()
    if sym and sym in new_buy_symbols:
        return f"  → {sym}: entry scenarios in PRIORITY 5 below"
    return None
