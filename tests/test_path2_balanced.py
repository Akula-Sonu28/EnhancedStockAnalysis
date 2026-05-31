"""Tests for Path 2 Breakout Radar and balanced strategy."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import get_config
from src.breakout_radar import classify_breakout_tier, scan_dataframe, TIER_IGNITE, TIER_READY, TIER_COIL
from src.path2_balanced import soften_rank_sells, apply_fast_track_entry


class TestBreakoutRadar(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_ignition_tier_aiaeng_may26(self):
        row = {
            'final_blended_score': 65.9,
            'hybrid_overall_score_v2': 62.5,
            'hybrid_momentum_technical': 57.9,
            'hybrid_multi_timeframe': 90.3,
            'hybrid_fundamental_quality': 73.9,
            'real_rsi': 63.3,
            'enhanced_price_change_1d': 4.3,
            'enhanced_volume_ratio': 10.0,
            'rejection_wick_pct': 2.0,
        }
        tier, score, reasons = classify_breakout_tier(row, self.cfg)
        self.assertEqual(tier, TIER_IGNITE)
        self.assertGreater(score, 0)

    def test_coil_tier_may25_style(self):
        row = {
            'final_blended_score': 55.3,
            'hybrid_momentum_technical': 48.9,
            'hybrid_multi_timeframe': 70.0,
            'hybrid_fundamental_quality': 74.9,
            'real_rsi': 56.6,
            'enhanced_price_change_1d': -0.5,
            'enhanced_volume_ratio': 1.2,
            'dist_20d_high_pct': 2.5,
        }
        tier, _, _ = classify_breakout_tier(row, self.cfg)
        self.assertEqual(tier, TIER_COIL)

    def test_scan_excludes_holdings(self):
        df = pd.DataFrame([
            {
                'symbol': 'COIL1',
                'final_recommendation': 'BUY',
                'final_blended_score': 60,
                'hybrid_momentum_technical': 48,
                'hybrid_multi_timeframe': 72,
                'hybrid_fundamental_quality': 80,
                'real_rsi': 55,
                'enhanced_price_change_1d': 0.5,
                'enhanced_volume_ratio': 1.3,
                'dist_20d_high_pct': 2.0,
                'current_price': 100,
            },
            {
                'symbol': 'HELD1',
                'final_recommendation': 'BUY',
                'final_blended_score': 60,
                'hybrid_momentum_technical': 48,
                'hybrid_multi_timeframe': 72,
                'hybrid_fundamental_quality': 80,
                'real_rsi': 55,
                'enhanced_price_change_1d': 0.5,
                'enhanced_volume_ratio': 1.3,
                'dist_20d_high_pct': 2.0,
                'current_price': 100,
            },
        ])
        out = scan_dataframe(df, held_symbols={'HELD1'}, cfg=self.cfg)
        self.assertTrue(all(out['symbol'] != 'HELD1'))


class TestPath2Balanced(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_soften_rank_sell_in_band(self):
        class LegacyCfg:
            PATH2_BALANCED_ENABLED = True
            PATH2_SOFT_SELL_PNL_MIN = -0.03
            PATH2_SOFT_SELL_PNL_MAX = 0.03
            PATH2_CONSIDER_TRIM_PCT = 0.25
            ORACLE_STACK_ALIGN = False
            ORACLE_DISABLE_RANK_SELL_ALL = False
        df = pd.DataFrame([{
            'symbol': 'GLAND',
            'is_current_holding': True,
            'action_recommendation': 'SELL',
            'exit_reason': 'Rank bottom 20%',
            'current_profit_pct': 0.016,
            'profit_booking_pct': 1.0,
        }])
        n = soften_rank_sells(df, LegacyCfg())
        self.assertEqual(n, 1)
        self.assertEqual(df.at[0, 'action_recommendation'], 'CONSIDER SELLING')

    def test_vmq_sell_not_softened(self):
        df = pd.DataFrame([{
            'symbol': 'GESHIP',
            'is_current_holding': True,
            'action_recommendation': 'SELL',
            'exit_reason': 'VMQ HARD STOP: loss -14%',
            'current_profit_pct': -0.149,
        }])
        n = soften_rank_sells(df, self.cfg)
        self.assertEqual(n, 0)
        self.assertEqual(df.at[0, 'action_recommendation'], 'SELL')

    @patch('src.flow_quality_oracle.oracle_pause_new_entries', return_value=(False, ''))
    def test_fast_track_promotes_ignition(self, _mock_pause):
        from src.picking_metrics import enrich_results_df_oracle_stack
        alloc = pd.DataFrame(columns=[
            'symbol', 'action_recommendation', 'is_current_holding',
            'investment_amount', 'suggested_quantity', 'current_price',
        ])
        results = pd.DataFrame([{
            'symbol': 'CGPOWER',
            'company_name': 'CG Power',
            'final_recommendation': 'BUY',
            'final_blended_score': 62,
            'hybrid_overall_score_v2': 62,
            'hybrid_volume_strength': 75,
            'hybrid_momentum_technical': 52,
            'hybrid_multi_timeframe': 72,
            'hybrid_fundamental_quality': 70,
            'hybrid_risk_adjustment': 50,
            'real_rsi': 64,
            'enhanced_price_change_1d': 3.5,
            'enhanced_volume_ratio': 3.0,
            'dist_20d_high_pct': 0.5,
            'current_price': 900,
            'rejection_wick_pct': 1.0,
        }])
        results = enrich_results_df_oracle_stack(results, self.cfg)
        stats = apply_fast_track_entry(
            alloc, results, pd.DataFrame(), set(), 1_000_000, self.cfg,
        )
        self.assertTrue(stats.get('promoted'), stats.get('reason'))
        self.assertEqual(stats.get('symbol'), 'CGPOWER')


if __name__ == '__main__':
    unittest.main()
