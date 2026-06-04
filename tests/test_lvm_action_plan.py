"""Tests for shared LVM action-plan helpers."""
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer
from src.lvm_action_plan import (
    LVM_DEGRADED_MSG,
    compute_lvm_p5_actions,
    compute_tax_harvest_totals,
    format_allocation_pnl,
    lvm_p5_capital_and_buys,
    lvm_rotation_reason,
    portfolio_value_for_rsi_sizing,
    resolve_lvm_universe,
    sanitize_reason_fragment,
)
from src.lowvol_momentum import _return_12m_col, is_lvm_momentum_degraded
from src.picking_metrics import classify_sell_category


class TestFormatAllocationPnl:
    def test_nan_returns_empty(self):
        assert format_allocation_pnl({'P&L %': float('nan')}) == ''

    def test_pct_column(self):
        assert format_allocation_pnl({'P&L %': 5.2}) == '+5.2%'

    def test_zero_pnl_without_cost_basis_blank(self):
        assert format_allocation_pnl({'P&L %': 0.0, 'avg_cost': 0}) == ''


class TestDashboardParity:
    def test_degraded_on_allocation_not_complete_data(self):
        from scripts.update_analysis_canvas import build_dashboard_payload
        import pandas as pd

        pa = pd.read_excel(
            'reports/Enhanced_Stock_Report_20260604_161322.xlsx',
            sheet_name='Portfolio Allocation',
            header=1,
        )
        p = build_dashboard_payload(
            'reports/Enhanced_Stock_Report_20260604_161322.xlsx',
            pa,
            portfolio_amount=0,
        )
        assert p is not None
        assert p.get('lvmDataDegraded') is False
        buynew = next(
            (s for s in p.get('sections', []) if s.get('id') == 'buynew'),
            None,
        )
        assert buynew is not None
        assert 'SKIPPED' not in str(buynew.get('headline', ''))

    def test_action_summary_excludes_footer_rows(self):
        from scripts.update_analysis_canvas import _action_summary

        df = pd.DataFrame([
            {'symbol': 'AAA', 'ACTION': 'HOLD', 'MY VALUE ₹': 1000, 'INVEST ₹': 0},
            {'symbol': float('nan'), 'ACTION': float('nan'), 'MY VALUE ₹': float('nan'), 'INVEST ₹': float('nan')},
            {
                'symbol': 'Holdings rank uses Pick rank (fq_score), not v1 SCORE.',
                'ACTION': float('nan'),
                'MY VALUE ₹': float('nan'),
                'INVEST ₹': float('nan'),
            },
        ])
        summary = _action_summary(df)
        assert len(summary) == 1
        assert summary[0]['action'] == 'HOLD'

    def test_lvm_final_numbers_use_rotation_proceeds_only(self):
        from scripts.update_analysis_canvas import _build_final_numbers

        totals = {
            'swapTotal': 100000,
            'sellTotal': 0,
            'exitTotal': 0,
            'bookTotal': 50000,
            'lvmRotTotal': 800000,
            'buyTotal': 500000,
            'increaseTotal': 0,
        }
        fn = _build_final_numbers(totals, 0, lvm_buy_total=0, lvm_active=True)
        assert fn['sellProceeds'] == 800000
        assert fn['buyOrders'] == 0

    def test_lvm_p5_capital_matches_terminal_formula(self):
        totals = {'sellTotal': 0, 'exitTotal': 0, 'lvmRotTotal': 744210}
        sell, buy, avail = lvm_p5_capital_and_buys(
            totals, 0, {'COALINDIA'}, pd.DataFrame(), None,
        )
        assert sell == 744210
        assert avail == 744210


class TestLvmReasonAndTax:
    def test_sanitize_reason_fragment(self):
        assert sanitize_reason_fragment(float('nan')) == ''
        assert sanitize_reason_fragment('hold') == 'hold'

    def test_lvm_rotation_reason_no_nan(self):
        assert 'nan' not in lvm_rotation_reason('LVM Top 20', float('nan')).lower()
        assert lvm_rotation_reason('LVM Top 20', 'prior') == 'Not in LVM Top 20 — rotate out | prior'

    def test_rsi_budget_one_percent_of_holdings(self):
        df = pd.DataFrame([{'MY VALUE ₹': 500_000}, {'MY VALUE ₹': 500_000}])
        assert portfolio_value_for_rsi_sizing(df) == 10_000.0

    def test_tax_harvest_uses_my_value_when_book_zero(self):
        sells = pd.DataFrame([
            {'ACTION': 'SELL (LVM ROTATION)', 'BOOK ₹': 0, 'MY VALUE ₹': 100000, 'P&L %': -2.0, 'TAX ₹': 0},
        ])
        tot = compute_tax_harvest_totals(sells)
        assert tot is not None
        assert tot['losses'] < 0


