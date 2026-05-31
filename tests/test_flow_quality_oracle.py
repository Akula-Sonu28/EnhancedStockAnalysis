#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.flow_quality_oracle import (
    adaptive_momentum_lambda,
    build_entry_watchlist_mask,
    compute_flow_quality_score,
    oracle_pause_new_entries,
)
from src.turbo_entry import compute_turbo_score, compute_turbo_score_v2_reference


class TestFlowQualityOracle(unittest.TestCase):
    def test_flow_quality_penalizes_momentum(self):
        high_mom = compute_flow_quality_score(70, 90, lam=0.5)
        low_mom = compute_flow_quality_score(70, 40, lam=0.5)
        self.assertGreater(low_mom, high_mom)

    def test_adaptive_lambda_tiers(self):
        self.assertEqual(adaptive_momentum_lambda(40), 0.3)
        self.assertEqual(adaptive_momentum_lambda(55), 0.5)
        self.assertEqual(adaptive_momentum_lambda(80), 0.8)

    def test_watchlist_top_pct(self):
        df = pd.DataFrame({
            'hybrid_volume_strength': [90, 50, 10, 80, 60],
            'hybrid_momentum_technical': [50, 50, 50, 50, 50],
        })
        mask = build_entry_watchlist_mask(df)
        self.assertGreaterEqual(int(mask.sum()), 1)
        self.assertLessEqual(int(mask.sum()), 2)

    def test_turbo_does_not_alias_v2(self):
        row = {
            'hybrid_overall_score_v2': 88.0,
            'score_v2': 88.0,
            'hybrid_volume_strength': 55,
            'hybrid_momentum_technical': 45,
            'hybrid_multi_timeframe': 70,
            'hybrid_fundamental_quality': 50,
            'hybrid_risk_adjustment': 50,
        }
        ref = compute_turbo_score_v2_reference(row)
        turbo = compute_turbo_score(row)
        self.assertEqual(ref, 88.0)
        self.assertNotEqual(turbo, 88.0)

    def test_pause_when_entry_not_live(self):
        class C:
            ORACLE_ENTRY_LIVE = False
            ORACLE_PAUSE_NEW_ON_HOLD_SHADOW = False
            DATA_DIR = 'data'
        paused, reason = oracle_pause_new_entries(C())
        self.assertTrue(paused)
        self.assertIn('ENTRY_LIVE', reason.upper())

    def test_v2_shadow_does_not_pause_when_hold_shadow_off(self):
        class C:
            V2_SHADOW_MODE = True
            ORACLE_ENTRY_LIVE = True
            ORACLE_PAUSE_NEW_ON_HOLD_SHADOW = False
            ORACLE_PAUSE_NEW_IN_BEAR = False
            DATA_DIR = 'data'
        paused, _ = oracle_pause_new_entries(C())
        self.assertFalse(paused)

    def test_pauses_new_on_escalate_tier_c_when_enabled(self):
        class C:
            ORACLE_ENTRY_LIVE = True
            ORACLE_PAUSE_NEW_ON_HOLD_SHADOW = True
            ORACLE_PAUSE_NEW_IN_BEAR = False
            DATA_DIR = 'data'
        paused, reason = oracle_pause_new_entries(C(), walkforward_verdict='ESCALATE_TIER_C')
        self.assertTrue(paused)
        self.assertIn('ESCALATE', reason.upper())


if __name__ == '__main__':
    unittest.main()
