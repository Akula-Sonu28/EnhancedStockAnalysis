"""Tests for dashboard action document builder."""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.dashboard_action_document import build_action_document, _guide_block


class TestDashboardActionDocument(unittest.TestCase):
    def test_guide_block_has_columns(self):
        g = _guide_block('P2')
        self.assertIn('what', g)
        self.assertIn('typicalReason', g)
        self.assertTrue(len(g['columns']) >= 4)
        self.assertIn('tables', g)
        self.assertTrue(len(g['tables']) >= 1)

    def test_build_document_from_report(self):
        reports = sorted((REPO_ROOT / 'reports').glob('Enhanced_Stock_Report_*.xlsx'))
        if not reports:
            self.skipTest('no report')
        r = reports[-1]
        df = pd.read_excel(r, sheet_name='Portfolio Allocation', header=1)
        doc = build_action_document(df, r, [], [], {}, None, None, [], '')
        ids = [s['id'] for s in doc['sections']]
        self.assertIn('intro', ids)
        self.assertIn('final_numbers', ids)

    def test_lvm_patch_buynew_funds_only_fund_slot(self):
        from scripts.update_analysis_canvas import _patch_lvm_action_document

        lvm = [
            {'stock': f'S{i:02d}', 'company': 'X', 'sector': 'IT', 'price': 100.0,
             'lvmScore': 200 - i, 'fundSlot': i < 12}
            for i in range(15)
        ]
        doc = {'sections': [{'id': 'sell', 'items': []}]}
        out = _patch_lvm_action_document(doc, pd.DataFrame(), lvm, {'sellTotal': 50000}, 100000)
        buynew = next(s for s in out[0]['sections'] if s['id'] == 'buynew')
        self.assertEqual(len(buynew['items']), 12)
        self.assertIn('Fund Top', buynew['headline'])

    def test_lvm_patch_buynew_shows_all_picks(self):
        from scripts.update_analysis_canvas import _patch_lvm_action_document

        lvm = [
            {'stock': 'AAA', 'company': 'A', 'sector': 'IT', 'price': 100.0, 'lvmScore': 150, 'fundSlot': True},
            {'stock': 'BBB', 'company': 'B', 'sector': 'Bank', 'price': 50.0, 'lvmScore': 140, 'fundSlot': True},
        ]
        df = pd.DataFrame([
            {'symbol': 'AAA', 'INVEST ₹': 5000, 'BUY QTY': 50, 'MY VALUE ₹': 0, 'ACTION': 'NEW POSITION (LVM)'},
        ])
        doc = {'sections': [{'id': 'sell', 'items': []}]}
        out = _patch_lvm_action_document(doc, df, lvm, {'sellTotal': 10000, 'lvmRotTotal': 5000}, 5000)
        buynew = next(s for s in out[0]['sections'] if s['id'] == 'buynew')
        self.assertEqual(len(buynew['items']), 2)
        self.assertIn('LVM', buynew['headline'])
        syms = {it['stock'] for it in buynew['items']}
        self.assertEqual(syms, {'AAA', 'BBB'})
        self.assertGreater(out[1], 0)

    def test_lvm_patch_increase_for_held_stocks(self):
        from scripts.update_analysis_canvas import _patch_lvm_action_document

        lvm = [
            {'stock': 'AAA', 'company': 'A', 'sector': 'IT', 'price': 100.0, 'lvmScore': 150},
            {'stock': 'BBB', 'company': 'B', 'sector': 'Bank', 'price': 50.0, 'lvmScore': 140},
        ]
        df = pd.DataFrame([
            {'symbol': 'AAA', 'MY VALUE ₹': 80000, 'ACTION': 'HOLD', 'INVEST ₹': 0, 'BUY QTY': 0},
            {'symbol': 'BBB', 'MY VALUE ₹': 80000, 'ACTION': 'HOLD', 'INVEST ₹': 0, 'BUY QTY': 0},
        ])
        doc = {'sections': [{'id': 'sell', 'items': []}]}
        out = _patch_lvm_action_document(doc, df, lvm, {'sellTotal': 10000, 'lvmRotTotal': 0}, 30000)
        buynew = next(s for s in out[0]['sections'] if s['id'] == 'buynew')
        for item in buynew['items']:
            self.assertEqual(item['action'], 'INCREASE')
            self.assertGreater(item.get('heldValue', 0), 0)

    def test_lvm_final_numbers_use_buy_override(self):
        from scripts.update_analysis_canvas import _build_final_numbers

        totals = {
            'swapTotal': 0, 'sellTotal': 241260, 'exitTotal': 0, 'bookTotal': 0,
            'lvmRotTotal': 714089, 'buyTotal': 0, 'increaseTotal': 0,
            'skipTotal': 0, 'considerTotal': 0,
        }
        fn = _build_final_numbers(totals, 100000, lvm_buy_total=1050800)
        self.assertEqual(fn['sellProceeds'], 955349)
        self.assertEqual(fn['buyOrders'], 1050800)
        self.assertEqual(fn['netMin'], 95451)
        self.assertEqual(fn['budgetStatus'], 'within')


if __name__ == '__main__':
    unittest.main()
