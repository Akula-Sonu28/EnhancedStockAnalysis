"""
Universe Filter
===============

Excludes non-stock instruments (ETFs, REITs, InvITs) and low-liquidity names from
the analysis universe so the scoring engine and recommendation history are not
polluted with signals that cannot be acted on as equities.

Public API:
    is_tradeable(symbol, avg_volume, current_price) -> Tuple[bool, str]
    filter_universe(symbols) -> Tuple[List[str], List[Tuple[str, str]]]
    is_excluded_instrument(symbol) -> Tuple[bool, str]
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

EXCLUDED_INSTRUMENTS = {
    'NIFTYBEES', 'BANKBEES', 'GOLDBEES', 'LIQUIDBEES', 'JUNIORBEES',
    'CPSEETF', 'SETFNIF50', 'SETFNIFBK', 'SETFGOLD', 'KOTAKGOLD',
    'KOTAKLIQ', 'KOTAKBKETF', 'HDFCNIFTY', 'HDFCNIFETF', 'HDFCSML250',
    'ICICILIQ', 'ICICIB22', 'ICICIM150',
    'EMBASSY', 'MINDSPACE', 'BROOKFIELD', 'NEXUS',
    'IRBINVIT', 'POWERINDIA-INVIT', 'INDIGRID',
}

EXCLUDED_PATTERNS = [
    re.compile(r'BEES$'),
    re.compile(r'IETF$'),
    re.compile(r'.*ETF$'),
    re.compile(r'.*INVIT$'),
    re.compile(r'-RR$'),
    re.compile(r'^GOLD'),
    re.compile(r'^SILVER'),
]

DEFAULT_MIN_ADV_CRORES = 10.0


def is_excluded_instrument(symbol: str) -> Tuple[bool, str]:
    """Return (True, reason) when symbol is a known ETF/REIT/InvIT, else (False, '')."""
    if not symbol:
        return False, ''
    sym = str(symbol).upper().strip()
    if sym in EXCLUDED_INSTRUMENTS:
        return True, f'excluded instrument list ({sym})'
    for pat in EXCLUDED_PATTERNS:
        if pat.search(sym):
            return True, f'matches excluded pattern {pat.pattern!r}'
    return False, ''


def _compute_adv_crores(avg_volume: Optional[float], current_price: Optional[float]) -> Optional[float]:
    """Compute average daily traded value in crores (1 cr = 1e7).

    Returns None when either input is missing or non-positive so callers can apply
    a permissive policy (do not drop stock for missing data).
    """
    try:
        if avg_volume is None or current_price is None:
            return None
        v = float(avg_volume)
        p = float(current_price)
        if v <= 0 or p <= 0:
            return None
        return (v * p) / 1e7
    except (TypeError, ValueError):
        return None


def is_tradeable(symbol: str,
                 avg_volume: Optional[float] = None,
                 current_price: Optional[float] = None,
                 min_adv_crores: float = DEFAULT_MIN_ADV_CRORES) -> Tuple[bool, str]:
    """Return (tradeable, reason) for a stock symbol.

    Permissive policy: when liquidity inputs are missing, the symbol is treated as
    tradeable so we do not silently drop names due to data-gathering gaps. The
    instrument-class exclusion still applies regardless of liquidity inputs.
    """
    excluded, reason = is_excluded_instrument(symbol)
    if excluded:
        return False, reason

    adv_crores = _compute_adv_crores(avg_volume, current_price)
    if adv_crores is None:
        return True, 'tradeable (liquidity data unavailable; permissive)'

    if adv_crores < min_adv_crores:
        return False, f'low liquidity: ADV={adv_crores:.1f} cr < {min_adv_crores} cr'

    return True, f'tradeable (ADV={adv_crores:.0f} cr)'


def filter_universe(symbols: Iterable[str],
                    avg_volumes: Optional[dict] = None,
                    prices: Optional[dict] = None,
                    min_adv_crores: float = DEFAULT_MIN_ADV_CRORES) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Filter an iterable of symbols and return (kept, dropped_with_reasons).

    Liquidity dictionaries are optional; when not provided, only the
    instrument-class exclusion is applied.
    """
    kept: List[str] = []
    dropped: List[Tuple[str, str]] = []
    avg_volumes = avg_volumes or {}
    prices = prices or {}
    for sym in symbols:
        ok, reason = is_tradeable(
            sym,
            avg_volume=avg_volumes.get(sym),
            current_price=prices.get(sym),
            min_adv_crores=min_adv_crores,
        )
        if ok:
            kept.append(sym)
        else:
            dropped.append((sym, reason))
    return kept, dropped
