"""Tests for LVM backtest snapshot builder and strategy."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from backtest.lvm_strategy import LVMStrategyAdapter
from backtest.data.indicators import annualized_volatility_12m, return_12m_pct


def test_return_12m_and_vol_12m_on_trend():
    n = 280
    close = pd.Series(np.linspace(100, 150, n))
    ret = return_12m_pct(close)
    vol = annualized_volatility_12m(close)
    assert ret > 0
    assert 0 < vol < 100


def test_lvm_stop_triggers_at_minus_10():
    strat = LVMStrategyAdapter(stop_pct=10)
    dec = strat.check_open_position(score=150, profit_pct=-0.10)
    assert dec.action == 'SELL'
    assert 'LVM_STOP' in dec.reason

    hold = strat.check_open_position(score=150, profit_pct=-0.05)
    assert hold.action == 'HOLD'


def test_lvm_stop_15():
    strat = LVMStrategyAdapter(stop_pct=15)
    assert strat.check_open_position(score=1, profit_pct=-0.12).action == 'HOLD'
    assert strat.check_open_position(score=1, profit_pct=-0.16).action == 'SELL'


def test_compute_lowvol_mom_on_synthetic():
    from src.lowvol_momentum import compute_lowvol_mom_score

    n = 60
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        'symbol': [f'S{i}' for i in range(n)],
        'current_price': rng.uniform(100, 500, n),
        'legacy_sma_50': rng.uniform(90, 400, n),
        'price_change_1y': rng.uniform(-10, 80, n),
        'volatility_6m': rng.uniform(10, 50, n),
        'sector': [f'Sec{i % 8}' for i in range(n)],
    })
    df.loc[:5, 'current_price'] = df.loc[:5, 'legacy_sma_50'] * 1.1
    out = compute_lowvol_mom_score(df)
    elig = out['lowvol_mom_eligible'].fillna(False).sum()
    assert elig == 10
