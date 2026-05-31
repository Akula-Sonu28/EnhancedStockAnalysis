#!/usr/bin/env python3
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.nse_flow_data import (
    build_flow_lookup,
    compute_nse_volume_strength,
    enrich_nse_flow_shadow_columns,
)


class TestNseFlowData(unittest.TestCase):
    def test_compute_nse_volume_strength(self):
        score = compute_nse_volume_strength(45.0, 200.0)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_build_flow_lookup(self):
        bhav = pd.DataFrame([
            {'SYMBOL': 'RELIANCE', 'DELIV_PER': 50.0, 'TURNOVER_LACS': 10000.0, 'CLOSE PRICE': 2500},
        ])
        lookup = build_flow_lookup(bhav)
        self.assertIn('RELIANCE', lookup)
        self.assertAlmostEqual(lookup['RELIANCE']['nse_delivery_pct'], 50.0)

    def test_enrich_shadow_columns_off_when_disabled(self):
        class C:
            ORACLE_USE_NSE_FLOW_SHADOW = False
        df = pd.DataFrame([{'symbol': 'RELIANCE'}])
        out = enrich_nse_flow_shadow_columns(df, C())
        self.assertNotIn('fq_score_nse', out.columns)

    @patch('src.nse_flow_data.load_bhavcopy')
    def test_enrich_shadow_columns(self, mock_load):
        mock_load.return_value = pd.read_csv(StringIO(
            "SYMBOL,SERIES,DELIV_PER,TURNOVER_LACS,CLOSE PRICE\n"
            "RELIANCE,EQ,55.0,5000.0,2500.0\n"
        ))
        class C:
            ORACLE_USE_NSE_FLOW_SHADOW = True
            FQ_LAMBDA_DEFAULT = 0.5
            FQ_LAMBDA_LOW = 0.3
            FQ_MOM_MID_THRESHOLD = 50.0
            FQ_MOM_HIGH_THRESHOLD = 65.0
        df = pd.DataFrame([{
            'symbol': 'RELIANCE',
            'hybrid_momentum_technical': 40,
        }])
        out = enrich_nse_flow_shadow_columns(df, C())
        self.assertEqual(out.at[0, 'nse_flow_status'], 'OK')
        self.assertIsNotNone(out.at[0, 'fq_score_nse'])


if __name__ == '__main__':
    unittest.main()
