"""Tests for turbo MTF primary entry driver."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import get_config
from src.turbo_entry import (
    compute_turbo_score,
    evaluate_turbo_entry_gate,
    get_confirm_return_pct,
    sync_price_change_aliases,
)


class TestTurboEntry(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_recomputes_not_v2_alias(self):
        row = {
            'hybrid_overall_score_v2': 62.5,
            'score_v2': 62.5,
            'hybrid_momentum_technical': 55,
            'hybrid_volume_strength': 60,
            'hybrid_multi_timeframe': 70,
            'hybrid_fundamental_quality': 50,
        }
        turbo = compute_turbo_score(row, self.cfg)
        self.assertNotEqual(turbo, 62.5)
        self.assertGreater(turbo, 0)

    def test_blocks_value_trap_low_turbo(self):
        row = {
            'hybrid_overall_score_v2': 58.0,
            'hybrid_momentum_technical': 42.0,
            'hybrid_multi_timeframe': 50.0,
            'hybrid_fundamental_quality': 85.0,
            'final_blended_score': 67.0,
            'price_change_5d': 1.5,
        }
        r = evaluate_turbo_entry_gate(row, self.cfg, new_this_week=0)
        self.assertFalse(r.allowed)

    def test_confirm_wait_when_turbo_ok_but_price_flat(self):
        row = {
            'hybrid_overall_score_v2': 62.0,
            'hybrid_momentum_technical': 55.0,
            'hybrid_multi_timeframe': 68.0,
            'hybrid_volume_strength': 65.0,
            'hybrid_fundamental_quality': 65.0,
            'final_blended_score': 60.0,
            'price_change_5d': -1.2,
        }
        r = evaluate_turbo_entry_gate(row, self.cfg, new_this_week=0)
        self.assertFalse(r.allowed)
        self.assertEqual(r.status, 'CONFIRM_WAIT')

    def test_passes_strong_turbo_with_confirm(self):
        row = {
            'hybrid_overall_score_v2': 65.0,
            'hybrid_momentum_technical': 58.0,
            'hybrid_multi_timeframe': 68.0,
            'hybrid_volume_strength': 70.0,
            'hybrid_fundamental_quality': 70.0,
            'final_blended_score': 62.0,
            'price_change_5d': 2.5,
            'price_change_1d': 1.0,
            'real_rsi': 62.0,
        }
        r = evaluate_turbo_entry_gate(row, self.cfg, new_this_week=0)
        self.assertTrue(r.allowed)
        self.assertEqual(r.status, 'PASS')

    def test_confirm_from_5d_proxy(self):
        row = {'price_change_5d': 3.1}
        self.assertAlmostEqual(get_confirm_return_pct(row), 3.1)

    def test_negative_1d_overrides_positive_5d(self):
        row = {
            'price_change_5d': 21.8,
            'enhanced_price_change_20d': 21.8,
            'price_change_1d': -4.36,
        }
        self.assertAlmostEqual(get_confirm_return_pct(row), -4.36)

    def test_never_falls_back_to_20d(self):
        row = {'enhanced_price_change_20d': 21.8}
        self.assertAlmostEqual(get_confirm_return_pct(row), 0.0)

    def test_sync_aliases_from_enhanced_tech(self):
        row = {'enhanced_tech_price_change_5d': 8.2, 'enhanced_tech_price_change_1d': -2.0}
        synced = sync_price_change_aliases(row)
        self.assertAlmostEqual(synced['price_change_5d'], 8.2)
        self.assertAlmostEqual(get_confirm_return_pct(synced), -2.0)

    def test_atgl_like_reversal_blocked(self):
        """Post-spike reversal: +5d chase, RSI 79.6, -4.4% day, 10% rejection wick."""
        row = {
            'hybrid_overall_score_v2': 62.4,
            'hybrid_momentum_technical': 53.0,
            'hybrid_multi_timeframe': 71.2,
            'hybrid_fundamental_quality': 70.0,
            'final_blended_score': 64.8,
            'price_change_5d': 21.1,
            'price_change_1d': -4.36,
            'real_rsi': 79.6,
            'rejection_wick_pct': 10.1,
        }
        r = evaluate_turbo_entry_gate(row, self.cfg, new_this_week=0)
        self.assertFalse(r.allowed)
        self.assertIn(r.status, ('CONFIRM_WAIT', 'WATCHLIST'))


if __name__ == '__main__':
    unittest.main()
