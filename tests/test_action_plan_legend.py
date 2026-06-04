"""Tests for action plan category legend."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.action_plan_legend import (
    ACTION_PLAN_CATEGORIES,
    enrich_section_guide,
    format_action_plan_legend,
    format_holdings_action_lines,
    row_reason_text,
)


class TestActionPlanLegend(unittest.TestCase):
    def test_all_categories_have_four_fields(self):
        for item in ACTION_PLAN_CATEGORIES:
            self.assertEqual(len(item), 4)

    def test_full_legend_includes_priorities(self):
        text = '\n'.join(format_action_plan_legend())
        self.assertIn('PRIORITY 5: BUY NEW', text)
        self.assertIn('PRIORITY 2: SELL', text)
        self.assertIn('Typical REASON', text)

    def test_enrich_section_guide_vmq_tables(self):
        g = enrich_section_guide('VMQ', {'what': 'test'})
        self.assertIn('tables', g)
        self.assertGreaterEqual(len(g['tables'][0]['rows']), 3)

    def test_row_reason_text_prefers_reason_column(self):
        row = {'symbol': 'TCS', 'ACTION': 'HOLD', 'REASON': 'HOLD STEADY Rank #42'}
        self.assertEqual(row_reason_text(row), 'HOLD STEADY Rank #42')

    def test_format_holdings_action_lines(self):
        import pandas as pd

        df = pd.DataFrame([
            {'symbol': 'HEXT', 'ACTION': 'HOLD', 'REASON': 'ORACLE_NO_RANK_SELL', 'MY VALUE ₹': 50000, 'P&L %': -2.5},
        ])
        lines = format_holdings_action_lines(df, value_col='MY VALUE ₹', pnl_col='P&L %')
        self.assertEqual(len(lines), 1)
        self.assertIn('HEXT', lines[0])
        self.assertIn('ORACLE_NO_RANK_SELL', lines[0])
        self.assertIn('-2.5%', lines[0])

    def test_decode_reason_plain(self):
        from src.action_plan_legend import (
            DASHBOARD_SKIP_SECTIONS,
            build_context_glossary,
            build_dashboard_glossary,
            dashboard_policy,
            decode_reason_plain,
            decode_tier_plain,
            explain_radar_reason,
        )

        self.assertIn('−8%', decode_reason_plain('VMQ HARD STOP: loss -14.5% <= -8%'))
        self.assertIn(
            'LVM rotation',
            decode_reason_plain(
                '📊 HOLD STEADY (Rank #8/12)',
                action='SELL (LVM ROTATION)',
                sell_why='LVM_ROTATION',
            ),
        )
        self.assertIn('chase risk', decode_tier_plain('B-IGNITE').lower())
        self.assertIn('volume', explain_radar_reason('ignition +10.4% vol 3.1x mtf 84').lower())
        pol = dashboard_policy()
        self.assertEqual(set(pol['skipSections']), set(DASHBOARD_SKIP_SECTIONS))
        g = build_dashboard_glossary()
        self.assertIn('columns', g)
        self.assertIn('entryScenarios', g)
        self.assertGreater(len(g['categories']), 10)
        self.assertGreater(len(g['reasonPatterns']), 5)
        ctx = build_context_glossary({'sections': [{'id': 'radar', 'items': [
            {'tier': 'B-IGNITE', 'reason': 'ignition +10.4% vol 3.1x mtf 84', 'trigger': 'Active: vol>=2.5x'},
        ]}]})
        codes = {e['code'] for e in ctx}
        self.assertIn('B-IGNITE', codes)


if __name__ == '__main__':
    unittest.main()
