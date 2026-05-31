"""Tests for QMST pick-layer quality gates."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import get_config
from src.qmst_pick_gates import evaluate_pick_gates, pick_gates_enabled


class TestQmstPickGates(unittest.TestCase):
    def test_off_by_default(self):
        cfg = get_config()
        self.assertFalse(pick_gates_enabled(cfg))
        row = {'hybrid_fundamental_quality': 30.0, 'hybrid_risk_adjustment': 30.0}
        result = evaluate_pick_gates(row, cfg)
        self.assertTrue(result.allowed)

    def test_blocks_low_fq_when_enabled(self):
        class C:
            QMST_PICK_GATES_ENABLED = True
            QMST_PICK_FQ_MIN = 48.0
            QMST_PICK_RK_MIN = 42.0
            QMST_PICK_VL_GATE = False
            QMST_PICK_VL_MIN = 45.0

        row = {'hybrid_fundamental_quality': 40.0, 'hybrid_risk_adjustment': 50.0}
        result = evaluate_pick_gates(row, C())
        self.assertFalse(result.allowed)
        self.assertTrue(any('FQ' in r for r in result.reasons))

    def test_blocks_low_rk_when_enabled(self):
        class C:
            QMST_PICK_GATES_ENABLED = True
            QMST_PICK_FQ_MIN = 48.0
            QMST_PICK_RK_MIN = 42.0
            QMST_PICK_VL_GATE = False

        row = {'hybrid_fundamental_quality': 55.0, 'hybrid_risk_adjustment': 35.0}
        result = evaluate_pick_gates(row, C())
        self.assertFalse(result.allowed)
        self.assertTrue(any('RK' in r for r in result.reasons))

    def test_passes_strong_row_when_enabled(self):
        class C:
            QMST_PICK_GATES_ENABLED = True
            QMST_PICK_FQ_MIN = 48.0
            QMST_PICK_RK_MIN = 42.0
            QMST_PICK_VL_GATE = False

        row = {'hybrid_fundamental_quality': 60.0, 'hybrid_risk_adjustment': 50.0}
        result = evaluate_pick_gates(row, C())
        self.assertTrue(result.allowed)

    def test_vl_gate_optional(self):
        class C:
            QMST_PICK_GATES_ENABLED = True
            QMST_PICK_FQ_MIN = 48.0
            QMST_PICK_RK_MIN = 42.0
            QMST_PICK_VL_GATE = True
            QMST_PICK_VL_MIN = 45.0

        row = {
            'hybrid_fundamental_quality': 60.0,
            'hybrid_risk_adjustment': 50.0,
            'hybrid_value': 30.0,
        }
        result = evaluate_pick_gates(row, C())
        self.assertFalse(result.allowed)
        self.assertTrue(any('VL' in r for r in result.reasons))


if __name__ == '__main__':
    unittest.main()
