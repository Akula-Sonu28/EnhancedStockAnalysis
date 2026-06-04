"""Technical indicators computed from OHLCV.

Goal: produce the `stock_data` dict that the v1 scoring engine's
calculate_* functions consume, using ONLY historical OHLCV.

Fields produced (only those that v2's non-zero-weighted components read):
    momentum_technical -> real_rsi, enhanced_price_change_20d, current_price,
                          sma_50, enhanced_macd_histogram, enhanced_stoch_k
    volume_strength    -> enhanced_volume_ratio, volume_quality
    multi_timeframe    -> mtf_timeframe_agreement, mtf_trend_strength,
                          mtf_composite_score, mtf_momentum_strength
    risk_adjustment    -> volatility, beta, max_drawdown_6m,
                          52_week_high, current_price

Components with zero v2 weight (fundamental_quality, growth, value,
ml_signal) are filled with neutral defaults — they have no impact.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd


# --- Primitive indicators -------------------------------------------------

def rsi_14(close: pd.Series, length: int = 14) -> float:
    if len(close) < length + 1:
        return 50.0
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else 50.0


def macd_histogram(close: pd.Series,
                   fast: int = 12, slow: int = 26, signal: int = 9) -> float:
    if len(close) < slow + signal:
        return 0.0
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = (macd - sig).iloc[-1]
    return float(hist) if pd.notna(hist) else 0.0


def stochastic_k(high: pd.Series, low: pd.Series, close: pd.Series,
                 length: int = 14) -> float:
    if len(close) < length:
        return 50.0
    hh = high.rolling(length).max().iloc[-1]
    ll = low.rolling(length).min().iloc[-1]
    if pd.isna(hh) or pd.isna(ll) or hh == ll:
        return 50.0
    k = (close.iloc[-1] - ll) / (hh - ll) * 100.0
    return float(np.clip(k, 0, 100))


def sma(close: pd.Series, length: int) -> float:
    if len(close) < length:
        return float(close.iloc[-1])
    return float(close.iloc[-length:].mean())


def annualized_volatility_20d(close: pd.Series) -> float:
    if len(close) < 22:
        return 25.0
    rets = close.pct_change().dropna().iloc[-20:]
    if rets.empty:
        return 25.0
    return float(rets.std() * np.sqrt(252) * 100)  # percent


def annualized_volatility_12m(close: pd.Series, lookback: int = 252) -> float:
    """12-month daily-return std, annualized (percent). Used for LVM backtests."""
    if len(close) < 60:
        return 999.0
    rets = close.pct_change().dropna()
    window = rets.iloc[-lookback:] if len(rets) >= lookback else rets
    if window.empty or len(window) < 20:
        return 999.0
    return float(window.std() * np.sqrt(252) * 100)


def return_12m_pct(close: pd.Series, lookback: int = 252) -> float:
    """Total return over ~12 months (percent)."""
    if len(close) < 22:
        return -999.0
    idx = -lookback if len(close) >= lookback else 0
    base = float(close.iloc[idx])
    if base <= 0:
        return -999.0
    return float((close.iloc[-1] / base - 1.0) * 100.0)


def beta_vs(nifty: pd.Series, stock_close: pd.Series, window: int = 60) -> float:
    if len(stock_close) < window or len(nifty) < window:
        return 1.0
    sc = stock_close.iloc[-window:].pct_change().dropna()
    nc = nifty.iloc[-window:].pct_change().dropna()
    df = pd.concat([sc, nc], axis=1, join='inner').dropna()
    if len(df) < 5 or df.iloc[:, 1].var() == 0:
        return 1.0
    cov = df.iloc[:, 0].cov(df.iloc[:, 1])
    var = df.iloc[:, 1].var()
    return float(cov / var)


def max_drawdown_pct(close: pd.Series, lookback_days: int = 126) -> float:
    """6-month (126 trading days) peak-to-trough drawdown in %."""
    if len(close) < 2:
        return 0.0
    s = close.iloc[-lookback_days:]
    peak = s.cummax()
    dd = (s - peak) / peak
    if dd.empty:
        return 0.0
    return float(dd.min() * 100)


def week_52_high(close: pd.Series) -> float:
    if close.empty:
        return float('nan')
    s = close.iloc[-252:] if len(close) >= 252 else close
    return float(s.max())


# --- Volume features ------------------------------------------------------

def volume_ratio(volume: pd.Series, length: int = 20) -> float:
    if len(volume) < length:
        return 1.0
    avg = volume.iloc[-length:].mean()
    if avg <= 0:
        return 1.0
    return float(volume.iloc[-1] / avg)


def volume_quality(volume: pd.Series, length: int = 20) -> str:
    """Categorical: LOW / MODERATE / HIGH based on coefficient of variation."""
    if len(volume) < length:
        return 'MODERATE'
    s = volume.iloc[-length:]
    mean = s.mean()
    if mean <= 0:
        return 'LOW'
    cov = s.std() / mean
    if cov > 2.0:
        return 'LOW'
    if cov < 0.6:
        return 'HIGH'
    return 'MODERATE'


# --- Multi-timeframe agreement -------------------------------------------

def mtf_features(close: pd.Series) -> dict:
    """Daily / weekly / monthly trend alignment, each 0-100."""
    out = {
        'mtf_timeframe_agreement': 50.0,
        'mtf_trend_strength': 50.0,
        'mtf_composite_score': 50.0,
        'mtf_momentum_strength': 50.0,
    }
    if len(close) < 60:
        return out

    daily_trend = 1 if close.iloc[-1] > sma(close, 50) else 0
    weekly = close.resample('W').last().dropna()
    monthly = close.resample('M').last().dropna()
    if len(weekly) >= 10:
        w_trend = 1 if weekly.iloc[-1] > weekly.iloc[-10:].mean() else 0
    else:
        w_trend = daily_trend
    if len(monthly) >= 6:
        m_trend = 1 if monthly.iloc[-1] > monthly.iloc[-6:].mean() else 0
    else:
        m_trend = daily_trend

    aligned = daily_trend + w_trend + m_trend
    out['mtf_timeframe_agreement'] = aligned / 3.0 * 100.0

    # Trend strength: how far above SMA, normalized
    sma50 = sma(close, 50)
    if sma50 > 0:
        dist = (close.iloc[-1] - sma50) / sma50 * 100  # percent
        out['mtf_trend_strength'] = float(np.clip(50.0 + dist * 2, 0, 100))

    # Momentum strength: 20-day return rescaled
    if len(close) >= 21:
        ret_20 = (close.iloc[-1] / close.iloc[-21] - 1) * 100
        out['mtf_momentum_strength'] = float(np.clip(50.0 + ret_20 * 2.5, 0, 100))

    out['mtf_composite_score'] = float(np.mean([
        out['mtf_timeframe_agreement'],
        out['mtf_trend_strength'],
        out['mtf_momentum_strength'],
    ]))
    return out


# --- Master builder -------------------------------------------------------

def build_stock_data(symbol: str, ohlcv: pd.DataFrame,
                     nifty_close: Optional[pd.Series],
                     on_date: date,
                     use_pit_fundamentals: bool = False) -> Optional[dict]:
    """Build the dict v1 engine functions expect, evaluated AS OF `on_date`.

    Args:
        ohlcv: OHLCV DataFrame indexed by tz-naive date, with at least
               60 trading rows ending on or before `on_date`.
        nifty_close: optional Nifty close series for beta computation
                     (same date range as ohlcv).
        on_date: the decision date; we ignore any rows AFTER this date.
        use_pit_fundamentals: if True, replace neutral fundamental defaults
            with point-in-time data from Screener.in cache.

    Returns:
        dict or None if insufficient data.
    """
    cutoff = pd.Timestamp(on_date)
    df = ohlcv[ohlcv.index <= cutoff]
    if len(df) < 60:
        return None
    close = df['Close'].astype(float)
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    volume = df['Volume'].astype(float)

    current_price = float(close.iloc[-1])
    if current_price <= 0:
        return None

    nifty = None
    if nifty_close is not None:
        nifty = nifty_close[nifty_close.index <= cutoff]

    sd: dict = {
        'symbol': symbol,
        'current_price': current_price,

        # momentum_technical inputs
        'real_rsi': rsi_14(close),
        'enhanced_price_change_20d': (
            (close.iloc[-1] / close.iloc[-21] - 1) * 100
            if len(close) >= 21 else 0.0
        ),
        'sma_50': sma(close, 50),
        'enhanced_macd_histogram': macd_histogram(close),
        'enhanced_stoch_k': stochastic_k(high, low, close),

        # volume_strength inputs
        'enhanced_volume_ratio': volume_ratio(volume),
        'volume_quality': volume_quality(volume),

        # risk_adjustment inputs
        'volatility': annualized_volatility_20d(close),
        'beta': beta_vs(nifty, close) if nifty is not None else 1.0,
        'max_drawdown_6m': max_drawdown_pct(close, lookback_days=126),
        '52_week_high': week_52_high(close),

        # ml_signal: no historical model. Set neutral so the v1 function
        # returns 50 (function checks `ml_model_source == 'trained_model'`).
        'ml_model_source': 'not_trained',
        'ml_confidence': 0,
        'ml_expected_return': 0,
        'ml_signal': 'HOLD',

        # fundamental/growth/value: neutral defaults (overridden below if PIT enabled)
        'pe_ratio': 20.0,
        'roe': 15.0,
        'debt_to_equity': 50.0,
        'market_cap': 1e10,
        'earnings_growth': 0.0,
        'revenue_growth': 0.0,
        'pb_ratio': 2.0,
        'dividend_yield': 0.0,
    }

    sd.update(mtf_features(close))

    if use_pit_fundamentals:
        from .fundamentals_pit import get_fundamental_lookup
        pit = get_fundamental_lookup().lookup(symbol, on_date, price=current_price)
        sd['pe_ratio'] = pit.get('pe_ratio', sd['pe_ratio'])
        sd['pb_ratio'] = pit.get('pb_ratio', sd['pb_ratio'])
        sd['roe'] = pit.get('roe', sd['roe'])
        sd['debt_to_equity'] = pit.get('debt_to_equity', sd['debt_to_equity'])
        sd['earnings_growth'] = pit.get('earnings_growth', sd['earnings_growth'])
        sd['revenue_growth'] = pit.get('revenue_growth', sd['revenue_growth'])

    return sd
