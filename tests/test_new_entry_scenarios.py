"""Tests for NEW entry scenario action-plan helper."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import get_config
from src.new_entry_scenarios import (
    build_entry_scenarios,
    format_entry_scenario_lines,
    format_swap_target_entry_ref,
    new_buy_symbols_from_df,
)


class TestNewEntryScenarios(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_aiaeng_like_row_has_three_scenarios(self):
        row = {
            'symbol': 'AIAENG',
            'PRICE': 4503.60,
            'INVEST ₹': 54043.2,
            'BUY QTY': 12,
            'SUPPORT': 4200.0,
            'real_rsi': 74.1,
            'enhanced_price_change_5d': 12.7,
        }
        sc = build_entry_scenarios(row, self.cfg)
        self.assertEqual(sc['symbol'], 'AIAENG')
        self.assertEqual(sc['full_qty'], 12)
        self.assertEqual(sc['half_qty'], 6)
        self.assertTrue(sc['chase_warning'])
        lines = format_entry_scenario_lines(sc)
        text = '\n'.join(lines)
        self.assertIn('S1 HOLD', text)
        self.assertIn('S2 PULLBACK', text)
        self.assertIn('S3 BREAK', text)
        self.assertIn('4,200', text)

    def test_fallback_support_when_missing(self):
        row = {'symbol': 'TEST', 'PRICE': 1000.0, 'BUY QTY': 10}
        sc = build_entry_scenarios(row, self.cfg)
        self.assertAlmostEqual(sc['support'], 930.0, places=0)

    def test_swap_target_defers_when_symbol_in_buynew(self):
        import pandas as pd

        df = pd.DataFrame([
            {'symbol': 'HEXT', 'MY VALUE ₹': 55590, 'INVEST ₹': 0},
            {'symbol': 'AIAENG', 'MY VALUE ₹': 0, 'INVEST ₹': 54000},
        ])
        syms = new_buy_symbols_from_df(df, 'MY VALUE ₹', 'INVEST ₹')
        self.assertEqual(syms, {'AIAENG'})
        ref = format_swap_target_entry_ref('AIAENG', syms)
        self.assertIn('PRIORITY 5', ref)
        self.assertIsNone(format_swap_target_entry_ref('RELIANCE', syms))


if __name__ == '__main__':
    unittest.main()
