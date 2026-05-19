"""Unit tests for backtest.metrics.

Covers the new rolling_sharpe helper. Deterministic — uses a fixed
numpy seed (42) so failures are reproducible across machines.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backtest.metrics import TRADING_DAYS_PER_YEAR, rolling_sharpe  # noqa: E402


SEED = 42


def _make_returns(rows: int, cols: int, vol: float = 0.01) -> pd.DataFrame:
    """Deterministic Gaussian daily returns (mu=0, sigma=vol)."""
    rng = np.random.default_rng(SEED)
    data = rng.standard_normal((rows, cols)) * vol
    dates = pd.bdate_range('2025-01-01', periods=rows)
    cols_named = [f'STOCK_{i}' for i in range(cols)]
    return pd.DataFrame(data, index=dates, columns=cols_named)


class TestRollingSharpeShape:

    def test_returns_series(self):
        df = _make_returns(60, 5)
        out = rolling_sharpe(df, window=30)
        assert isinstance(out, pd.Series)
        assert out.name == 'rolling_sharpe'

    def test_length_matches_input(self):
        df = _make_returns(60, 5)
        out = rolling_sharpe(df, window=30)
        assert len(out) == len(df)
        assert (out.index == df.index).all()

    def test_first_window_minus_one_are_nan(self):
        df = _make_returns(60, 5)
        out = rolling_sharpe(df, window=30)
        assert out.iloc[:29].isna().all()
        assert not pd.isna(out.iloc[29])


class TestRollingSharpeFormula:

    def test_matches_direct_formula_at_first_valid_index(self):
        """rolling_sharpe at t=window-1 must equal the direct annualised
        Sharpe of the trailing-window portfolio returns."""
        df = _make_returns(45, 3)
        window = 30
        rf = 0.07

        portfolio_returns = df.mean(axis=1)
        head = portfolio_returns.iloc[:window]
        daily_rf = rf / TRADING_DAYS_PER_YEAR
        expected = ((head - daily_rf).mean() / head.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)

        out = rolling_sharpe(df, window=window, risk_free_annual=rf)
        assert out.iloc[window - 1] == pytest.approx(float(expected), rel=1e-12)

    def test_matches_direct_formula_at_last_index(self):
        df = _make_returns(80, 4)
        window = 30
        rf = 0.07

        portfolio_returns = df.mean(axis=1)
        tail = portfolio_returns.iloc[-window:]
        daily_rf = rf / TRADING_DAYS_PER_YEAR
        expected = ((tail - daily_rf).mean() / tail.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)

        out = rolling_sharpe(df, window=window, risk_free_annual=rf)
        assert out.iloc[-1] == pytest.approx(float(expected), rel=1e-12)

    def test_single_column_equals_self_aggregation(self):
        df = _make_returns(50, 1)
        out_df = rolling_sharpe(df, window=20)
        out_series_as_df = rolling_sharpe(df[['STOCK_0']].copy(), window=20)
        pd.testing.assert_series_equal(out_df, out_series_as_df)

    def test_zero_risk_free_does_not_flip_sign(self):
        """With rf=0 and positive-mean returns, Sharpe must be positive."""
        rng = np.random.default_rng(SEED)
        positive_drift = rng.standard_normal((60, 3)) * 0.01 + 0.002
        df = pd.DataFrame(positive_drift, index=pd.bdate_range('2025-01-01', periods=60))
        out = rolling_sharpe(df, window=30, risk_free_annual=0.0).dropna()
        assert (out > 0).all()


class TestRollingSharpeEdgeCases:

    def test_constant_returns_yield_nan(self):
        df = pd.DataFrame(
            np.full((40, 2), 0.001),
            index=pd.bdate_range('2025-01-01', periods=40),
            columns=['A', 'B'],
        )
        out = rolling_sharpe(df, window=20)
        assert out.iloc[19:].isna().all()

    def test_empty_dataframe_returns_empty_series(self):
        out = rolling_sharpe(pd.DataFrame(), window=30)
        assert isinstance(out, pd.Series)
        assert out.empty
        assert out.name == 'rolling_sharpe'

    def test_none_returns_empty_series(self):
        out = rolling_sharpe(None, window=30)
        assert out.empty

    def test_window_too_small_raises(self):
        df = _make_returns(30, 2)
        with pytest.raises(ValueError, match='window must be >= 2'):
            rolling_sharpe(df, window=1)
        with pytest.raises(ValueError):
            rolling_sharpe(df, window=0)

    def test_window_larger_than_rows_all_nan(self):
        df = _make_returns(10, 2)
        out = rolling_sharpe(df, window=30)
        assert out.isna().all()

    def test_no_inf_in_output(self):
        df = _make_returns(60, 3)
        out = rolling_sharpe(df, window=30)
        finite = out.dropna()
        assert np.isfinite(finite).all()


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
