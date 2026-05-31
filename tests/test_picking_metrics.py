#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.picking_metrics import (
    add_picking_rank_column,
    apply_oracle_stack_display_labels,
    backfill_allocation_from_results,
    classify_sell_category,
    enrich_results_df_oracle_stack,
    filter_rank_surface,
    format_holdings_reason,
    format_rank_metric_clause,
    oracle_stack_align_enabled,
    populate_sell_categories,
    quintile_spread,
    resolve_holdings_rank_score,
    resolve_validation_score,
    spearman_ic,
    synthesise_v2_score,
    SELL_CATEGORY_LABELS,
)


class TestPickingMetrics(unittest.TestCase):
    def test_filter_rank_surface_drops_exits(self):
        df = pd.DataFrame([
            {'action': 'HOLD', 'score': 60},
            {'action': 'SELL', 'score': 70},
            {'action': 'EXIT NOW - Heavy exhaustion', 'score': 80},
            {'action': 'NEW POSITION', 'score': 75},
        ])
        out = filter_rank_surface(df)
        self.assertEqual(len(out), 2)
        self.assertTrue(all('SELL' not in a and 'EXIT' not in a for a in out['action']))

    def test_filter_rank_surface_no_action_column(self):
        df = pd.DataFrame([{'score': 60}])
        self.assertEqual(len(filter_rank_surface(df)), 1)

    def test_synthesise_deviation_form(self):
        df = pd.DataFrame([{
            'hybrid_risk_adjustment': 100.0,
            'hybrid_fundamental_quality': 50.0,
        }])
        s = synthesise_v2_score(df, {'risk_adjustment': -0.5})
        self.assertAlmostEqual(float(s.iloc[0]), 25.0)

    def test_synthesise_nan_when_all_missing(self):
        df = pd.DataFrame([{'hybrid_risk_adjustment': np.nan}])
        s = synthesise_v2_score(df, {'risk_adjustment': -0.5})
        self.assertTrue(pd.isna(s.iloc[0]))

    def test_add_picking_rank_prefers_turbo(self):
        cfg = type('C', (), {
            'PICKING_RANK_DRIVER': 'turbo_mtf',
            'ENTRY_DRIVER': 'turbo_mtf',
            'DATA_DIR': 'data',
            'ORACLE_WATCHLIST_PCT': 0.2,
        })()
        df = pd.DataFrame([{
            'turbo_score': 88.0,
            'overall_score': 55.0,
            'final_blended_score': 60.0,
        }])
        out = add_picking_rank_column(df, cfg)
        self.assertAlmostEqual(float(out['picking_rank'].iloc[0]), 88.0)

    def test_spearman_ic_positive_monotone(self):
        score = pd.Series(np.linspace(40, 90, 50))
        ret = pd.Series(np.linspace(-5, 15, 50))
        rho, _, n = spearman_ic(score, ret)
        self.assertGreater(rho, 0.9)
        self.assertEqual(n, 50)

    def test_quintile_spread_positive(self):
        score = pd.Series(np.linspace(40, 90, 100))
        ret = pd.Series(np.linspace(-5, 15, 100))
        q5, q1, spread, n = quintile_spread(score, ret)
        self.assertGreater(spread, 0)
        self.assertGreater(q5, q1)

    def test_resolve_holdings_rank_uses_fq_when_aligned(self):
        cfg = type('C', (), {
            'ORACLE_STACK_ALIGN': True,
            'PICKING_RANK_DRIVER': 'flow_quality',
            'ENTRY_DRIVER': 'turbo_mtf',
            'DATA_DIR': 'data',
            'ORACLE_WATCHLIST_PCT': 0.2,
            'FQ_LAMBDA_DEFAULT': 0.5,
        })()
        row = {
            'overall_score': 80.0,
            'final_blended_score': 80.0,
            'hybrid_volume_strength': 70,
            'hybrid_momentum_technical': 40,
        }
        self.assertTrue(oracle_stack_align_enabled(cfg))
        rank_score = resolve_holdings_rank_score(row, cfg)
        self.assertAlmostEqual(rank_score, 58.0)  # fq_adapt: 70 - 0.3*40 (low mom tier)

    def test_enrich_results_df_oracle_stack_adds_picking_rank(self):
        cfg = type('C', (), {
            'ORACLE_STACK_ALIGN': True,
            'PICKING_RANK_DRIVER': 'flow_quality',
            'ENTRY_DRIVER': 'turbo_mtf',
            'DATA_DIR': 'data',
            'ORACLE_WATCHLIST_PCT': 0.2,
            'FQ_LAMBDA_DEFAULT': 0.5,
            'DUAL_STRATEGY_PROFILES': {'turbo_mtf': {'weights': {'momentum_technical': 0.5}}},
        })()
        df = pd.DataFrame([{
            'symbol': 'RELIANCE',
            'hybrid_volume_strength': 70,
            'hybrid_momentum_technical': 40,
            'hybrid_multi_timeframe': 55,
            'hybrid_fundamental_quality': 50,
            'hybrid_risk_adjustment': 50,
        }])
        out = enrich_results_df_oracle_stack(df, cfg)
        self.assertIn('picking_rank', out.columns)
        self.assertIn('fq_score', out.columns)
        self.assertIn('turbo_score', out.columns)
        self.assertIn('v1_audit_recommendation', out.columns)
        self.assertTrue(str(out.at[0, 'final_recommendation']).startswith('🎯') or
                        str(out.at[0, 'final_recommendation']).startswith('📋'))

    def test_apply_oracle_stack_display_labels(self):
        cfg = type('C', (), {'ORACLE_STACK_ALIGN': True, 'VMQ_TURBO_MIN': 65.0})()
        df = pd.DataFrame([
            {'on_oracle_watchlist': True, 'turbo_score': 70, 'phase2_recommendation': '🟢 BUY'},
            {'on_oracle_watchlist': False, 'turbo_score': 40, 'phase2_recommendation': '🔴 SELL'},
        ])
        out = apply_oracle_stack_display_labels(df, cfg)
        self.assertEqual(out.at[0, 'final_recommendation'], '🎯 ORACLE+TURBO POOL')
        self.assertEqual(out.at[1, 'final_recommendation'], '⚪ OUT OF ORACLE POOL')
        self.assertEqual(out.at[0, 'v1_audit_recommendation'], '🟢 BUY')

    def test_resolve_validation_score_uses_oracle_rank(self):
        cfg = type('C', (), {
            'ORACLE_STACK_ALIGN': True,
            'PICKING_RANK_DRIVER': 'flow_quality',
            'ENTRY_DRIVER': 'turbo_mtf',
            'FQ_LAMBDA_DEFAULT': 0.5,
            'FQ_LAMBDA_LOW': 0.3,
            'FQ_MOM_MID_THRESHOLD': 50.0,
            'FQ_MOM_HIGH_THRESHOLD': 65.0,
        })()
        row = {
            'final_blended_score': 80.0,
            'hybrid_volume_strength': 70,
            'hybrid_momentum_technical': 40,
        }
        self.assertAlmostEqual(resolve_validation_score(row, cfg), 58.0)

    def test_classify_sell_category_vmq_hard_stop(self):
        cat = classify_sell_category({
            'action_recommendation': 'SELL',
            'vmq_reason': 'VMQ HARD STOP: loss -9.0% <= -8%',
        })
        self.assertEqual(cat, 'VMQ_HARD_STOP')
        self.assertIn('VMQ hard stop', SELL_CATEGORY_LABELS[cat])

    def test_classify_sell_category_swap(self):
        self.assertEqual(
            classify_sell_category({'action_recommendation': 'SWAP -> AIAENG'}),
            'SWAP_ROTATION',
        )

    def test_backfill_allocation_sector_and_volatility(self):
        alloc = pd.DataFrame([{
            'symbol': 'RELIANCE',
            'sector': 'Unknown',
            'volatility': 0,
            'overall_score': np.nan,
        }])
        results = pd.DataFrame([{
            'symbol': 'RELIANCE',
            'sector': 'Energy',
            'volatility_6m': 28.5,
            'final_blended_score': 72.0,
        }])
        out = backfill_allocation_from_results(alloc, results)
        self.assertEqual(out.at[0, 'sector'], 'Energy')
        self.assertAlmostEqual(float(out.at[0, 'volatility']), 28.5)
        self.assertAlmostEqual(float(out.at[0, 'overall_score']), 72.0)

    def test_populate_sell_categories_column(self):
        df = pd.DataFrame([{
            'action_recommendation': 'SELL',
            'exit_reason': 'VMQ SWING STOP: loss -6.1% <= -5%',
        }])
        out = populate_sell_categories(df)
        self.assertEqual(out.at[0, 'sell_category'], 'VMQ_SWING_STOP')

    def test_format_holdings_reason_pick_rank_label(self):
        reason = format_holdings_reason(
            7, 19, -32.8, oracle_aligned=True, prefix='📊 HOLD STEADY',
        )
        self.assertIn('Pick rank: -32.8', reason)
        self.assertNotIn('Score:', reason)

    def test_format_rank_metric_clause(self):
        cfg = type('C', (), {'ORACLE_STACK_ALIGN': True, 'QMST_ENABLED': True})()
        self.assertEqual(format_rank_metric_clause(-32.8, cfg), 'Pick rank: -32.8')
        cfg_legacy = type('C', (), {'ORACLE_STACK_ALIGN': False, 'QMST_ENABLED': False})()
        self.assertEqual(format_rank_metric_clause(72.0, cfg_legacy), 'Score: 72.0')


if __name__ == '__main__':
    unittest.main()
