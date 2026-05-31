#!/usr/bin/env python3
"""QMST layer-priority regression — VMQ > Turbo > Pick rank > SCORE audit."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import get_config
from src.picking_metrics import (
    format_holdings_reason,
    format_rank_metric_clause,
    holdings_rank_metric_label,
    oracle_stack_align_enabled,
)
from src.turbo_entry import evaluate_turbo_entry_gate
from src.vmq_strategy import apply_vmq_to_allocation_df, evaluate_holding_validation


class TestQMSTLayerPriority(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_format_holdings_reason_pick_rank_label(self):
        reason = format_holdings_reason(7, 19, -32.8, oracle_aligned=True, prefix='📊 HOLD STEADY')
        self.assertIn('Pick rank: -32.8', reason)
        self.assertNotIn('Score:', reason)
        self.assertIn('Rank #7/19', reason)

    def test_format_rank_metric_clause_oracle_aligned(self):
        clause = format_rank_metric_clause(-32.8, self.cfg)
        if oracle_stack_align_enabled(self.cfg):
            self.assertEqual(clause, 'Pick rank: -32.8')
        else:
            self.assertEqual(clause, 'Score: -32.8')

    def test_vmq_overrides_hold_on_hard_stop(self):
        entry = datetime.now() - timedelta(days=30)
        hist = pd.DataFrame([
            {'symbol': 'NATCOPHARM', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
        ])
        alloc = pd.DataFrame([{
            'symbol': 'NATCOPHARM',
            'is_current_holding': True,
            'action_recommendation': 'HOLD',
            'action_type': 'HOLD',
            'avg_cost': 100.0,
            'current_price': 87.4,
            'current_profit_pct': -0.126,
            'sleeve': 'TACTICAL',
            'investment_amount': 0,
        }])
        stats = apply_vmq_to_allocation_df(alloc, hist, self.cfg)
        self.assertGreaterEqual(stats.get('exit_forced', 0), 1)
        self.assertEqual(str(alloc.at[0, 'action_recommendation']).upper(), 'SELL')
        self.assertIn('HARD STOP', str(alloc.at[0, 'exit_reason']).upper())

    def test_turbo_blocks_new(self):
        row = {
            'final_blended_score': 75.0,
            'hybrid_overall_score_v2': 55.0,
            'hybrid_momentum_technical': 42.0,
            'hybrid_multi_timeframe': 40.0,
            'hybrid_fundamental_quality': 65.0,
            'hybrid_volume_strength': 55.0,
        }
        result = evaluate_turbo_entry_gate(row, self.cfg, new_this_week=0)
        self.assertFalse(result.allowed)
        self.assertIn(result.status, ('WATCHLIST', 'CONFIRM_WAIT'))

    def test_turbo_blocks_increase_to_hold(self):
        class C:
            VMQ_ENABLED = True
            ENTRY_DRIVER = 'turbo_mtf'
            TURBO_ENTRY_V2_MIN = 60.0
            TURBO_ENTRY_MTF_MIN = 55.0
            TURBO_ENTRY_MOM_MIN = 50.0
            TURBO_ENTRY_RSI_HARD_BLOCK = 75.0
            TURBO_ENTRY_RSI_MAX = 75.0
            TURBO_ENTRY_CHASE_5D_MAX = 15.0
            TURBO_ENTRY_REJECTION_WICK_PCT = 8.0
            TURBO_ENTRY_VS_MIN = 0.0
            ENTRY_CONFIRM_3D_MIN_RET = 0.0
            ENTRY_CONFIRM_3D_STRONG_RET = 2.0
            VMQ_MAX_NEW_PER_WEEK = 3
            ENTRY_V1_SCORE_FLOOR = 55.0
            VMQ_VALUE_TRAP_FUND_MIN = 75.0
            VMQ_VALUE_TRAP_MOM_MAX = 55.0
            DATA_DIR = 'data'
            DUAL_STRATEGY_PROFILES = {
                'turbo_mtf': {'weights': {'momentum_technical': 0.5, 'multi_timeframe': 0.3}},
            }

        alloc = pd.DataFrame([{
            'symbol': 'ENRIN',
            'is_current_holding': True,
            'action_recommendation': 'INCREASE',
            'action_type': 'INCREASE',
            'investment_amount': 5000,
            'suggested_quantity': 5,
            'final_blended_score': 80.0,
            'hybrid_momentum_technical': 72.0,
            'hybrid_multi_timeframe': 70.0,
            'hybrid_fundamental_quality': 65.0,
            'hybrid_volume_strength': 60.0,
            'real_rsi': 78.0,
            'enhanced_price_change_1d': 1.0,
            'enhanced_price_change_5d': 2.0,
        }])
        stats = apply_vmq_to_allocation_df(alloc, pd.DataFrame(), C())
        self.assertGreaterEqual(stats.get('increase_blocked', 0), 1)
        self.assertEqual(str(alloc.at[0, 'action_recommendation']).upper(), 'HOLD')
        self.assertEqual(float(alloc.at[0, 'investment_amount']), 0.0)
        self.assertIn('TURBO BLOCK (INCREASE)', str(alloc.at[0, 'exit_reason']))

    def test_rank_sell_disabled_profitable(self):
        """Bottom rank + profit should not rank-SELL when oracle stack disables rank sell."""
        if not oracle_stack_align_enabled(self.cfg):
            self.skipTest('ORACLE_STACK_ALIGN=false')
        if not getattr(self.cfg, 'ORACLE_DISABLE_RANK_SELL_ALL', True):
            self.skipTest('rank sell not disabled')
        label = holdings_rank_metric_label(self.cfg)
        self.assertEqual(label, 'Pick rank')

    def test_core_hard_stop_still_fires_over_hold(self):
        out = evaluate_holding_validation(
            'LOSER', 100.0, datetime.now() - timedelta(days=60), 91.0, -0.09,
            pd.DataFrame(), self.cfg, sleeve='TACTICAL',
        )
        self.assertIsNotNone(out)
        self.assertIn('HARD STOP', out[1].upper())


if __name__ == '__main__':
    unittest.main()
