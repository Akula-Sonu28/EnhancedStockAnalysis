"""Tests for LowVol→Mom stock picker and RSI Pullback scanner."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ── LowVol→Mom tests ──

class TestComputeLowvolMomScore:
    def _make_df(self, n=60):
        np.random.seed(42)
        return pd.DataFrame({
            'symbol': [f'SYM{i}' for i in range(n)],
            'current_price': np.random.uniform(100, 5000, n),
            'enhanced_sma_50': np.random.uniform(90, 4500, n),
            'volatility_6m': np.random.uniform(10, 60, n),
            'price_change_1y': np.random.uniform(-30, 80, n),
            'sector': np.random.choice(['IT', 'Bank', 'Pharma', 'Auto', 'Metal'], n),
        })

    def test_adds_required_columns(self):
        from src.lowvol_momentum import compute_lowvol_mom_score
        df = self._make_df()
        out = compute_lowvol_mom_score(df)
        assert 'lowvol_mom_score' in out.columns
        assert 'lowvol_mom_rank' in out.columns
        assert 'lowvol_mom_eligible' in out.columns

    def test_eligible_count_respects_top_n(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 40
            LVM_TOP_N = 10
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        df = self._make_df(100)
        out = compute_lowvol_mom_score(df, Cfg())
        assert out['lowvol_mom_eligible'].sum() <= 10

    def test_sector_cap_applied(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 40
            LVM_TOP_N = 10
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 2

        df = self._make_df(100)
        df['sector'] = 'IT'  # all same sector
        out = compute_lowvol_mom_score(df, Cfg())
        assert out['lowvol_mom_eligible'].sum() <= 2

    def test_sma50_filter(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 40
            LVM_TOP_N = 10
            LVM_REQUIRE_ABOVE_SMA50 = True
            LVM_SECTOR_CAP = 0

        df = self._make_df(50)
        df['current_price'] = 50
        df['enhanced_sma_50'] = 100  # all below SMA50
        out = compute_lowvol_mom_score(df, Cfg())
        assert out['lowvol_mom_eligible'].sum() == 0

    def test_empty_df(self):
        from src.lowvol_momentum import compute_lowvol_mom_score
        out = compute_lowvol_mom_score(pd.DataFrame())
        assert out is not None

    def test_eligible_stocks_have_higher_score(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 40
            LVM_TOP_N = 5
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        df = self._make_df(80)
        out = compute_lowvol_mom_score(df, Cfg())
        eligible = out[out['lowvol_mom_eligible']]
        not_eligible = out[~out['lowvol_mom_eligible']]
        if not eligible.empty and not not_eligible.empty:
            assert eligible['lowvol_mom_score'].min() > not_eligible['lowvol_mom_score'].max()


# ── Oracle integration tests ──

class TestOracleIntegration:
    def _make_df(self, n=50):
        np.random.seed(7)
        return pd.DataFrame({
            'symbol': [f'SYM{i}' for i in range(n)],
            'current_price': np.random.uniform(100, 5000, n),
            'enhanced_sma_50': np.random.uniform(80, 4000, n),
            'volatility_6m': np.random.uniform(10, 60, n),
            'price_change_1y': np.random.uniform(-20, 60, n),
            'hybrid_volume_strength': np.random.uniform(20, 80, n),
            'hybrid_momentum_technical': np.random.uniform(30, 70, n),
            'sector': np.random.choice(['IT', 'Bank', 'Pharma'], n),
        })

    def test_oracle_pick_metric_lowvol_mom(self):
        from src.flow_quality_oracle import add_oracle_pick_columns

        class Cfg:
            ORACLE_PICK_METRIC = 'lowvol_mom'
            ORACLE_WATCHLIST_PCT = 0.20
            FQ_LAMBDA_DEFAULT = 0.5
            LVM_LOWVOL_POOL_SIZE = 20
            LVM_TOP_N = 5
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        df = self._make_df()
        out = add_oracle_pick_columns(df, Cfg())
        assert 'lowvol_mom_score' in out.columns
        assert 'on_oracle_watchlist' in out.columns
        assert out['on_oracle_watchlist'].sum() > 0

    def test_oracle_pick_metric_fq_still_works(self):
        from src.flow_quality_oracle import add_oracle_pick_columns

        class Cfg:
            ORACLE_PICK_METRIC = 'fq_score'
            ORACLE_WATCHLIST_PCT = 0.20
            FQ_LAMBDA_DEFAULT = 0.5

        df = self._make_df()
        out = add_oracle_pick_columns(df, Cfg())
        assert 'fq_score' in out.columns
        assert 'on_oracle_watchlist' in out.columns


# ── Picking rank tests ──

class TestPickingRank:
    def test_lowvol_mom_driver(self):
        from src.picking_metrics import resolve_picking_rank_value

        class Cfg:
            PICKING_RANK_DRIVER = 'lowvol_mom'
            ENTRY_DRIVER = 'turbo_mtf'

        row = {'lowvol_mom_score': 85.5, 'fq_score': 20.0, 'turbo_score': 60.0}
        val = resolve_picking_rank_value(row, Cfg())
        assert val == 85.5

    def test_lowvol_mom_in_holdings_rank(self):
        from src.picking_metrics import resolve_holdings_rank_score

        class Cfg:
            ORACLE_STACK_ALIGN = True
            PICKING_RANK_DRIVER = 'lowvol_mom'

        row = {'picking_rank': None, 'lowvol_mom_score': 75.0, 'fq_score': 30.0}
        val = resolve_holdings_rank_score(row, Cfg())
        assert val == 75.0


# ── RSI Pullback scanner tests ──

class TestRsiPullbackScanner:
    def test_scan_basic(self):
        from src.rsi_pullback_scanner import scan_rsi_pullback
        df = pd.DataFrame({
            'symbol': ['A', 'B', 'C'],
            'current_price': [100, 200, 300],
            'enhanced_sma_50': [90, 250, 280],
            'real_rsi': [40, 60, 38],
            'sector': ['IT', 'Bank', 'Pharma'],
        })
        out = scan_rsi_pullback(df)
        assert len(out) == 2  # A (rsi=40, above sma) and C (rsi=38, above sma)
        assert 'B' not in out['symbol'].values  # RSI too high

    def test_scan_empty(self):
        from src.rsi_pullback_scanner import scan_rsi_pullback
        out = scan_rsi_pullback(pd.DataFrame())
        assert len(out) == 0


# ── Gap-fill tests: LowVol→Mom integration ──


class TestEmptyDataFrameColumns:
    """Gap 1: empty DataFrame must still produce required columns."""

    def test_empty_df_returns_required_columns_present(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        empty = pd.DataFrame(columns=[
            'symbol', 'current_price', 'enhanced_sma_50',
            'volatility_6m', 'price_change_1y', 'sector',
        ])
        out = compute_lowvol_mom_score(empty)
        # With schema columns but zero rows, should still return DF
        assert out is not None
        for col in ('lowvol_mom_score', 'lowvol_mom_rank', 'lowvol_mom_eligible'):
            assert col in out.columns, f"Missing column: {col}"
        assert len(out) == 0

    def test_truly_empty_df_returns_as_is(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        out = compute_lowvol_mom_score(pd.DataFrame())
        # Totally empty DF — implementation returns early (df.empty guard)
        assert out is not None
        assert len(out) == 0

    def test_none_input_returns_none(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        out = compute_lowvol_mom_score(None)
        assert out is None


class TestNaNHandling:
    """Gap 2: NaN/None values in volatility and return columns."""

    def _make_nan_df(self, n=30):
        np.random.seed(99)
        df = pd.DataFrame({
            'symbol': [f'NAN{i}' for i in range(n)],
            'current_price': np.random.uniform(100, 2000, n),
            'enhanced_sma_50': np.random.uniform(80, 1800, n),
            'volatility_6m': np.random.uniform(10, 50, n),
            'price_change_1y': np.random.uniform(-20, 60, n),
            'sector': np.random.choice(['IT', 'Bank', 'Pharma'], n),
        })
        # Inject NaN/None in volatility
        df.loc[0, 'volatility_6m'] = np.nan
        df.loc[1, 'volatility_6m'] = None
        # Inject NaN/None in return
        df.loc[2, 'price_change_1y'] = np.nan
        df.loc[3, 'price_change_1y'] = None
        # All NaN row
        df.loc[4, 'volatility_6m'] = np.nan
        df.loc[4, 'price_change_1y'] = np.nan
        return df

    def test_nan_volatility_does_not_crash(self):
        from src.lowvol_momentum import compute_lowvol_mom_score
        df = self._make_nan_df()
        out = compute_lowvol_mom_score(df)
        assert out is not None
        assert 'lowvol_mom_score' in out.columns
        assert len(out) == len(df)

    def test_nan_return_does_not_crash(self):
        from src.lowvol_momentum import compute_lowvol_mom_score
        df = self._make_nan_df()
        out = compute_lowvol_mom_score(df)
        assert not out['lowvol_mom_score'].isna().all()

    def test_all_nan_volatility(self):
        from src.lowvol_momentum import compute_lowvol_mom_score
        df = pd.DataFrame({
            'symbol': ['A', 'B', 'C'],
            'current_price': [100, 200, 300],
            'enhanced_sma_50': [90, 180, 280],
            'volatility_6m': [np.nan, np.nan, np.nan],
            'price_change_1y': [10.0, 20.0, 30.0],
            'sector': ['IT', 'IT', 'Bank'],
        })
        out = compute_lowvol_mom_score(df)
        assert out is not None
        assert 'lowvol_mom_score' in out.columns

    def test_string_values_in_numeric_columns(self):
        """Non-numeric strings should be coerced gracefully."""
        from src.lowvol_momentum import compute_lowvol_mom_score
        df = pd.DataFrame({
            'symbol': ['X', 'Y', 'Z'],
            'current_price': [100, 200, 300],
            'enhanced_sma_50': [90, 180, 280],
            'volatility_6m': ['bad', '15.0', 'N/A'],
            'price_change_1y': [10.0, 'err', 30.0],
            'sector': ['IT', 'Bank', 'Pharma'],
        })
        out = compute_lowvol_mom_score(df)
        assert out is not None
        assert len(out) == 3


class TestTieBreaking:
    """Gap 3: stocks with identical volatility — deterministic, no crash."""

    def test_identical_volatility_no_crash(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 10
            LVM_TOP_N = 5
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        n = 20
        df = pd.DataFrame({
            'symbol': [f'TIE{i}' for i in range(n)],
            'current_price': np.arange(100, 100 + n, dtype=float),
            'enhanced_sma_50': np.full(n, 50.0),
            'volatility_6m': np.full(n, 25.0),  # all identical vol
            'price_change_1y': np.arange(1, n + 1, dtype=float),
            'sector': ['IT'] * n,
        })
        out = compute_lowvol_mom_score(df, Cfg())
        assert out is not None
        assert out['lowvol_mom_eligible'].sum() == 5

    def test_identical_volatility_deterministic_ordering(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 10
            LVM_TOP_N = 5
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        n = 20
        df = pd.DataFrame({
            'symbol': [f'TIE{i}' for i in range(n)],
            'current_price': np.arange(100, 100 + n, dtype=float),
            'enhanced_sma_50': np.full(n, 50.0),
            'volatility_6m': np.full(n, 25.0),
            'price_change_1y': np.arange(1, n + 1, dtype=float),
            'sector': ['IT'] * n,
        })
        out1 = compute_lowvol_mom_score(df.copy(), Cfg())
        out2 = compute_lowvol_mom_score(df.copy(), Cfg())
        # Same input → same eligible set
        eligible1 = set(out1[out1['lowvol_mom_eligible']]['symbol'].tolist())
        eligible2 = set(out2[out2['lowvol_mom_eligible']]['symbol'].tolist())
        assert eligible1 == eligible2

    def test_identical_returns_tie(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 10
            LVM_TOP_N = 5
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        n = 15
        df = pd.DataFrame({
            'symbol': [f'TRET{i}' for i in range(n)],
            'current_price': np.arange(100, 100 + n, dtype=float),
            'enhanced_sma_50': np.full(n, 50.0),
            'volatility_6m': np.linspace(10, 30, n),
            'price_change_1y': np.full(n, 42.0),  # identical returns
            'sector': ['Bank'] * n,
        })
        out = compute_lowvol_mom_score(df, Cfg())
        assert out is not None
        assert out['lowvol_mom_eligible'].sum() <= 5


class TestMisconfigTopNExceedsPoolSize:
    """Gap 4: LVM_TOP_N > LVM_LOWVOL_POOL_SIZE should not crash."""

    def test_top_n_greater_than_pool_size(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 5
            LVM_TOP_N = 20  # top_n > pool_size
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        np.random.seed(88)
        df = pd.DataFrame({
            'symbol': [f'MISC{i}' for i in range(30)],
            'current_price': np.random.uniform(100, 1000, 30),
            'enhanced_sma_50': np.random.uniform(80, 900, 30),
            'volatility_6m': np.random.uniform(10, 50, 30),
            'price_change_1y': np.random.uniform(-10, 60, 30),
            'sector': np.random.choice(['IT', 'Pharma'], 30),
        })
        out = compute_lowvol_mom_score(df, Cfg())
        assert out is not None
        # eligible should be capped at pool_size since pool < top_n
        assert out['lowvol_mom_eligible'].sum() <= 5

    def test_top_n_equals_pool_size(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 10
            LVM_TOP_N = 10
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        np.random.seed(77)
        df = pd.DataFrame({
            'symbol': [f'EQ{i}' for i in range(50)],
            'current_price': np.random.uniform(100, 1000, 50),
            'enhanced_sma_50': np.random.uniform(80, 900, 50),
            'volatility_6m': np.random.uniform(10, 50, 50),
            'price_change_1y': np.random.uniform(-10, 60, 50),
            'sector': np.random.choice(['IT', 'Bank', 'Pharma'], 50),
        })
        out = compute_lowvol_mom_score(df, Cfg())
        assert out is not None
        assert out['lowvol_mom_eligible'].sum() <= 10

    def test_top_n_greater_than_universe_size(self):
        from src.lowvol_momentum import compute_lowvol_mom_score

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 100
            LVM_TOP_N = 50
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        df = pd.DataFrame({
            'symbol': ['TINY1', 'TINY2', 'TINY3'],
            'current_price': [100, 200, 300],
            'enhanced_sma_50': [90, 180, 280],
            'volatility_6m': [15.0, 20.0, 25.0],
            'price_change_1y': [10.0, 20.0, 30.0],
            'sector': ['IT', 'Bank', 'Pharma'],
        })
        out = compute_lowvol_mom_score(df, Cfg())
        assert out is not None
        # Can't exceed universe size
        assert out['lowvol_mom_eligible'].sum() <= 3


class TestRollbackToFqScore:
    """Gap 5: switching ORACLE_PICK_METRIC back to fq_score still works."""

    def _make_df(self, n=40):
        np.random.seed(55)
        return pd.DataFrame({
            'symbol': [f'RB{i}' for i in range(n)],
            'current_price': np.random.uniform(100, 3000, n),
            'enhanced_sma_50': np.random.uniform(80, 2800, n),
            'volatility_6m': np.random.uniform(10, 50, n),
            'price_change_1y': np.random.uniform(-10, 60, n),
            'hybrid_volume_strength': np.random.uniform(20, 80, n),
            'hybrid_momentum_technical': np.random.uniform(30, 70, n),
            'sector': np.random.choice(['IT', 'Bank', 'Pharma', 'Auto'], n),
        })

    def test_rollback_fq_score_produces_watchlist(self):
        from src.flow_quality_oracle import add_oracle_pick_columns

        class Cfg:
            ORACLE_PICK_METRIC = 'fq_score'
            ORACLE_WATCHLIST_PCT = 0.20
            FQ_LAMBDA_DEFAULT = 0.5

        df = self._make_df()
        out = add_oracle_pick_columns(df, Cfg())
        assert 'fq_score' in out.columns
        assert 'on_oracle_watchlist' in out.columns
        assert out['on_oracle_watchlist'].sum() > 0
        # No lowvol_mom columns should be injected
        assert 'lowvol_mom_score' not in out.columns

    def test_rollback_fq_score_oracle_pick_pct_populated(self):
        from src.flow_quality_oracle import add_oracle_pick_columns

        class Cfg:
            ORACLE_PICK_METRIC = 'fq_score'
            ORACLE_WATCHLIST_PCT = 0.25
            FQ_LAMBDA_DEFAULT = 0.5

        df = self._make_df()
        out = add_oracle_pick_columns(df, Cfg())
        assert 'oracle_pick_pct' in out.columns
        assert out['oracle_pick_pct'].min() >= 0.0
        assert out['oracle_pick_pct'].max() <= 1.0

    def test_rollback_picking_rank_uses_fq(self):
        from src.picking_metrics import resolve_picking_rank_value

        class Cfg:
            PICKING_RANK_DRIVER = 'fq'
            ENTRY_DRIVER = 'turbo_mtf'
            ORACLE_STACK_ALIGN = True

        row = {'fq_score': 42.5, 'lowvol_mom_score': 90.0, 'turbo_score': 60.0}
        val = resolve_picking_rank_value(row, Cfg())
        # With driver='fq', lowvol_mom_score should NOT be selected
        assert val != 90.0

    def test_switch_between_lowvol_and_fq(self):
        """Simulate switching from lowvol_mom → fq_score and back."""
        from src.flow_quality_oracle import add_oracle_pick_columns

        df = self._make_df()

        class CfgLowvol:
            ORACLE_PICK_METRIC = 'lowvol_mom'
            ORACLE_WATCHLIST_PCT = 0.20
            FQ_LAMBDA_DEFAULT = 0.5
            LVM_LOWVOL_POOL_SIZE = 20
            LVM_TOP_N = 5
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        class CfgFq:
            ORACLE_PICK_METRIC = 'fq_score'
            ORACLE_WATCHLIST_PCT = 0.20
            FQ_LAMBDA_DEFAULT = 0.5

        out_lvm = add_oracle_pick_columns(df.copy(), CfgLowvol())
        out_fq = add_oracle_pick_columns(df.copy(), CfgFq())
        # Both produce watchlist but potentially different members
        assert out_lvm['on_oracle_watchlist'].sum() > 0
        assert out_fq['on_oracle_watchlist'].sum() > 0
        assert 'lowvol_mom_score' in out_lvm.columns
        assert 'lowvol_mom_score' not in out_fq.columns


class TestScanFromPriceHistory:
    """Gap 6: scan_from_price_history basic coverage."""

    def _make_history(self, n_days=80, final_price=100.0, rsi_target=40.0):
        """Build synthetic price history that produces a target-ish RSI."""
        np.random.seed(123)
        prices = np.linspace(80, final_price, n_days) + np.random.normal(0, 0.5, n_days)
        prices[-1] = final_price
        return pd.DataFrame({'Close': prices})

    def test_basic_scan_returns_dataframe(self):
        from src.rsi_pullback_scanner import scan_from_price_history

        hist_a = self._make_history(80, 120.0)
        hist_b = self._make_history(80, 90.0)
        history_dict = {'STOCKA': hist_a, 'STOCKB': hist_b}
        out = scan_from_price_history(['STOCKA', 'STOCKB'], history_dict)
        assert isinstance(out, pd.DataFrame)

    def test_insufficient_history_skipped(self):
        from src.rsi_pullback_scanner import scan_from_price_history

        short_hist = pd.DataFrame({'Close': [100, 101, 102]})  # < 55 rows
        history_dict = {'SHORT': short_hist}
        out = scan_from_price_history(['SHORT'], history_dict)
        assert len(out) == 0

    def test_missing_symbol_skipped(self):
        from src.rsi_pullback_scanner import scan_from_price_history

        history_dict = {'EXISTS': self._make_history(80, 120.0)}
        out = scan_from_price_history(['EXISTS', 'MISSING'], history_dict)
        # MISSING is not in dict → gracefully skipped
        assert 'MISSING' not in out.get('symbol', pd.Series()).values

    def test_below_sma50_excluded(self):
        """Stocks below their 50-day SMA should not pass."""
        from src.rsi_pullback_scanner import scan_from_price_history

        # Create a declining series so current price < SMA50
        prices = np.linspace(150, 80, 80)
        hist = pd.DataFrame({'Close': prices})
        history_dict = {'BELOW': hist}
        out = scan_from_price_history(['BELOW'], history_dict)
        assert 'BELOW' not in out.get('symbol', pd.Series()).values

    def test_empty_symbols_list(self):
        from src.rsi_pullback_scanner import scan_from_price_history

        out = scan_from_price_history([], {})
        assert isinstance(out, pd.DataFrame)
        assert len(out) == 0

    def test_output_columns_present(self):
        """When a candidate is found, output has required columns."""
        from src.rsi_pullback_scanner import scan_from_price_history

        np.random.seed(42)
        # Construct a history that has RSI in the 35-45 range and rising
        base = np.linspace(80, 130, 60)
        # Add a dip at the end to pull RSI down
        dip = np.concatenate([base, np.linspace(130, 115, 10), np.array([116, 117])])
        hist = pd.DataFrame({'Close': dip})
        history_dict = {'CAND': hist}
        out = scan_from_price_history(['CAND'], history_dict)
        if len(out) > 0:
            for col in ('symbol', 'current_price', 'rsi', 'distance_to_40', 'signal'):
                assert col in out.columns


class TestTurboBypass:
    """Gap 7: LVM_BYPASS_TURBO_GATE — when True and lowvol_mom_eligible,
    the turbo gate should be skipped (entry allowed regardless of turbo score).

    NOTE: This tests the *contract* that the integration should satisfy once
    the bypass is wired into evaluate_turbo_entry_gate. If the feature is not
    yet implemented, the test will xfail gracefully.
    """

    def _build_row(self, eligible: bool, turbo_score: float = 40.0):
        return {
            'symbol': 'BYPASS_TEST',
            'current_price': 500.0,
            'enhanced_sma_50': 480.0,
            'hybrid_momentum_technical': 55.0,
            'hybrid_multi_timeframe': 60.0,
            'hybrid_fundamental_quality': 55.0,
            'hybrid_volume_strength': 50.0,
            'hybrid_risk_adjustment': 50.0,
            'hybrid_ml_signal': 50.0,
            'hybrid_growth': 50.0,
            'hybrid_value': 50.0,
            'final_blended_score': 60.0,
            'lowvol_mom_eligible': eligible,
            'lowvol_mom_score': 85.0 if eligible else 20.0,
            'price_change_5d': 1.0,
            'confirm_3d_return': 1.5,
            'real_rsi': 55.0,
        }

    @pytest.mark.xfail(reason="LVM_BYPASS_TURBO_GATE not yet implemented", strict=False)
    def test_bypass_true_eligible_skips_turbo_gate(self):
        from src.turbo_entry import evaluate_turbo_entry_gate

        class Cfg:
            ENTRY_DRIVER = 'turbo_mtf'
            LVM_BYPASS_TURBO_GATE = True
            TURBO_ENTRY_V2_MIN = 60.0
            TURBO_ENTRY_MTF_MIN = 55.0
            TURBO_ENTRY_MOM_MIN = 50.0
            TURBO_ENTRY_VS_MIN = 0.0
            TURBO_ENTRY_RSI_HARD_BLOCK = 75.0
            ENTRY_CONFIRM_3D_MIN_RET = 0.0
            ENTRY_CONFIRM_3D_STRONG_RET = 2.0
            ENTRY_V1_SCORE_FLOOR = 55.0
            VMQ_MAX_NEW_PER_WEEK = 3
            VMQ_V2_BUY_THRESHOLD = 60.0
            ORACLE_STACK_ALIGN = True
            PICKING_RANK_DRIVER = 'lowvol_mom'

        row = self._build_row(eligible=True, turbo_score=30.0)
        result = evaluate_turbo_entry_gate(row, Cfg(), new_this_week=0)
        # Bypass means turbo gate is irrelevant for LVM-eligible stocks
        assert result.allowed is True or result.status == 'PASS'

    @pytest.mark.xfail(reason="LVM_BYPASS_TURBO_GATE not yet implemented", strict=False)
    def test_bypass_true_not_eligible_still_enforces_turbo(self):
        from src.turbo_entry import evaluate_turbo_entry_gate

        class Cfg:
            ENTRY_DRIVER = 'turbo_mtf'
            LVM_BYPASS_TURBO_GATE = True
            TURBO_ENTRY_V2_MIN = 60.0
            TURBO_ENTRY_MTF_MIN = 55.0
            TURBO_ENTRY_MOM_MIN = 50.0
            TURBO_ENTRY_VS_MIN = 0.0
            TURBO_ENTRY_RSI_HARD_BLOCK = 75.0
            ENTRY_CONFIRM_3D_MIN_RET = 0.0
            ENTRY_CONFIRM_3D_STRONG_RET = 2.0
            ENTRY_V1_SCORE_FLOOR = 55.0
            VMQ_MAX_NEW_PER_WEEK = 3
            VMQ_V2_BUY_THRESHOLD = 60.0
            ORACLE_STACK_ALIGN = True
            PICKING_RANK_DRIVER = 'lowvol_mom'

        row = self._build_row(eligible=False, turbo_score=30.0)
        result = evaluate_turbo_entry_gate(row, Cfg(), new_this_week=0)
        # NOT eligible → turbo gate NOT bypassed, should fail
        assert result.allowed is False

    @pytest.mark.xfail(reason="LVM_BYPASS_TURBO_GATE not yet implemented", strict=False)
    def test_bypass_false_eligible_still_checks_turbo(self):
        from src.turbo_entry import evaluate_turbo_entry_gate

        class Cfg:
            ENTRY_DRIVER = 'turbo_mtf'
            LVM_BYPASS_TURBO_GATE = False
            TURBO_ENTRY_V2_MIN = 60.0
            TURBO_ENTRY_MTF_MIN = 55.0
            TURBO_ENTRY_MOM_MIN = 50.0
            TURBO_ENTRY_VS_MIN = 0.0
            TURBO_ENTRY_RSI_HARD_BLOCK = 75.0
            ENTRY_CONFIRM_3D_MIN_RET = 0.0
            ENTRY_CONFIRM_3D_STRONG_RET = 2.0
            ENTRY_V1_SCORE_FLOOR = 55.0
            VMQ_MAX_NEW_PER_WEEK = 3
            VMQ_V2_BUY_THRESHOLD = 60.0
            ORACLE_STACK_ALIGN = True
            PICKING_RANK_DRIVER = 'lowvol_mom'

        row = self._build_row(eligible=True, turbo_score=30.0)
        result = evaluate_turbo_entry_gate(row, Cfg(), new_this_week=0)
        # bypass disabled → turbo gate enforced even when eligible
        assert result.allowed is False


class TestQualityLvmStabilityAudit:
    def test_active_lvm_score_defaults_as_of_for_quality(self):
        from datetime import date
        from src.lowvol_momentum import compute_active_lvm_score
        import pandas as pd

        class Cfg:
            ORACLE_PICK_METRIC = 'quality_lvm'
            LVM_QUALITY_REQUIRE_REAL_PIT = True
            LVM_LOWVOL_POOL_SIZE = 40
            LVM_TOP_N = 5
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0

        df = pd.DataFrame({
            'symbol': ['RELIANCE', 'TCS', 'INFY'],
            'current_price': [2500.0, 3500.0, 1500.0],
            'volatility_6m': [20.0, 18.0, 22.0],
            'price_change_1y': [15.0, 12.0, 10.0],
            'sector': ['Energy', 'IT', 'IT'],
            'pit_roe': [18.0, 20.0, 22.0],
            'pit_earnings_growth': [12.0, 10.0, 8.0],
            'pit_revenue_growth': [8.0, 7.0, 6.0],
            'pit_debt_to_equity': [40.0, 10.0, 5.0],
            'pit_value_trap': [False, False, False],
            'pit_has_real_filing': [True, True, True],
        })
        out = compute_active_lvm_score(df, Cfg())
        assert out['quality_lvm_eligible'].sum() > 0


class TestLvmTopNConfig:
    def test_lvm_top_n_sheet_and_label(self):
        from src.lowvol_momentum import lvm_fund_n, lvm_sheet_name, lvm_top_label, lvm_top_n

        class Cfg20:
            LVM_TOP_N = 20
            LVM_FUND_N = 12
            ORACLE_PICK_METRIC = 'quality_lvm'

        assert lvm_top_n(Cfg20()) == 20
        assert lvm_fund_n(Cfg20()) == 12
        assert lvm_sheet_name(Cfg20()) == 'Quality-LVM Top 20'
        assert lvm_top_label(Cfg20()) == 'LVM Top 20'

        class Cfg10:
            LVM_TOP_N = 10
            ORACLE_PICK_METRIC = 'lowvol_mom'

        assert lvm_sheet_name(Cfg10()) == 'LowVol-Mom Top 10'

    def test_lvm_fund_symbols_caps_fund_n(self):
        from src.lowvol_momentum import (
            compute_lowvol_mom_score,
            lvm_eligible_symbols,
            lvm_fund_symbols,
        )

        class Cfg:
            LVM_LOWVOL_POOL_SIZE = 40
            LVM_TOP_N = 20
            LVM_FUND_N = 10
            LVM_REQUIRE_ABOVE_SMA50 = False
            LVM_SECTOR_CAP = 0
            ORACLE_PICK_METRIC = 'lowvol_mom'

        np.random.seed(1)
        n = 80
        df = pd.DataFrame({
            'symbol': [f'SYM{i}' for i in range(n)],
            'current_price': np.random.uniform(100, 5000, n),
            'enhanced_sma_50': np.random.uniform(90, 4500, n),
            'volatility_6m': np.random.uniform(10, 60, n),
            'price_change_1y': np.random.uniform(-30, 80, n),
            'sector': np.random.choice(['IT', 'Bank', 'Pharma', 'Auto', 'Metal'], n),
        })
        out = compute_lowvol_mom_score(df, Cfg())
        funded = lvm_fund_symbols(out, Cfg())
        assert len(funded) == 10
        assert len(lvm_eligible_symbols(out, Cfg())) == 20


class TestLvmAllocationHelpers:
    def test_apply_lvm_rotation_marks_non_lvm_holdings(self):
        from src.lowvol_momentum import apply_lvm_rotation_to_allocation

        alloc = pd.DataFrame([
            {'symbol': 'AAA', 'is_current_holding': True, 'current_value': 5000,
             'action_recommendation': 'HOLD', 'exit_reason': 'ok'},
            {'symbol': 'BBB', 'is_current_holding': True, 'current_value': 3000,
             'action_recommendation': 'HOLD', 'exit_reason': 'ok'},
            {'symbol': 'CCC', 'is_current_holding': True, 'current_value': 2000,
             'action_recommendation': 'SELL', 'exit_reason': 'vmq'},
        ])
        out, n = apply_lvm_rotation_to_allocation(alloc, {'AAA'})
        assert n == 1
        bbb = out[out['symbol'] == 'BBB'].iloc[0]
        assert 'LVM ROTATION' in str(bbb['action_recommendation'])
        assert bbb['keep_stock'] is False
        aaa = out[out['symbol'] == 'AAA'].iloc[0]
        assert aaa['action_recommendation'] == 'HOLD'
        ccc = out[out['symbol'] == 'CCC'].iloc[0]
        assert ccc['action_recommendation'] == 'SELL'

    def test_fund_lvm_picks_equal_weight_new_positions(self):
        from src.lowvol_momentum import fund_lvm_picks_equal_weight

        results = pd.DataFrame([
            {'symbol': 'AAA', 'company_name': 'A Ltd', 'sector': 'IT',
             'current_price': 100.0, 'lowvol_mom_eligible': True, 'lowvol_mom_score': 150},
            {'symbol': 'BBB', 'company_name': 'B Ltd', 'sector': 'Bank',
             'current_price': 50.0, 'lowvol_mom_eligible': True, 'lowvol_mom_score': 140},
        ])
        alloc = pd.DataFrame(columns=[
            'symbol', 'company_name', 'sector', 'current_price', 'current_value',
            'current_quantity', 'investment_amount', 'suggested_quantity',
            'action_recommendation', 'keep_stock', 'is_current_holding',
        ])
        out, total, buys, incs, rem = fund_lvm_picks_equal_weight(
            alloc, results, {'AAA', 'BBB'}, 10000, 1000,
        )
        assert buys == 2
        assert incs == 0
        assert total > 0
        assert len(out) == 2
        assert (out['investment_amount'] > 0).all()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
