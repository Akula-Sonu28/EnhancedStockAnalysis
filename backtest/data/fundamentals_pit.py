"""Point-in-time fundamental data lookup from Screener.in cache.

Maps (symbol, as_of_date) -> {pe_ratio, roe, debt_to_equity, pb_ratio,
earnings_growth, revenue_growth, dividend_yield} using the latest
annual filing available BEFORE or ON the as_of_date.

Fiscal year "Mar 2025" -> available from 15 Jun 2025 (conservative).
Non-standard periods (15m, 9m, etc.) are excluded.
"""
from __future__ import annotations

import logging
import math
import re
from datetime import date
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
FUND_PKL = REPO_ROOT / 'data' / 'screener_fundamentals.pkl'

NEUTRAL = {
    'pe_ratio': 20.0,
    'roe': 15.0,
    'debt_to_equity': 50.0,
    'pb_ratio': 2.0,
    'earnings_growth': 0.0,
    'revenue_growth': 0.0,
    'dividend_yield': 0.0,
}

_FIELD_KEYS = ['roe', 'debt_to_equity', 'revenue_growth', 'earnings_growth',
               'eps', 'bv_per_share', 'interest_expense_cr', 'net_profit_cr',
               'equity_cr']


def _fy_to_available_date(fy: str) -> Optional[date]:
    """Convert fiscal year label to the earliest date the data would be public."""
    fy = str(fy).strip()
    if fy == 'TTM' or not fy:
        return None
    if re.search(r'\d+m', fy):
        return None
    m = re.match(r'(Mar|Jun|Sep|Dec)\s*(\d{4})', fy)
    if not m:
        return None
    month_str, year = m.group(1), int(m.group(2))
    month_map = {'Mar': 6, 'Jun': 9, 'Sep': 12, 'Dec': 3}
    avail_month = month_map[month_str]
    avail_year = year if month_str != 'Dec' else year + 1
    return date(avail_year, avail_month, 15)


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _count_non_null(entry: dict) -> int:
    return sum(1 for k in _FIELD_KEYS if _safe_float(entry.get(k)) is not None)


class FundamentalLookup:
    """In-memory PIT fundamental cache. Build once, query per (symbol, date)."""

    def __init__(self, path: Path = FUND_PKL):
        if not path.exists():
            logging.warning('[fundamentals] %s not found — all lookups return neutral', path)
            self._data: Dict[str, list] = {}
            return
        df = pd.read_pickle(path)
        self._data = {}
        for sym, grp in df.groupby('symbol'):
            raw_entries: Dict[date, list] = {}
            for _, row in grp.iterrows():
                is_std = row.get('is_standard_period', True)
                if isinstance(is_std, bool) and not is_std:
                    continue
                avail = _fy_to_available_date(row['fiscal_year'])
                if avail is None:
                    continue
                entry = {
                    'available_from': avail,
                    'roe': _safe_float(row.get('roe')),
                    'debt_to_equity': _safe_float(row.get('debt_to_equity')),
                    'revenue_growth': _safe_float(row.get('revenue_growth_pct')),
                    'earnings_growth': _safe_float(row.get('earnings_growth_pct')),
                    'eps': _safe_float(row.get('eps')),
                    'bv_per_share': _safe_float(row.get('bv_per_share')),
                    'equity_cr': _safe_float(row.get('equity_cr')),
                    'net_profit_cr': _safe_float(row.get('net_profit_cr')),
                    'interest_expense_cr': _safe_float(row.get('interest_expense_cr')),
                }
                raw_entries.setdefault(avail, []).append(entry)

            deduped = []
            for avail_date, candidates in raw_entries.items():
                best = max(candidates, key=_count_non_null)
                deduped.append(best)
            deduped.sort(key=lambda e: e['available_from'])
            self._data[str(sym).upper()] = deduped
        logging.info('[fundamentals] loaded PIT data for %d symbols', len(self._data))

    def lookup(self, symbol: str, as_of, price: float = 0.0) -> dict:
        """Return latest available fundamentals for symbol as of date.

        If price > 0, compute PE = price / EPS and PB = price / BV_per_share.
        """
        sym = str(symbol).upper().replace('.NS', '')
        if not isinstance(as_of, date) or isinstance(as_of, pd.Timestamp):
            as_of = pd.Timestamp(as_of).date()
        entries = self._data.get(sym)
        if not entries:
            return dict(NEUTRAL)
        best = None
        for e in entries:
            if e['available_from'] <= as_of:
                best = e
            else:
                break
        if best is None:
            return dict(NEUTRAL)

        out = dict(NEUTRAL)
        for key in ('roe', 'debt_to_equity', 'revenue_growth', 'earnings_growth'):
            val = _safe_float(best.get(key))
            if val is not None:
                out[key] = val

        eps = _safe_float(best.get('eps'))
        bv = _safe_float(best.get('bv_per_share'))
        if price > 0 and eps is not None and eps > 0:
            out['pe_ratio'] = round(price / eps, 2)
        if price > 0 and bv is not None and bv > 0:
            out['pb_ratio'] = round(price / bv, 2)

        interest = _safe_float(best.get('interest_expense_cr'))
        net_profit = _safe_float(best.get('net_profit_cr'))
        equity = _safe_float(best.get('equity_cr'))
        if interest is not None and interest > 0 and net_profit is not None:
            pbt_approx = net_profit * 1.25
            out['interest_coverage'] = round(pbt_approx / interest, 2)
        if equity is not None and equity < 0:
            out['negative_equity'] = True

        return out

    def has_real_filing(self, symbol: str, as_of) -> bool:
        """True if a Screener annual filing was public on or before as_of (not NEUTRAL fill)."""
        sym = str(symbol).upper().replace('.NS', '')
        if not isinstance(as_of, date) or isinstance(as_of, pd.Timestamp):
            as_of = pd.Timestamp(as_of).date()
        entries = self._data.get(sym)
        if not entries:
            return False
        best = None
        for e in entries:
            if e['available_from'] <= as_of:
                best = e
            else:
                break
        if best is None:
            return False
        return _safe_float(best.get('roe')) is not None

    def is_value_trap(self, symbol: str, as_of, price: float = 0.0) -> bool:
        """Return True if stock shows distress signals (interest coverage < 1.5 or negative equity)."""
        f = self.lookup(symbol, as_of, price)
        if f.get('negative_equity'):
            return True
        ic = f.get('interest_coverage')
        if ic is not None and ic < 1.5:
            return True
        return False

    @property
    def symbol_count(self) -> int:
        return len(self._data)


_SINGLETON: Optional[FundamentalLookup] = None


def get_fundamental_lookup() -> FundamentalLookup:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = FundamentalLookup()
    return _SINGLETON


def reset_singleton() -> None:
    global _SINGLETON
    _SINGLETON = None
