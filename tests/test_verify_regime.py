"""Unit tests for scripts/verify_regime.py helpers (no network)."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_regime import _label_from_score, _vmq_day3_status


class TestVerifyRegimeHelpers(unittest.TestCase):
    def test_label_thresholds(self):
        self.assertEqual(_label_from_score(0.8), 'BULL')
        self.assertEqual(_label_from_score(-0.6), 'BEAR')
        self.assertEqual(_label_from_score(0.0), 'SIDEWAYS')

    def test_vmq_bull_off_when_gated(self):
        class C:
            VMQ_DAY3_ENABLED = True
            VMQ_DAY3_REGIME_GATED = True
            VMQ_DAY3_ACTIVE_REGIMES = 'bear,high_vol'
            VMQ_DAY3_VIX_MIN = 25.0

        vmq = _vmq_day3_status('BULL', 16.0, C())
        self.assertFalse(vmq['day3_validation_active'])

    def test_vmq_production_disabled_by_default(self):
        from config import get_config
        vmq = _vmq_day3_status('BEAR', 30.0, get_config())
        self.assertFalse(vmq['vmq_day3_enabled'])
        self.assertFalse(vmq['day3_validation_active'])

    def test_vmq_bear_on_when_enabled_and_gated(self):
        class C:
            VMQ_DAY3_ENABLED = True
            VMQ_DAY3_REGIME_GATED = True
            VMQ_DAY3_ACTIVE_REGIMES = 'bear,high_vol'
            VMQ_DAY3_VIX_MIN = 25.0

        vmq = _vmq_day3_status('BEAR', 16.0, C())
        self.assertTrue(vmq['day3_validation_active'])


if __name__ == '__main__':
    unittest.main()
