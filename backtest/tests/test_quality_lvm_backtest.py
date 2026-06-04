"""Tests for Quality + LVM ranker and snapshot scoring mode."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.quality_lowvol_momentum import compute_quality_lvm_score


class Cfg:
    LVM_LOWVOL_POOL_SIZE = 40
    LVM_QUALITY_POOL_SIZE = 30
    LVM_TOP_N = 10
    LVM_REQUIRE_ABOVE_SMA50 = False
    LVM_SECTOR_CAP = 0
    LVM_QUALITY_MIN_ROE = 5.0
    LVM_QUALITY_MAX_DEBT_TO_EQUITY = 200.0
    LVM_QUALITY_MIN_EARNINGS_GROWTH = -100.0
    LVM_QUALITY_EXCLUDE_VALUE_TRAPS = True


def _synthetic_df(n=80):
    rng = np.random.default_rng(7)
    return pd.DataFrame({
        'symbol': [f'S{i}' for i in range(n)],
        'current_price': rng.uniform(100, 500, n),
        'legacy_sma_50': rng.uniform(90, 400, n),
        'price_change_1y': rng.uniform(0, 60, n),
        'volatility_6m': rng.uniform(8, 40, n),
        'sector': [f'Sec{i % 6}' for i in range(n)],
        'pit_roe': rng.uniform(8, 30, n),
        'pit_earnings_growth': rng.uniform(-5, 40, n),
        'pit_revenue_growth': rng.uniform(-5, 30, n),
        'pit_debt_to_equity': rng.uniform(0, 80, n),
        'pit_value_trap': False,
    })


def test_quality_lvm_adds_columns():
    out = compute_quality_lvm_score(_synthetic_df(), Cfg(), as_of=date(2024, 6, 1))
    assert 'quality_lvm_score' in out.columns
    assert 'quality_lvm_eligible' in out.columns
    assert out['quality_lvm_eligible'].sum() <= 10


def test_value_trap_excluded():
    df = _synthetic_df(50)
    df['pit_value_trap'] = False
    df.loc[0:5, 'pit_value_trap'] = True
    df.loc[0:5, 'price_change_1y'] = 99
    df.loc[0:5, 'volatility_6m'] = 5
    out = compute_quality_lvm_score(df, Cfg(), as_of=date(2024, 6, 1))
    trapped = set(df.loc[0:5, 'symbol'])
    picked = set(out.loc[out['quality_lvm_eligible'], 'symbol'])
    assert trapped.isdisjoint(picked)


def test_snapshot_builder_quality_mode(monkeypatch):
    from backtest.lvm_snapshot_builder import LvmSnapshotBuilder

    class FakeBuilder(LvmSnapshotBuilder):
        def __init__(self):
            self.universe = ['AAA', 'BBB', 'CCC']
            self.vol_mode = '12m'
            self.score_mode = 'quality_lvm'
            self.pit_only = False
            self.sectors = {s: 'IT' for s in self.universe}
            self._cfg = Cfg()

        def _row_for_symbol(self, sym, d, nifty_close):
            return {
                'date': pd.Timestamp(d),
                'symbol': sym,
                'sector': 'IT',
                'current_price': 100.0,
                'legacy_sma_50': 90.0,
                'sma_50': 90.0,
                'enhanced_sma_50': 90.0,
                'price_change_1y': 20.0,
                'volatility_12m': 15.0,
                'volatility_6m': 15.0,
            }

    b = FakeBuilder()
    snap = b._build_snapshot(date(2024, 6, 1))
    assert snap is not None
    assert 'quality_lvm_score' in snap.columns
    assert 'pit_roe' in snap.columns
