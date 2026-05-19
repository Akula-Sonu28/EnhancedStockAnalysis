"""Unit tests for the executor: T+1 fills, slippage, signed cash deltas."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backtest.execution import Executor, ExecutionError  # noqa: E402


def _open_lookup_fixed(price: float):
    def _l(_sym: str, _after: date):
        return price
    return _l


def _mcap_fixed(mc: float | None = 20_000):
    def _f(_sym: str):
        return mc
    return _f


class TestExecutor(unittest.TestCase):

    def test_buy_decreases_cash(self):
        ex = Executor(next_day_open=_open_lookup_fixed(100.0),
                      market_cap_crores=_mcap_fixed(20_000))
        f = ex.submit(symbol='X', side='BUY', qty=100,
                      decision_date=date(2026, 5, 1),
                      fill_date=date(2026, 5, 2))
        self.assertEqual(f.side, 'BUY')
        # Slippage = mid tier (20 bps) on 100 -> fill 100.20
        self.assertAlmostEqual(f.fill_price, 100.20, places=2)
        # Cash delta is negative for BUY (we pay) and includes charges.
        self.assertLess(f.cash_delta, -10_020)  # turnover + something for STT etc

    def test_sell_increases_cash(self):
        ex = Executor(next_day_open=_open_lookup_fixed(100.0),
                      market_cap_crores=_mcap_fixed(20_000))
        f = ex.submit(symbol='X', side='SELL', qty=100,
                      decision_date=date(2026, 5, 1),
                      fill_date=date(2026, 5, 2))
        self.assertEqual(f.side, 'SELL')
        self.assertAlmostEqual(f.fill_price, 99.80, places=2)
        self.assertGreater(f.cash_delta, 0)

    def test_missing_price_raises(self):
        ex = Executor(next_day_open=lambda s, d: None,
                      market_cap_crores=_mcap_fixed())
        with self.assertRaises(ExecutionError):
            ex.submit(symbol='X', side='BUY', qty=10,
                      decision_date=date(2026, 5, 1),
                      fill_date=date(2026, 5, 2))

    def test_invalid_side(self):
        ex = Executor(next_day_open=_open_lookup_fixed(100.0),
                      market_cap_crores=_mcap_fixed())
        with self.assertRaises(ExecutionError):
            ex.submit(symbol='X', side='HOLD', qty=10,
                      decision_date=date(2026, 5, 1),
                      fill_date=date(2026, 5, 2))

    def test_zero_qty_raises(self):
        ex = Executor(next_day_open=_open_lookup_fixed(100.0),
                      market_cap_crores=_mcap_fixed())
        with self.assertRaises(ExecutionError):
            ex.submit(symbol='X', side='BUY', qty=0,
                      decision_date=date(2026, 5, 1),
                      fill_date=date(2026, 5, 2))


if __name__ == '__main__':
    unittest.main()
