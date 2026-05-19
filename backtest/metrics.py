"""Performance + risk metrics.

All inputs are simple Python types or pandas series. The point is that the
engine builds an equity curve `pd.Series indexed by date` and this module
gives you the report-ready numbers.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def daily_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def cagr(equity: pd.Series) -> float:
    if equity.empty or len(equity) < 2:
        return 0.0
    start, end = equity.iloc[0], equity.iloc[-1]
    if start <= 0:
        return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    years = days / 365.25
    return float((end / start) ** (1 / years) - 1)


def total_return(equity: pd.Series) -> float:
    if equity.empty or equity.iloc[0] <= 0:
        return 0.0
    return float(equity.iloc[-1] / equity.iloc[0] - 1)


def annualized_volatility(equity: pd.Series) -> float:
    r = daily_returns(equity)
    if r.empty:
        return 0.0
    return float(r.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def sharpe(equity: pd.Series, risk_free_annual: float = 0.07) -> float:
    r = daily_returns(equity)
    if r.empty or r.std() == 0:
        return 0.0
    excess = r - (risk_free_annual / TRADING_DAYS_PER_YEAR)
    return float(excess.mean() / r.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def rolling_sharpe(
    df: pd.DataFrame,
    window: int = 30,
    risk_free_annual: float = 0.07,
) -> pd.Series:
    """Trailing rolling annualised Sharpe of an equal-weight portfolio.

    Each column of `df` is one holding's simple daily return. Portfolio
    return at t is the cross-sectional mean across columns; Sharpe at t is
    computed over the trailing `window` observations using the same formula
    as `sharpe()` — excess_mean / std * sqrt(TRADING_DAYS_PER_YEAR).

    The first `window - 1` entries are NaN. Windows where the portfolio
    return has zero std (constant series) also yield NaN; callers should
    `.dropna()` if a clean series is required. If the caller has already
    aggregated holdings into a single portfolio return series, pass it as
    a single-column DataFrame.
    """
    if df is None or df.empty:
        return pd.Series(dtype='float64', name='rolling_sharpe')
    if window < 2:
        raise ValueError(f'window must be >= 2, got {window}')

    portfolio_returns = df.mean(axis=1)
    daily_rf = risk_free_annual / TRADING_DAYS_PER_YEAR
    excess = portfolio_returns - daily_rf
    rolling_mean = excess.rolling(window).mean()
    rolling_std = portfolio_returns.rolling(window).std()
    out = (rolling_mean / rolling_std) * np.sqrt(TRADING_DAYS_PER_YEAR)
    out = out.replace([np.inf, -np.inf], np.nan)
    return out.rename('rolling_sharpe')


def sortino(equity: pd.Series, risk_free_annual: float = 0.07) -> float:
    r = daily_returns(equity)
    if r.empty:
        return 0.0
    excess = r - (risk_free_annual / TRADING_DAYS_PER_YEAR)
    downside = r[r < 0]
    if downside.empty or downside.std() == 0:
        return 0.0
    return float(excess.mean() / downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def max_drawdown(equity: pd.Series) -> tuple[float, Optional[date], Optional[date]]:
    """Return (max_dd_pct as negative number, peak_date, trough_date)."""
    if equity.empty:
        return 0.0, None, None
    peak = equity.expanding().max()
    dd = (equity - peak) / peak
    if dd.empty:
        return 0.0, None, None
    trough_idx = dd.idxmin()
    max_dd = float(dd.min())
    peak_idx = equity.loc[:trough_idx].idxmax()
    return max_dd, peak_idx.date() if hasattr(peak_idx, 'date') else peak_idx, \
           trough_idx.date() if hasattr(trough_idx, 'date') else trough_idx


def calmar(equity: pd.Series) -> float:
    c = cagr(equity)
    mdd, _, _ = max_drawdown(equity)
    if mdd == 0:
        return 0.0
    return float(c / abs(mdd))


def win_rate_from_trades(trades: list[dict]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get('net_pl', 0) > 0)
    return wins / len(trades) * 100


def avg_win_avg_loss(trades: list[dict]) -> tuple[float, float, float]:
    wins = [t['net_pl'] for t in trades if t.get('net_pl', 0) > 0]
    losses = [t['net_pl'] for t in trades if t.get('net_pl', 0) <= 0]
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else 0.0
    return avg_win, avg_loss, profit_factor


def turnover_pct(trades: list[dict], avg_equity: float) -> float:
    """Sum of turnover / avg equity, annualized roughly by run length."""
    if not trades or avg_equity <= 0:
        return 0.0
    total_turnover = sum(t.get('qty', 0) * t.get('exit_price', 0) for t in trades)
    total_turnover += sum(t.get('qty', 0) * t.get('entry_price', 0) for t in trades)
    return total_turnover / avg_equity * 100


def summarize(equity: pd.Series, trades: list[dict],
              initial_capital: float, benchmark: Optional[pd.Series] = None,
              risk_free_annual: float = 0.07) -> dict:
    """Build a metrics dict ready for the report writer."""
    mdd, mdd_peak, mdd_trough = max_drawdown(equity)
    avg_w, avg_l, pf = avg_win_avg_loss(trades)
    summary = {
        'initial_capital':       float(initial_capital),
        'final_equity':          float(equity.iloc[-1]) if not equity.empty else float(initial_capital),
        'total_return_pct':      total_return(equity) * 100,
        'cagr_pct':              cagr(equity) * 100,
        'volatility_pct':        annualized_volatility(equity) * 100,
        'sharpe':                sharpe(equity, risk_free_annual),
        'sortino':               sortino(equity, risk_free_annual),
        'calmar':                calmar(equity),
        'max_drawdown_pct':      mdd * 100,
        'max_dd_peak_date':      str(mdd_peak) if mdd_peak else None,
        'max_dd_trough_date':    str(mdd_trough) if mdd_trough else None,
        'trades_total':          len(trades),
        'trades_win_rate_pct':   win_rate_from_trades(trades),
        'avg_win_inr':           avg_w,
        'avg_loss_inr':          avg_l,
        'profit_factor':         pf,
        'turnover_pct_of_avg_eq': turnover_pct(
            trades,
            float(equity.mean()) if not equity.empty else initial_capital,
        ),
    }
    if benchmark is not None and not benchmark.empty:
        b_ret = total_return(benchmark) * 100
        b_cagr = cagr(benchmark) * 100
        b_mdd, _, _ = max_drawdown(benchmark)
        summary['benchmark_total_return_pct'] = b_ret
        summary['benchmark_cagr_pct'] = b_cagr
        summary['benchmark_max_dd_pct'] = b_mdd * 100
        summary['excess_return_pct'] = summary['total_return_pct'] - b_ret
    return summary
