"""QMST backtest loader and strategy smoke tests."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backtest.data.qmst_loader import QmstLoader
from backtest.qmst_strategy import QMSTStrategyAdapter


class TestQmstLoader(unittest.TestCase):
    def test_iter_snapshots_adds_oracle_columns(self):
        loader = QmstLoader()
        snaps = list(loader.iter_snapshots(min_universe=20))
        if not snaps:
            self.skipTest('no dense snapshots in historical_outcomes.csv')
        snap = snaps[0]
        for col in (
            'fq_score', 'picking_rank', 'turbo_score',
            'on_oracle_watchlist', 'turbo_pass', 'score_engine',
        ):
            self.assertIn(col, snap.df.columns, msg=col)
        self.assertTrue((snap.df['score_engine'] == snap.df['fq_score']).all())
        self.assertGreaterEqual(int(snap.df['on_oracle_watchlist'].sum()), 1)

    def test_watchlist_is_top_pct(self):
        loader = QmstLoader()
        snaps = list(loader.iter_snapshots(min_universe=20))
        if not snaps:
            self.skipTest('no dense snapshots')
        snap = snaps[-1]
        n = len(snap.df)
        wl = int(snap.df['on_oracle_watchlist'].sum())
        self.assertGreaterEqual(wl, max(1, int(n * 0.15)))
        self.assertLessEqual(wl, max(1, int(n * 0.25)))


class TestQmstStrategy(unittest.TestCase):
    def test_vmq_hard_stop_fires(self):
        strat = QMSTStrategyAdapter()
        dec = strat.check_open_position(
            score=-10.0,
            profit_pct=-0.10,
            current_price=90.0,
            entry_price=100.0,
            symbol='TEST',
            entry_date=date(2026, 3, 1),
        )
        self.assertEqual(dec.action, 'SELL')
        self.assertIn('HARD STOP', dec.reason.upper())

    def test_turbo_blocks_weak_row(self):
        strat = QMSTStrategyAdapter()
        row = {
            'hybrid_momentum_technical': 40.0,
            'hybrid_multi_timeframe': 40.0,
            'hybrid_fundamental_quality': 80.0,
            'hybrid_volume_strength': 55.0,
            'final_blended_score': 60.0,
            'turbo_pass': False,
        }
        self.assertFalse(strat.entry_allowed(row))

    def test_default_include_day3_follows_config(self):
        from config import get_config
        cfg = get_config()
        strat = QMSTStrategyAdapter()
        self.assertEqual(strat.include_day3, bool(getattr(cfg, 'VMQ_DAY3_ENABLED', False)))


if __name__ == '__main__':
    unittest.main()
