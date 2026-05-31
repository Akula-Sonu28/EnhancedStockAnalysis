"""Unit tests for VMQ (Validated Momentum-Quality) strategy gates."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import get_config
from src.vmq_strategy import (
    apply_vmq_to_allocation_df,
    count_new_positions_this_week,
    day3_validation_active,
    evaluate_entry_gate,
    evaluate_holding_validation,
    get_entry_info,
    is_value_trap,
    should_skip_day3_validation,
)


def _day3_enabled_cfg(**overrides):
    """Test helper: enable day-3/5 with bear-only regime gate (production default is off)."""
    base = get_config()
    class C:
        VMQ_DAY3_ENABLED = True
        VMQ_DAY3_REGIME_GATED = getattr(base, 'VMQ_DAY3_REGIME_GATED', True)
        VMQ_DAY3_ACTIVE_REGIMES = getattr(base, 'VMQ_DAY3_ACTIVE_REGIMES', 'bear,high_vol')
        VMQ_DAY3_VIX_MIN = getattr(base, 'VMQ_DAY3_VIX_MIN', 25.0)
        VMQ_DAY3_SMART_SKIP = getattr(base, 'VMQ_DAY3_SMART_SKIP', True)
        VMQ_DAY3_SKIP_PNL_MIN = getattr(base, 'VMQ_DAY3_SKIP_PNL_MIN', 5.0)
        VMQ_DAY3_SKIP_MTF_MIN = getattr(base, 'VMQ_DAY3_SKIP_MTF_MIN', 52.0)
        VMQ_VALIDATION_FAIL_3D = getattr(base, 'VMQ_VALIDATION_FAIL_3D', -2.0)
        VMQ_VALIDATION_FAIL_5D = getattr(base, 'VMQ_VALIDATION_FAIL_5D', 0.0)
        VMQ_SWING_STOP_PCT = getattr(base, 'VMQ_SWING_STOP_PCT', -5.0)
        VMQ_HARD_STOP_PCT = getattr(base, 'VMQ_HARD_STOP_PCT', -8.0)
        VMQ_TRAIL_STOP_PCT = getattr(base, 'VMQ_TRAIL_STOP_PCT', 0.08)
        VMQ_ENABLED = True
        VMQ_TURBO_MIN = getattr(base, 'VMQ_TURBO_MIN', 65.0)
    for k, v in overrides.items():
        setattr(C, k, v)
    return C()


class TestVMQEntryGate(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_value_trap_detects_gpil_pattern(self):
        self.assertTrue(is_value_trap(82.0, 48.0, self.cfg))

    def test_blocks_low_score_when_v1_floor_enabled(self):
        class C:
            VMQ_ENTRY_SCORE_MIN = 70.0
            VMQ_ENTRY_MOM_FLOOR = 45.0
            VMQ_VALUE_TRAP_FUND_MIN = 75.0
            VMQ_VALUE_TRAP_MOM_MAX = 55.0
            VMQ_V1_V2_GAP_MAX = 15.0
            VMQ_MAX_NEW_PER_WEEK = 3
            VMQ_REQUIRE_V2_BUY = False
            VMQ_REQUIRE_TURBO_PASS = False
            VMQ_TURBO_MIN = 65.0
            VMQ_ENABLED = True
        row = {
            'final_blended_score': 62.0,
            'hybrid_overall_score_v2': 55.0,
            'hybrid_momentum_technical': 48.0,
            'hybrid_fundamental_quality': 78.0,
        }
        result = evaluate_entry_gate(row, C())
        self.assertFalse(result.allowed)

    def test_allows_low_v1_score_when_oracle_floor_zero(self):
        row = {
            'final_blended_score': 62.0,
            'hybrid_overall_score_v2': 55.0,
            'hybrid_momentum_technical': 72.0,
            'hybrid_fundamental_quality': 65.0,
            'turbo_score': 70.0,
        }
        result = evaluate_entry_gate(row, self.cfg, new_this_week=0)
        self.assertTrue(result.allowed)

    def test_uses_hybrid_overall_when_blended_missing(self):
        class C:
            VMQ_ENTRY_SCORE_MIN = 70.0
            VMQ_ENTRY_MOM_FLOOR = 45.0
            VMQ_VALUE_TRAP_FUND_MIN = 75.0
            VMQ_VALUE_TRAP_MOM_MAX = 55.0
            VMQ_V1_V2_GAP_MAX = 15.0
            VMQ_MAX_NEW_PER_WEEK = 3
            VMQ_REQUIRE_V2_BUY = False
            VMQ_REQUIRE_TURBO_PASS = False
            VMQ_TURBO_MIN = 65.0
            VMQ_ENABLED = True
        row = {
            'hybrid_overall_score': 68.0,
            'hybrid_overall_score_v2': 65.0,
            'hybrid_momentum_technical': 72.0,
            'hybrid_fundamental_quality': 65.0,
        }
        result = evaluate_entry_gate(row, C(), new_this_week=0)
        self.assertFalse(result.allowed)  # score 68 < 70
        self.assertFalse(any('0.0<' in r for r in result.reasons))

    def test_allows_strong_momentum_entry(self):
        row = {
            'final_blended_score': 75.0,
            'hybrid_overall_score_v2': 68.0,
            'hybrid_momentum_technical': 72.0,
            'hybrid_fundamental_quality': 65.0,
        }
        result = evaluate_entry_gate(row, self.cfg, new_this_week=0)
        self.assertTrue(result.allowed)


class TestVMQHoldingValidation(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()
        self.day3_cfg = _day3_enabled_cfg()

    def test_day5_fail_recent_loser(self):
        entry = datetime.now() - timedelta(days=10)
        hist = pd.DataFrame([
            {'symbol': 'GESHIP', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'GESHIP', 'date': entry + timedelta(days=5), 'price': 98.5, 'action': 'HOLD'},
        ])
        out = evaluate_holding_validation(
            'GESHIP', 100.0, entry, 98.5, -0.015, hist, self.day3_cfg, sleeve='TACTICAL',
            market_regime='BEAR',
        )
        self.assertIsNotNone(out)
        self.assertIn('DAY-5', out[1])

    def test_day5_skipped_in_bull_when_regime_gated(self):
        entry = datetime.now() - timedelta(days=10)
        hist = pd.DataFrame([
            {'symbol': 'GESHIP', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'GESHIP', 'date': entry + timedelta(days=5), 'price': 98.5, 'action': 'HOLD'},
        ])
        out = evaluate_holding_validation(
            'GESHIP', 100.0, entry, 98.5, -0.015, hist, self.day3_cfg, sleeve='TACTICAL',
            market_regime='BULL',
        )
        self.assertIsNone(out)

    def test_skips_day3_when_recovered_profit(self):
        entry = datetime.now() - timedelta(days=10)
        hist = pd.DataFrame([
            {'symbol': 'ENRIN', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'ENRIN', 'date': entry + timedelta(days=3), 'price': 97.8, 'action': 'HOLD'},
            {'symbol': 'ENRIN', 'date': datetime.now(), 'price': 106.0, 'action': 'HOLD'},
        ])
        out = evaluate_holding_validation(
            'ENRIN', 100.0, entry, 106.0, 0.056, hist, self.day3_cfg, sleeve='TACTICAL',
        )
        self.assertIsNone(out)

    def test_no_day3_without_entry_date(self):
        out = evaluate_holding_validation(
            'BAJAJHLDNG', 100.0, None, 95.0, -0.05,
            pd.DataFrame(), self.cfg, sleeve='CORE',
        )
        self.assertIsNone(out)

    def test_core_skips_swing_stop(self):
        out = evaluate_holding_validation(
            'CORE1', 100.0, datetime.now() - timedelta(days=60), 94.0, -0.06,
            pd.DataFrame(), self.cfg, sleeve='CORE',
        )
        self.assertIsNone(out)

    def test_core_hard_stop_still_fires(self):
        out = evaluate_holding_validation(
            'GESHIP', 100.0, datetime.now() - timedelta(days=60), 85.0, -0.15,
            pd.DataFrame(), self.cfg, sleeve='CORE',
        )
        self.assertIsNotNone(out)
        self.assertIn('HARD STOP', out[1])

    def test_day5_skipped_when_turbo_pass(self):
        entry = datetime.now() - timedelta(days=10)
        hist = pd.DataFrame([
            {'symbol': 'GESHIP', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'GESHIP', 'date': entry + timedelta(days=5), 'price': 98.5, 'action': 'HOLD'},
        ])
        out = evaluate_holding_validation(
            'GESHIP', 100.0, entry, 98.5, -0.015, hist, self.day3_cfg, sleeve='TACTICAL',
            market_regime='BEAR', turbo_score=72.0,
        )
        self.assertIsNone(out)

    def test_day5_skipped_when_mtf_intact(self):
        entry = datetime.now() - timedelta(days=10)
        hist = pd.DataFrame([
            {'symbol': 'GESHIP', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'GESHIP', 'date': entry + timedelta(days=5), 'price': 98.5, 'action': 'HOLD'},
        ])
        out = evaluate_holding_validation(
            'GESHIP', 100.0, entry, 98.5, -0.015, hist, self.day3_cfg, sleeve='TACTICAL',
            market_regime='BEAR', mtf_score=55.0,
        )
        self.assertIsNone(out)

    def test_day5_fires_on_small_profit_without_skip_signals(self):
        entry = datetime.now() - timedelta(days=10)
        hist = pd.DataFrame([
            {'symbol': 'GESHIP', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'GESHIP', 'date': entry + timedelta(days=5), 'price': 98.5, 'action': 'HOLD'},
        ])
        out = evaluate_holding_validation(
            'GESHIP', 100.0, entry, 102.0, 0.02, hist, self.day3_cfg, sleeve='TACTICAL',
            market_regime='BEAR', turbo_score=50.0, mtf_score=45.0,
        )
        self.assertIsNotNone(out)
        self.assertIn('DAY-5', out[1])

    def test_production_day3_disabled_by_default(self):
        cfg = get_config()
        self.assertFalse(getattr(cfg, 'VMQ_DAY3_ENABLED', True))
        entry = datetime.now() - timedelta(days=10)
        hist = pd.DataFrame([
            {'symbol': 'GESHIP', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'GESHIP', 'date': entry + timedelta(days=5), 'price': 98.5, 'action': 'HOLD'},
        ])
        out = evaluate_holding_validation(
            'GESHIP', 100.0, entry, 98.5, -0.015, hist, cfg, sleeve='TACTICAL',
            market_regime='BEAR',
        )
        self.assertIsNone(out)

    def test_should_skip_day3_validation_profit_threshold(self):
        skip, reason = should_skip_day3_validation(6.0, self.cfg)
        self.assertTrue(skip)
        self.assertIn('pnl', reason)
        skip2, _ = should_skip_day3_validation(2.0, self.cfg)
        self.assertFalse(skip2)

    def test_get_entry_info_uses_latest_new_position(self):
        hist = pd.DataFrame([
            {'symbol': 'X', 'date': '2026-05-01', 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'X', 'date': '2026-05-20', 'price': 200.0, 'action': 'NEW POSITION'},
        ])
        _, ep = get_entry_info('X', hist)
        self.assertEqual(ep, 200.0)


class TestVMQDay3RegimeGate(unittest.TestCase):
    def test_production_master_switch_off(self):
        cfg = get_config()
        self.assertFalse(day3_validation_active('BEAR', cfg=cfg))
        self.assertFalse(day3_validation_active('BULL', vix_level=30.0, cfg=cfg))

    def test_active_in_bear_not_sideways(self):
        cfg = _day3_enabled_cfg()
        self.assertTrue(day3_validation_active('BEAR', cfg=cfg))
        self.assertFalse(day3_validation_active('SIDEWAYS', cfg=cfg))

    def test_inactive_in_bull_when_gated(self):
        cfg = _day3_enabled_cfg()
        if getattr(cfg, 'VMQ_DAY3_REGIME_GATED', True):
            self.assertFalse(day3_validation_active('BULL', cfg=cfg))

    def test_high_vix_triggers_when_configured(self):
        cfg = _day3_enabled_cfg()
        self.assertTrue(day3_validation_active('BULL', vix_level=30.0, cfg=cfg))

    def test_ungated_always_active(self):
        class C:
            VMQ_DAY3_ENABLED = True
            VMQ_DAY3_REGIME_GATED = False
        self.assertTrue(day3_validation_active('BULL', cfg=C()))


class TestVMQAllocationApply(unittest.TestCase):
    def setUp(self):
        self.cfg = get_config()

    def test_apply_blocks_new_and_caps_exits(self):
        alloc = pd.DataFrame([
            {
                'symbol': 'BADNEW',
                'is_current_holding': False,
                'action_recommendation': 'NEW POSITION',
                'action_type': 'NEW POSITION',
                'final_blended_score': 60.0,
                'hybrid_overall_score_v2': 50.0,
                'hybrid_momentum_technical': 42.0,
                'hybrid_fundamental_quality': 80.0,
                'investment_amount': 5000,
                'suggested_quantity': 10,
            },
            {
                'symbol': 'LOSER1',
                'is_current_holding': True,
                'action_recommendation': 'HOLD',
                'avg_cost': 100.0,
                'current_price': 90.0,
                'current_profit_pct': -0.10,
                'sleeve': 'TACTICAL',
            },
            {
                'symbol': 'LOSER2',
                'is_current_holding': True,
                'action_recommendation': 'HOLD',
                'avg_cost': 100.0,
                'current_price': 94.0,
                'current_profit_pct': -0.06,
                'sleeve': 'TACTICAL',
            },
        ])
        entry = datetime.now() - timedelta(days=8)
        hist = pd.DataFrame([
            {'symbol': 'LOSER1', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
            {'symbol': 'LOSER2', 'date': entry, 'price': 100.0, 'action': 'NEW POSITION'},
        ])
        stats = apply_vmq_to_allocation_df(alloc, hist, self.cfg)
        self.assertEqual(stats['entry_blocked'], 1)
        self.assertEqual(alloc.loc[0, 'action_recommendation'], 'WATCHLIST')
        self.assertGreaterEqual(stats['exit_forced'], 1)
        self.assertGreaterEqual(stats.get('exit_capped', 0), 0)


if __name__ == '__main__':
    unittest.main()
