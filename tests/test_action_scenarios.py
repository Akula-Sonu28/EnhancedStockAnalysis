"""Tests for exit and unified action scenarios."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import get_config
from src.action_scenarios import scenario_payload_for_section
from src.exit_scenarios import build_exit_scenarios, format_exit_scenario_lines, format_hold_monitor_lines, build_hold_monitor
from src.new_entry_scenarios import format_entry_scenario_lines, build_entry_scenarios


class TestExitScenarios(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_hard_sell_has_e1_e3(self):
        row = {
            'symbol': 'GESHIP',
            'ACTION': 'SELL',
            'REASON': 'VMQ HARD STOP: loss -10% <= -8%',
            'PRICE': 1425.0,
            'MY QTY': 53,
        }
        sc = build_exit_scenarios(row, 'sell', self.cfg)
        lines = format_exit_scenario_lines(sc)
        text = '\n'.join(lines)
        self.assertIn('EXIT SCENARIOS', text)
        self.assertIn('E1 OPEN', text)
        self.assertIn('E3 SKIP', text)
        self.assertEqual(sc['urgency'], 'hard')

    def test_consider_is_soft(self):
        row = {'symbol': 'X', 'ACTION': 'CONSIDER SELLING', 'PRICE': 100.0, 'MY QTY': 10}
        sc = build_exit_scenarios(row, 'consider', self.cfg)
        self.assertEqual(sc['urgency'], 'soft')
        self.assertIn('E3 DEFER', '\n'.join(format_exit_scenario_lines(sc)))

    def test_hold_monitor_levels(self):
        row = {'symbol': 'HEXT', 'PRICE': 510.0, 'MY QTY': 109}
        mon = build_hold_monitor(row, self.cfg)
        lines = format_hold_monitor_lines(mon)
        self.assertIn('M1 HOLD', '\n'.join(lines))
        self.assertIn('M3 ALERT', '\n'.join(lines))


class TestActionScenarios(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_buynew_entry_payload(self):
        row = {'symbol': 'AIAENG', 'PRICE': 4500.0, 'INVEST ₹': 54000, 'BUY QTY': 12}
        payload = scenario_payload_for_section(row, 'buynew', self.cfg)
        self.assertIn('entryScenarios', payload)
        self.assertIn('S2 PULLBACK', '\n'.join(payload['entryScenarios']['lines']))

    def test_swap_defers_entry_to_buynew(self):
        import pandas as pd

        df = pd.DataFrame([
            {'symbol': 'HEXT', 'ACTION': 'SWAP', 'PRICE': 510.0, 'MY QTY': 109, 'MY VALUE ₹': 55590},
            {'symbol': 'AIAENG', 'PRICE': 4500.0, 'INVEST ₹': 54000, 'BUY QTY': 12, 'MY VALUE ₹': 0},
        ])
        payload = scenario_payload_for_section(
            df.iloc[0].to_dict(),
            'swap',
            self.cfg,
            new_buy_syms={'AIAENG'},
            swap_target='AIAENG',
            allocation_df=df,
        )
        self.assertIn('exitScenarios', payload)
        self.assertIn('PRIORITY 5', payload.get('entryScenariosRef', ''))
        self.assertNotIn('entryScenarios', payload)

    def test_increase_uses_add_mode(self):
        row = {'symbol': 'TCS', 'PRICE': 4000.0, 'INVEST ₹': 20000, 'BUY QTY': 5}
        payload = scenario_payload_for_section(row, 'increase', self.cfg)
        text = '\n'.join(payload['entryScenarios']['lines'])
        self.assertIn('ADD SCENARIOS', text)


if __name__ == '__main__':
    unittest.main()
