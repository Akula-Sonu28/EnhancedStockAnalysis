"""Unit tests for the Indian cost model.

Anchor values come from Zerodha's published Equity Delivery charges
calculator (zerodha.com/charges/). We test typical retail trade sizes.
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backtest.costs import (  # noqa: E402
    DEFAULT_COST, DEFAULT_SLIPPAGE,
    charges_for_leg, apply_slippage,
    is_long_term, realized_gain, stcg_on, ltcg_on, indian_fy_of,
)


class TestChargesPerLeg(unittest.TestCase):

    def test_buy_leg_25k_typical(self):
        """₹25,000 turnover BUY leg — small retail trade."""
        ch = charges_for_leg(25_000, 'BUY')
        # brokerage = 0 (delivery is free)
        self.assertEqual(ch['brokerage'], 0.0)
        # STT 0.1% = ₹25
        self.assertAlmostEqual(ch['stt'], 25.0, places=2)
        # Stamp duty 0.015% on BUY = ₹3.75
        self.assertAlmostEqual(ch['stamp_duty'], 3.75, places=2)
        # SEBI ₹10/crore = ₹0.025
        self.assertAlmostEqual(ch['sebi'], 0.025, places=4)
        # All totals must be non-negative
        self.assertGreater(ch['total'], 0)

    def test_sell_leg_25k_no_stamp(self):
        """SELL leg pays no stamp duty."""
        ch = charges_for_leg(25_000, 'SELL')
        self.assertEqual(ch['stamp_duty'], 0.0)
        self.assertAlmostEqual(ch['stt'], 25.0, places=2)

    def test_zero_turnover_returns_zero(self):
        ch = charges_for_leg(0, 'BUY')
        self.assertEqual(ch['total'], 0.0)

    def test_invalid_side(self):
        with self.assertRaises(ValueError):
            charges_for_leg(1000, 'HOLD')

    def test_stamp_duty_cap(self):
        """Stamp duty caps at ₹1500 per contract (extreme size)."""
        # ₹1cr turnover would otherwise be 0.015% * 1cr = ₹1500 (exactly at cap)
        # ₹2cr exceeds cap.
        ch = charges_for_leg(2_00_00_000, 'BUY')  # ₹2 crore
        self.assertEqual(ch['stamp_duty'], 1500.0)

    def test_gst_only_on_brokerage_exchange_sebi(self):
        """GST = 18% * (brokerage + exchange + SEBI). STT/stamp NOT taxed."""
        ch = charges_for_leg(1_00_000, 'BUY')
        expected_gst = 0.18 * (ch['brokerage'] + ch['exchange'] + ch['sebi'])
        self.assertAlmostEqual(ch['gst'], expected_gst, places=4)


class TestSlippage(unittest.TestCase):

    def test_buy_pays_more(self):
        out = apply_slippage(100.0, 'BUY', 25.0)  # 25 bps
        self.assertAlmostEqual(out, 100.0 * 1.0025, places=4)

    def test_sell_receives_less(self):
        out = apply_slippage(100.0, 'SELL', 25.0)
        self.assertAlmostEqual(out, 100.0 * 0.9975, places=4)

    def test_zero_bps_no_change(self):
        self.assertEqual(apply_slippage(100.0, 'BUY', 0.0), 100.0)

    def test_zero_price_passthrough(self):
        self.assertEqual(apply_slippage(0, 'BUY', 25.0), 0)

    def test_bps_tier_by_market_cap(self):
        s = DEFAULT_SLIPPAGE
        self.assertEqual(s.bps_for_market_cap(100_000), s.bps_large)
        self.assertEqual(s.bps_for_market_cap(20_000), s.bps_mid)
        self.assertEqual(s.bps_for_market_cap(5_000), s.bps_small)
        self.assertEqual(s.bps_for_market_cap(1_000), s.bps_micro)
        self.assertEqual(s.bps_for_market_cap(None), s.bps_mid)


class TestCapitalGains(unittest.TestCase):

    def test_long_term_threshold(self):
        self.assertFalse(is_long_term(date(2025, 1, 1), date(2025, 6, 30)))
        self.assertTrue(is_long_term(date(2025, 1, 1), date(2026, 1, 1)))

    def test_stcg_20pct(self):
        # Budget 2024 raised STCG on equity to 20% (effective 2024-07-23).
        self.assertAlmostEqual(stcg_on(10_000), 2000.0, places=2)
        self.assertEqual(stcg_on(-5000), 0.0)

    def test_ltcg_below_exemption(self):
        # First ₹1L of LTCG is exempt
        tax, running = ltcg_on(50_000, 0.0)
        self.assertEqual(tax, 0.0)
        self.assertEqual(running, 50_000)

    def test_ltcg_above_exemption(self):
        tax, running = ltcg_on(200_000, 0.0)  # ₹2L gain in fresh FY
        # ₹1L is exempt, ₹1L is taxed @10% = ₹10,000
        self.assertAlmostEqual(tax, 10_000.0, places=2)
        self.assertEqual(running, 200_000)

    def test_ltcg_partial_exemption_use(self):
        # Already realized ₹80k LTCG this FY; new trade adds ₹50k.
        # Total ₹130k → ₹30k taxable; previous taxable was 0; tax on ₹30k.
        tax, running = ltcg_on(50_000, 80_000)
        self.assertAlmostEqual(tax, 3000.0, places=2)
        self.assertEqual(running, 130_000)

    def test_ltcg_loss_zero(self):
        tax, running = ltcg_on(-5000, 0.0)
        self.assertEqual(tax, 0.0)
        self.assertEqual(running, 0.0)

    def test_indian_fy_after_april(self):
        s, e = indian_fy_of(date(2026, 6, 1))
        self.assertEqual(s, date(2026, 4, 1))
        self.assertEqual(e, date(2027, 3, 31))

    def test_indian_fy_before_april(self):
        s, e = indian_fy_of(date(2026, 2, 14))
        self.assertEqual(s, date(2025, 4, 1))
        self.assertEqual(e, date(2026, 3, 31))


if __name__ == '__main__':
    unittest.main()
