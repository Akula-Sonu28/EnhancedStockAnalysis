"""Tests for point-in-time fundamental data lookup."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backtest.data.fundamentals_pit import (
    FundamentalLookup,
    NEUTRAL,
    _fy_to_available_date,
    _safe_float,
    reset_singleton,
)


class TestFyToAvailableDate:
    def test_mar_fy(self):
        assert _fy_to_available_date('Mar 2025') == date(2025, 6, 15)

    def test_jun_fy(self):
        assert _fy_to_available_date('Jun 2024') == date(2024, 9, 15)

    def test_sep_fy(self):
        assert _fy_to_available_date('Sep 2024') == date(2024, 12, 15)

    def test_dec_fy_crosses_year(self):
        assert _fy_to_available_date('Dec 2024') == date(2025, 3, 15)

    def test_ttm_returns_none(self):
        assert _fy_to_available_date('TTM') is None

    def test_empty_returns_none(self):
        assert _fy_to_available_date('') is None

    def test_anomalous_15m_filtered(self):
        assert _fy_to_available_date('Mar 2023\n            \n            \n              15m') is None

    def test_anomalous_9m_filtered(self):
        assert _fy_to_available_date('Mar 2016\n 9m') is None


class TestSafeFloat:
    def test_normal(self):
        assert _safe_float(15.5) == 15.5

    def test_nan(self):
        assert _safe_float(float('nan')) is None

    def test_none(self):
        assert _safe_float(None) is None

    def test_inf(self):
        assert _safe_float(float('inf')) is None

    def test_string(self):
        assert _safe_float('bad') is None


def _build_test_pkl(tmp_path: Path) -> Path:
    """Create a minimal test pickle with known data."""
    rows = [
        {'symbol': 'RELIANCE', 'fiscal_year': 'Mar 2020', 'roe': 8.88,
         'debt_to_equity': 79.06, 'revenue_growth_pct': 5.0, 'earnings_growth_pct': 3.0,
         'eps': 60.0, 'bv_per_share': 700.0, 'net_profit_cr': 39000, 'equity_cr': 500000,
         'interest_expense_cr': 20000, 'is_standard_period': True, 'borrowings_cr': 100000,
         'revenue_cr': 600000},
        {'symbol': 'RELIANCE', 'fiscal_year': 'Mar 2021', 'roe': 7.68,
         'debt_to_equity': 39.84, 'revenue_growth_pct': 10.0, 'earnings_growth_pct': 8.0,
         'eps': 65.0, 'bv_per_share': 800.0, 'net_profit_cr': 45000, 'equity_cr': 600000,
         'interest_expense_cr': 15000, 'is_standard_period': True, 'borrowings_cr': 80000,
         'revenue_cr': 660000},
        {'symbol': 'RELIANCE', 'fiscal_year': 'Mar 2023\n 15m', 'roe': np.nan,
         'debt_to_equity': np.nan, 'is_standard_period': False},
        {'symbol': 'YESBANK', 'fiscal_year': 'Mar 2020', 'roe': -50.0,
         'debt_to_equity': 200.0, 'net_profit_cr': -10000, 'equity_cr': -5000,
         'interest_expense_cr': 30000, 'is_standard_period': True},
    ]
    df = pd.DataFrame(rows)
    path = tmp_path / 'test_fund.pkl'
    df.to_pickle(path)
    return path


class TestFundamentalLookup:
    def test_lookup_returns_real_roe(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        result = fl.lookup('RELIANCE', date(2021, 7, 1))
        assert abs(result['roe'] - 7.68) < 0.01

    def test_lookup_before_first_entry_returns_neutral(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        result = fl.lookup('RELIANCE', date(2019, 1, 1))
        assert result == NEUTRAL

    def test_no_future_data(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        result = fl.lookup('RELIANCE', date(2020, 7, 1))
        assert abs(result['roe'] - 8.88) < 0.01

    def test_missing_symbol_returns_neutral(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        result = fl.lookup('NONEXISTENT', date(2021, 7, 1))
        assert result == NEUTRAL

    def test_nan_roe_does_not_propagate(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        result = fl.lookup('RELIANCE', date(2021, 7, 1))
        assert result['roe'] == 7.68
        assert not np.isnan(result['roe'])

    def test_anomalous_period_excluded(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        entries = fl._data.get('RELIANCE', [])
        assert len(entries) == 2

    def test_pe_from_price(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        result = fl.lookup('RELIANCE', date(2021, 7, 1), price=1300.0)
        assert result['pe_ratio'] == round(1300.0 / 65.0, 2)

    def test_pb_from_price(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        result = fl.lookup('RELIANCE', date(2021, 7, 1), price=1600.0)
        assert result['pb_ratio'] == round(1600.0 / 800.0, 2)

    def test_value_trap_negative_equity(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        assert fl.is_value_trap('YESBANK', date(2020, 7, 1))

    def test_not_value_trap(self, tmp_path):
        path = _build_test_pkl(tmp_path)
        fl = FundamentalLookup(path=path)
        assert not fl.is_value_trap('RELIANCE', date(2021, 7, 1))

    def test_missing_pkl_returns_neutral(self, tmp_path):
        fl = FundamentalLookup(path=tmp_path / 'nonexistent.pkl')
        result = fl.lookup('RELIANCE', date(2021, 7, 1))
        assert result == NEUTRAL