class TestComputeLvmP5Actions:
    def test_new_funded_names_get_buy_new(self):
        fund = {'AAA', 'BBB', 'CCC'}
        alloc = pd.DataFrame([
            {'symbol': 'AAA', 'MY VALUE ₹': 80000, 'ACTION': 'HOLD', 'PRICE': 100.0},
        ])
        actions, target, held_val, held, new = compute_lvm_p5_actions(
            fund,
            300000,
            alloc,
            None,
            min_invest=1000.0,
            price_by_sym={'BBB': 50.0, 'CCC': 40.0},
        )
        assert len(new) == 2
        buys = [a for a in actions if a['action'] in ('BUY NEW', 'INCREASE')]
        assert len(buys) >= 2
        assert target > 0


class TestSellCategoryLvm:
    def test_lvm_rotation_action(self):
        assert classify_sell_category({
            'action_recommendation': 'SELL (LVM ROTATION)',
            'exit_reason': 'Not in LVM Top 20 — rotate out',
        }) == 'LVM_ROTATION'


class TestLvmP5FromCompleteData:
    """Regression: new fund names not on allocation sheet still get BUY NEW."""

    def test_buy_new_when_only_in_complete_data(self):
        fund = {'NEW1', 'OLD1'}
        alloc = pd.DataFrame([
            {'symbol': 'OLD1', 'MY VALUE ₹': 90000, 'ACTION': 'HOLD', 'PRICE': 100.0},
        ])
        complete = pd.DataFrame([
            {'symbol': 'NEW1', 'current_price': 250.0},
            {'symbol': 'OLD1', 'current_price': 100.0},
        ])
        actions, target, _, held, new = compute_lvm_p5_actions(
            fund, 200000, alloc, complete, min_invest=1000.0,
        )
        assert 'NEW1' in new
        buys = {a['sym']: a for a in actions if a['action'] == 'BUY NEW'}
        assert 'NEW1' in buys
        assert buys['NEW1']['shares'] > 0


class TestLvmMomentumIntegrity:
    def test_return_12m_all_missing_logs_warning(self, caplog):
        df = pd.DataFrame({'symbol': ['A', 'B'], 'current_price': [100.0, 200.0]})
        with caplog.at_level(logging.WARNING):
            out = _return_12m_col(df)
        assert (out == 0.0).all()
        assert any('no momentum columns' in r.message for r in caplog.records)

    def test_is_lvm_momentum_degraded_no_columns(self):
        df = pd.DataFrame({'symbol': ['A'], 'current_price': [100.0]})
        assert is_lvm_momentum_degraded(df)

    def test_is_lvm_momentum_degraded_with_variance(self):
        df = pd.DataFrame({
            'symbol': ['A', 'B', 'C'],
            'current_price': [100.0, 200.0, 300.0],
            'price_change_1y': [5.0, 15.0, 25.0],
        })
        assert not is_lvm_momentum_degraded(df)

    def test_resolve_lvm_universe_degraded_returns_empty_fund(self):
        df = pd.DataFrame({'symbol': ['A'], 'current_price': [100.0]})
        screen, fund, _, msg = resolve_lvm_universe(df)
        assert screen == set()
        assert fund == set()
        assert msg == LVM_DEGRADED_MSG

    def test_compute_lvm_momentum_fields_from_hist(self):
        n = 60
        closes = np.linspace(100.0, 150.0, n)
        hist = pd.DataFrame({
            'Close': closes,
            'High': closes,
            'Low': closes,
        })
        fields = EnhancedTop200StockAnalyzer._compute_lvm_momentum_fields(hist)
        assert 'price_change_1y' in fields
        assert fields['price_change_1y'] > 0
        assert 'legacy_sma_50' in fields

    def test_r12_exclusion_list_protects_lvm_columns(self):
        src = (Path(__file__).resolve().parents[1] / 'analyze_top200_stocks_enhanced.py').read_text()
        assert "'price_change_1y'" in src
        assert "'legacy_sma_50'" in src
        assert "'quality_lvm_eligible'" in src
