"""Tests for QMST HTML dashboard build and payload contracts."""
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


class TestAnalysisDashboard(unittest.TestCase):
    def test_dashboard_policy_matches_skip_list(self):
        from src.action_plan_legend import DASHBOARD_SKIP_SECTIONS, dashboard_policy

        pol = dashboard_policy()
        self.assertEqual(set(pol['skipSections']), set(DASHBOARD_SKIP_SECTIONS))
        self.assertIn('radar', pol['monitorSectionIds'])

    def test_apply_dashboard_policy_lvm_keeps_rsi(self):
        from src.analysis_dashboard import apply_dashboard_policy

        payload = {'activeStrategy': 'LowVol→Mom', 'dashboardPolicy': {'skipSections': []}}
        apply_dashboard_policy(payload)
        skip = set(payload['dashboardPolicy']['skipSections'])
        self.assertIn('radar', skip)
        self.assertNotIn('rsipullback', skip)
        self.assertNotIn('hold', skip)

    def test_slim_payload_keys(self):
        from src.analysis_dashboard import _DASHBOARD_PAYLOAD_KEYS, slim_dashboard_payload
        from src.action_plan_legend import DASHBOARD_SKIP_SECTIONS

        full = {
            'runDate': 'x', 'report': 'r.xlsx', 'reportPath': '/tmp/r.xlsx', 'buildVersion': 'x|r.xlsx|1',
            'regime': 'Sideways', 'activeStrategy': 'QMST', 'positions': 1, 'portfolioValue': 1,
            'sectorChart': [{'name': 'Tech', 'value': 100}],
            'finalNumbers': {}, 'holdings': [{'stock': 'T', 'value': 1, 'pnlPct': 1.0, 'pnlPctAlloc': 1.0}],
            'actionPlanGuide': {'readingRule': 'r', 'categories': [{'key': 'x'}], 'reasonPatterns': []},
            'actionDocument': {
                'sections': [
                    {'id': 'intro', 'kind': 'intro', 'headline': 'H', 'items': []},
                    {'id': 'hold', 'kind': 'priority', 'headline': 'Hold', 'items': [{'stock': 'X', 'score': 99}]},
                    {'id': 'sell', 'kind': 'priority', 'headline': 'Priority 2: SELL', 'items': [{
                        'stock': 'A', 'action': 'SELL', 'when': 'Within 2 weeks', 'reason': 'VMQ HARD STOP',
                        'reasonPlain': 'x', 'sellWhy': 'VMQ_HARD_STOP', 'stopLoss': 100,
                        'v2Score': 46.9, 'score': 59.1, 'sector': 'Industrials',
                        'entryScenarios': {'lines': ['S1: a'], 's1': 'half', 's2': 'full'},
                    }]},
                    {'id': 'final_numbers', 'kind': 'footer', 'headline': 'Final', 'finalNumbers': {'netMin': 0}, 'items': []},
                ],
            },
            'dashboardPolicy': {'skipSections': sorted(DASHBOARD_SKIP_SECTIONS), 'monitorSectionIds': ['radar']},
            'dualStrategy': [],
            'trust': {},
            'lvmTop10': [],
            'rsiPullback': [],
        }
        slim = slim_dashboard_payload(full)
        self.assertNotIn('dualStrategy', slim)
        self.assertNotIn('trust', slim)
        self.assertNotIn('categories', slim['actionPlanGuide'])
        ids = [s['id'] for s in slim['actionDocument']['sections']]
        self.assertNotIn('intro', ids)
        self.assertNotIn('hold', ids)
        self.assertIn('sell', ids)
        sell_item = slim['actionDocument']['sections'][0]['items'][0]
        self.assertIn('v2Score', sell_item)
        self.assertIn('sector', sell_item)
        self.assertIn('when', sell_item)
        self.assertIn('s1', sell_item['entryScenarios'])
        self.assertNotIn('lines', sell_item.get('entryScenarios', {}))
        for key in _DASHBOARD_PAYLOAD_KEYS:
            self.assertIn(key, slim)

    def test_build_dashboard_if_report_exists(self):
        reports = sorted((REPO_ROOT / 'reports').glob('Enhanced_Stock_Report_*.xlsx'))
        if not reports:
            self.skipTest('no report')
        from src.analysis_dashboard import build_analysis_dashboard, DEFAULT_OUTPUT

        out = DEFAULT_OUTPUT
        if out.exists():
            out.unlink()
        path = build_analysis_dashboard(str(reports[-1]), output_path=out)
        self.assertTrue(path and path.exists())
        html = path.read_text(encoding='utf-8')
        m = re.search(r'window\.DASHBOARD_DATA = (\{.*?\});', html, re.DOTALL)
        self.assertIsNotNone(m)
        data = json.loads(m.group(1))
        self.assertIn('dashboardPolicy', data)
        self.assertIn('reportPath', data)
        self.assertTrue(data['reportPath'].endswith('.xlsx'))
        hidden = set(data['dashboardPolicy']['skipSections'])
        ids = {s['id'] for s in data['actionDocument']['sections']}
        self.assertTrue(hidden.isdisjoint(ids), f'hidden sections leaked: {hidden & ids}')
        raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        self.assertLess(len(raw), 120_000, 'embedded JSON should stay under ~120KB')
        holds = data.get('holdings') or []
        if holds:
            h = next((x for x in holds if x.get('pnlPctAlloc')), holds[0])
            self.assertIn('pnlPct', h)
            if h.get('pnlPctAlloc'):
                self.assertEqual(h['pnlPct'], h['pnlPctAlloc'])

    def test_holdings_enriched_pnl_from_allocation(self):
        import pandas as pd
        from scripts.update_analysis_canvas import _build_holdings_enriched

        df = pd.DataFrame([
            {
                'symbol': 'TEST',
                'ACTION': 'HOLD',
                'WHEN': 'No action',
                'SCORE': 70,
                'V2 RAW': 65,
                'P&L %': 9.2,
                'PRICE': 739.0,
                'SUPPORT': 572.45,
                'sector': 'Tech',
                'company_name': 'Test Industries Ltd',
                'STOP LOSS': 100,
                'ML': 'HOLD',
                'REASON': 'ORACLE_NO_RANK_SELL: rank exit disabled',
            },
        ])
        rows = _build_holdings_enriched(df, [{'stock': 'TEST', 'value': 50000, 'qty': 10}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['pnlPct'], 9.2)
        self.assertEqual(rows[0]['pnlPctAlloc'], 9.2)
        self.assertEqual(rows[0]['company'], 'Test Industries Ltd')
        self.assertIn('reasonPlain', rows[0])
        self.assertIn('summaryLine', rows[0])
        self.assertIn('TEST', rows[0]['summaryLine'])
        self.assertIn('ORACLE_NO_RANK_SELL', rows[0]['summaryLine'])
        mon = rows[0].get('monitorScenarios') or {}
        mon_text = '\n'.join(mon.get('lines') or [])
        self.assertIn('M1', mon_text)
        self.assertIn('M3', mon_text)
        from src.analysis_dashboard import slim_dashboard_payload
        slim_h = slim_dashboard_payload({
            'runDate': 'x', 'report': 'r', 'reportPath': '/x', 'regime': 'x',
            'positions': 1, 'portfolioValue': 1, 'finalNumbers': {},
            'actionPlanGuide': {'readingRule': 'r'}, 'actionDocument': {'sections': []},
            'dashboardPolicy': {'skipSections': [], 'monitorSectionIds': []},
            'holdings': [rows[0]],
        })['holdings'][0]
        self.assertIn('m1', slim_h.get('monitorScenarios', {}))
        self.assertNotIn('lines', slim_h.get('monitorScenarios', {}))
        self.assertNotIn('structured', slim_h.get('monitorScenarios', {}))
        self.assertNotIn('reason', slim_h)

    def test_slim_holdings_keeps_monitor_scenarios(self):
        from src.analysis_dashboard import slim_dashboard_payload

        full = {
            'runDate': 'x', 'report': 'r.xlsx', 'reportPath': '/tmp/r.xlsx',
            'regime': 'Sideways', 'positions': 1, 'portfolioValue': 1,
            'finalNumbers': {}, 'actionPlanGuide': {'readingRule': 'r'},
            'actionDocument': {'sections': []},
            'dashboardPolicy': {'skipSections': [], 'monitorSectionIds': []},
            'holdings': [{
                'stock': 'T', 'value': 1, 'action': 'HOLD',
                'summaryLine': 'T: HOLD — reason',
                'monitorScenarios': {
                    'symbol': 'T',
                    'lines': ['  M1 HOLD: above ₹100', '  M2 REVIEW: below ₹100'],
                    'structured': {'support': 100, 'breakdown': 98, 'price': 110},
                },
            }],
        }
        slim = slim_dashboard_payload(full)
        h = slim['holdings'][0]
        self.assertEqual(h['summaryLine'], 'T: HOLD — reason')
        self.assertIn('m1', h['monitorScenarios'])
        self.assertNotIn('lines', h['monitorScenarios'])

    def test_holdings_lvm_gtt_stop_fields(self):
        import pandas as pd
        from unittest.mock import patch
        from scripts.update_analysis_canvas import _build_holdings_enriched

        df = pd.DataFrame([
            {
                'symbol': 'LVMX',
                'ACTION': 'HOLD',
                'WHEN': 'No action',
                'SCORE': 70,
                'V2 RAW': 65,
                'P&L %': 1.0,
                'PRICE': 1000.0,
                'SUPPORT': 900.0,
                'sector': 'Tech',
                'company_name': 'LVM Test',
                'STOP LOSS': 950,
                'ML': 'HOLD',
                'REASON': 'LVM hold',
            },
        ])
        holdings = [{'stock': 'LVMX', 'value': 50000, 'qty': 10}]
        with patch('scripts.update_analysis_canvas._is_lvm_pick_mode', return_value=True):
            rows = _build_holdings_enriched(df, holdings)
        self.assertEqual(rows[0]['gttStop'], 900.0)
        self.assertEqual(rows[0]['gttStopPct'], 10.0)


if __name__ == '__main__':
    unittest.main()
