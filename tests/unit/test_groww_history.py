"""Unit tests for src.groww_history.

Mocks the growwapi SDK entirely; no network calls.
Run with: python3 -m unittest tests.unit.test_groww_history
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.groww_history import (  # noqa: E402
    GrowwHistoryClient,
    GrowwHistoryConfig,
    _candles_to_frame,
    fetch_and_cache_universe,
    load_cached,
    upsert_cache,
)


def _cfg(cache_dir: Path) -> GrowwHistoryConfig:
    return GrowwHistoryConfig(
        api_key="x",
        api_secret="y",
        cache_dir=cache_dir,
        request_delay_s=0.0,
        retry_attempts=2,
    )


def _fake_sdk_client() -> MagicMock:
    fake = MagicMock()
    fake.EXCHANGE_NSE = "NSE"
    fake.SEGMENT_CASH = "CASH"
    fake.CANDLE_INTERVAL_DAY = "1day"
    fake.get_historical_candles.return_value = {"candles": []}
    return fake


class GrowwHistoryConfigTests(unittest.TestCase):
    def test_from_env_requires_both_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved_key = os.environ.pop("GROWW_API_KEY", None)
            saved_secret = os.environ.pop("GROWW_API_SECRET", None)
            try:
                with self.assertRaisesRegex(RuntimeError, "GROWW_API_KEY"):
                    GrowwHistoryConfig.from_env(cache_dir=Path(tmp))
            finally:
                if saved_key is not None:
                    os.environ["GROWW_API_KEY"] = saved_key
                if saved_secret is not None:
                    os.environ["GROWW_API_SECRET"] = saved_secret

    def test_from_env_reads_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved_key = os.environ.get("GROWW_API_KEY")
            saved_secret = os.environ.get("GROWW_API_SECRET")
            os.environ["GROWW_API_KEY"] = "k"
            os.environ["GROWW_API_SECRET"] = "s"
            try:
                cfg = GrowwHistoryConfig.from_env(cache_dir=Path(tmp))
                self.assertEqual(cfg.api_key, "k")
                self.assertEqual(cfg.api_secret, "s")
                self.assertEqual(cfg.cache_dir, Path(tmp))
            finally:
                if saved_key is None:
                    os.environ.pop("GROWW_API_KEY", None)
                else:
                    os.environ["GROWW_API_KEY"] = saved_key
                if saved_secret is None:
                    os.environ.pop("GROWW_API_SECRET", None)
                else:
                    os.environ["GROWW_API_SECRET"] = saved_secret


class CandleParsingTests(unittest.TestCase):
    def test_handles_string_timestamps(self):
        candles = [["2025-09-24T10:30:00", 1.0, 2.0, 0.5, 1.5, 1000, None]]
        df = _candles_to_frame(candles)
        self.assertEqual(list(df.columns), ["open", "high", "low", "close", "volume"])
        self.assertEqual(int(df.iloc[0]["volume"]), 1000)
        self.assertEqual(df.iloc[0]["open"], 1.0)

    def test_handles_epoch_seconds(self):
        candles = [[1633072800, 1.0, 2.0, 0.5, 1.5, 1000]]
        df = _candles_to_frame(candles)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["close"], 1.5)

    def test_empty_returns_empty_schema(self):
        df = _candles_to_frame([])
        self.assertTrue(df.empty)
        self.assertEqual(list(df.columns), ["open", "high", "low", "close", "volume"])


class CacheTests(unittest.TestCase):
    def test_upsert_dedupes_overlapping_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = pd.DataFrame(
                [[1.0, 2.0, 0.5, 1.5, 100], [1.1, 2.1, 0.6, 1.6, 110]],
                index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="date"),
                columns=["open", "high", "low", "close", "volume"],
            )
            upsert_cache(tmp_path, "RELIANCE", base)
            update = pd.DataFrame(
                [[9.0, 9.0, 9.0, 9.0, 999]],
                index=pd.DatetimeIndex(["2024-01-02"], name="date"),
                columns=["open", "high", "low", "close", "volume"],
            )
            merged = upsert_cache(tmp_path, "RELIANCE", update)
            self.assertEqual(int(merged.loc["2024-01-02"]["volume"]), 999)
            self.assertEqual(len(merged), 2)

    def test_load_cached_returns_empty_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            df = load_cached(Path(tmp), "NONEXISTENT")
            self.assertTrue(df.empty)
            self.assertEqual(
                list(df.columns), ["open", "high", "low", "close", "volume"]
            )


class FetchDailyTests(unittest.TestCase):
    def test_chunks_at_180_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = GrowwHistoryClient(_cfg(Path(tmp)))
            client._client = _fake_sdk_client()
            client.fetch_daily("RELIANCE", date(2024, 1, 1), date(2025, 12, 31))
            # ~730 days at 180-day windows: ceil(730/180) = 5 chunks.
            self.assertEqual(client._client.get_historical_candles.call_count, 5)

    def test_empty_response_returns_empty_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = GrowwHistoryClient(_cfg(Path(tmp)))
            client._client = _fake_sdk_client()
            df = client.fetch_daily("RELIANCE", date(2025, 1, 1), date(2025, 1, 10))
            self.assertTrue(df.empty)

    def test_retries_on_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = GrowwHistoryClient(_cfg(Path(tmp)))
            fake = _fake_sdk_client()
            fake.get_historical_candles.side_effect = [
                Exception("transient"),
                {"candles": [["2025-01-15T00:00:00", 1.0, 2.0, 0.5, 1.5, 100]]},
            ]
            client._client = fake
            df = client.fetch_daily("RELIANCE", date(2025, 1, 1), date(2025, 1, 31))
            self.assertEqual(len(df), 1)
            self.assertEqual(fake.get_historical_candles.call_count, 2)

    def test_gives_up_after_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = GrowwHistoryClient(_cfg(Path(tmp)))
            fake = _fake_sdk_client()
            fake.get_historical_candles.side_effect = Exception("persistent")
            client._client = fake
            df = client.fetch_daily("RELIANCE", date(2025, 1, 1), date(2025, 1, 31))
            self.assertTrue(df.empty)
            self.assertEqual(fake.get_historical_candles.call_count, 2)


class UniverseFetchTests(unittest.TestCase):
    def test_is_resumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            client = GrowwHistoryClient(_cfg(tmp_path))
            fetched = pd.DataFrame(
                [[1.0, 2.0, 0.5, 1.5, 100]],
                index=pd.DatetimeIndex(["2025-01-15"], name="date"),
                columns=["open", "high", "low", "close", "volume"],
            )
            client.fetch_daily = MagicMock(return_value=fetched)
            manifest = fetch_and_cache_universe(
                client, ["RELIANCE"], date(2025, 1, 1), date(2025, 1, 15), tmp_path
            )
            self.assertEqual(manifest["RELIANCE"]["status"], "ok")

            client.fetch_daily.reset_mock()
            manifest2 = fetch_and_cache_universe(
                client, ["RELIANCE"], date(2025, 1, 1), date(2025, 1, 15), tmp_path
            )
            self.assertEqual(manifest2["RELIANCE"]["status"], "up_to_date")
            client.fetch_daily.assert_not_called()

    def test_isolates_symbol_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            client = GrowwHistoryClient(_cfg(tmp_path))
            good_df = pd.DataFrame(
                [[1.0, 2.0, 0.5, 1.5, 100]],
                index=pd.DatetimeIndex(["2025-01-15"], name="date"),
                columns=["open", "high", "low", "close", "volume"],
            )

            def side_effect(symbol, *_args, **_kwargs):
                if symbol == "BAD":
                    raise RuntimeError("simulated symbol failure")
                return good_df

            client.fetch_daily = MagicMock(side_effect=side_effect)
            manifest = fetch_and_cache_universe(
                client, ["GOOD", "BAD"], date(2025, 1, 1), date(2025, 1, 31), tmp_path
            )
            self.assertEqual(manifest["GOOD"]["status"], "ok")
            self.assertTrue(manifest["BAD"]["status"].startswith("error:"))

    def test_manifest_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            client = GrowwHistoryClient(_cfg(tmp_path))
            client.fetch_daily = MagicMock(
                return_value=pd.DataFrame(
                    [[1.0, 2.0, 0.5, 1.5, 100]],
                    index=pd.DatetimeIndex(["2025-01-15"], name="date"),
                    columns=["open", "high", "low", "close", "volume"],
                )
            )
            fetch_and_cache_universe(
                client, ["RELIANCE"], date(2025, 1, 1), date(2025, 1, 31), tmp_path
            )
            self.assertTrue((tmp_path / "_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
