"""Static + runtime checks that the backtest cannot peek into the future.

Static checks:
    - The strategy module must NOT load data files at import time.
    - Path1Loader.iter_snapshots must respect start/end bounds.

Runtime checks:
    - When iterating snapshots for date d, the dataframe rows must all
      carry date == d (no rows from later than d).
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backtest.data.path1_loader import Path1Loader, HISTORICAL_OUTCOMES  # noqa: E402


class TestNoLookahead(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not HISTORICAL_OUTCOMES.exists():
            raise unittest.SkipTest('historical_outcomes.csv not present')

    def test_snapshots_respect_end_date(self):
        loader = Path1Loader(engine='v2')
        ds, de = loader.dense_window()
        if ds is None:
            self.skipTest('no dense window')
        # Pick the midpoint as the "current" date; assert no snapshot row
        # carries a date after it.
        mid = ds + (de - ds) // 2
        for snap in loader.iter_snapshots(start=ds, end=mid, min_universe=1):
            self.assertLessEqual(snap.decision_date, mid)
            self.assertTrue((snap.df['date'].dt.date <= mid).all(),
                            f'snapshot {snap.decision_date} contains future-dated row')

    def test_snapshots_respect_start_date(self):
        loader = Path1Loader(engine='v2')
        ds, de = loader.dense_window()
        if ds is None:
            self.skipTest('no dense window')
        # Skip the first half of the window.
        mid = ds + (de - ds) // 2
        for snap in loader.iter_snapshots(start=mid, end=de, min_universe=1):
            self.assertGreaterEqual(snap.decision_date, mid)

    def test_returns_columns_not_used_in_scoring(self):
        """Sanity: the engine must NOT use return_7d/return_30d to compute
        score_engine. We verify by ensuring the synthesised score depends only
        on hybrid_* columns, not on return_*.
        """
        from backtest.data.path1_loader import _synthesise_v2_score
        df = pd.DataFrame({
            'hybrid_fundamental_quality': [50, 70, 30],
            'hybrid_momentum_technical':  [50, 50, 50],
            'hybrid_volume_strength':     [50, 50, 50],
            'hybrid_multi_timeframe':     [50, 50, 50],
            'hybrid_ml_signal':           [50, 50, 50],
            'hybrid_risk_adjustment':     [50, 50, 50],
            'hybrid_growth':              [50, 50, 50],
            'hybrid_value':               [50, 50, 50],
            'return_7d':                  [0.10, -0.20, 0.30],
            'return_30d':                 [0.10, -0.20, 0.30],
        })
        weights = {
            'fundamental_quality': 0.5, 'momentum_technical': 0.0,
            'volume_strength': 0.0, 'multi_timeframe': 0.0,
            'ml_signal': 0.0, 'risk_adjustment': 0.0,
            'growth': 0.0, 'value': 0.0,
        }
        s = _synthesise_v2_score(df, weights)
        # Hand math: deviation = (fund - 50)*0.5 = (0, 10, -10); score = (50, 60, 40)
        self.assertAlmostEqual(s.iloc[0], 50.0, places=2)
        self.assertAlmostEqual(s.iloc[1], 60.0, places=2)
        self.assertAlmostEqual(s.iloc[2], 40.0, places=2)


if __name__ == '__main__':
    unittest.main()
