#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


class TestUpstoxData(unittest.TestCase):
    def test_enabled_flag(self):
        import os
        from src import upstox_data as ud

        os.environ["UPSTOX_DATA_ENABLED"] = "true"
        self.assertTrue(ud.upstox_data_enabled())
        os.environ.pop("UPSTOX_DATA_ENABLED", None)
        self.assertFalse(ud.upstox_data_enabled())

    @patch("src.upstox_data.requests.get")
    def test_historical_parses_candles(self, mock_get):
        import tempfile
        from src import upstox_data as ud

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = tmp
            inst_path = ud._cache_path(data_dir)
            inst_path.parent.mkdir(parents=True, exist_ok=True)
            inst_path.write_text(
                json.dumps({"RELIANCE": "NSE_EQ|INE002A01018"}), encoding="utf-8"
            )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "success",
            "data": {
                "candles": [
                    ["2026-05-01T00:00:00+05:30", 100, 105, 99, 104, 1000, 0],
                    ["2026-05-02T00:00:00+05:30", 104, 106, 103, 105, 1100, 0],
                ]
            }
        }
        mock_get.return_value = mock_resp

            with patch.dict("os.environ", {"UPSTOX_ACCESS_TOKEN": "test-token"}):
                df = ud.fetch_historical_ohlcv(
                    "RELIANCE", period="1mo", data_dir=data_dir
                )
            self.assertIsNotNone(df)
            self.assertEqual(len(df), 2)
            self.assertIn("Close", df.columns)


if __name__ == "__main__":
    unittest.main()
