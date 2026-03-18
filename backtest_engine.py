#!/usr/bin/env python3
"""
Backtest Engine — Walk-forward portfolio simulation using the Hybrid V5.1 scoring engine.

Enhanced version with:
  - Adaptive regime detection per rebalance
  - Fundamentals enrichment (ticker.info)
  - Crisis adjustment from historical cross-asset data
  - Sector performance adjustment from historical sector indices
  - Data quality scoring
  - Zerodha transaction cost model
  - Score-proportional (rank-based) allocation

Usage:
    python backtest_engine.py --months 36 --top 20 --rebalance monthly
"""

import sys
import os
sys.path.append('src')
sys.path.append('.')

import argparse
import logging
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.WARNING)

from hybrid_optimized_scoring import HybridOptimizedScoringEngine
from adaptive_market_strategy import AdaptiveMarketRegimeStrategy
from crisis_detector import CrisisDetector


def _safe(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Sector index map (same as analyze_top200_stocks_enhanced._SECTOR_INDEX_MAP)
# ---------------------------------------------------------------------------
SECTOR_INDEX_MAP = {
    'banking': '^NSEBANK', 'bank': '^NSEBANK',
    'financial': '^CNXFIN', 'finance': '^CNXFIN',
    'technology': '^CNXIT', 'it': '^CNXIT', 'software': '^CNXIT',
    'pharma': '^CNXPHARMA', 'healthcare': '^CNXPHARMA',
    'auto': '^CNXAUTO', 'automobile': '^CNXAUTO',
    'fmcg': '^CNXFMCG', 'consumer': '^CNXFMCG',
    'oil': '^CNXENERGY', 'energy': '^CNXENERGY', 'power': '^CNXENERGY',
    'utilities': '^CNXENERGY',
    'realty': '^CNXREALTY', 'real estate': '^CNXREALTY',
    'metal': '^CNXMETAL', 'steel': '^CNXMETAL', 'mining': '^CNXMETAL',
    'basic materials': '^CNXMETAL', 'materials': '^CNXMETAL',
    'industrials': '^CNXINFRA', 'infrastructure': '^CNXINFRA',
    'capital goods': '^CNXINFRA',
    'communication services': 'CNXMEDIA.NS', 'media': 'CNXMEDIA.NS',
    'telecom': 'CNXMEDIA.NS',
}


def build_stock_data_from_hist(symbol: str, hist: pd.DataFrame,
                               info: dict = None) -> Dict:
    """Build a stock_data dict the scoring engine can consume from raw OHLCV."""
    if hist is None or hist.empty or len(hist) < 20:
        return {}

    close = hist['Close'].dropna()
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    if close.empty:
        return {}

    cur = float(close.iloc[-1])
    high_52w = float(close.max())
    low_52w = float(close.min())

    returns = close.pct_change().dropna()
    vol_20d = float(returns.tail(20).std() * np.sqrt(252) * 100) if len(returns) >= 20 else 20.0

    sma_50 = float(close.tail(50).mean()) if len(close) >= 50 else cur
    sma_200 = float(close.tail(200).mean()) if len(close) >= 200 else cur

    rsi_14 = _compute_rsi(close, 14)
    macd_hist = _compute_macd_histogram(close)

    pct_1m = ((cur / float(close.iloc[-21])) - 1) * 100 if len(close) > 21 else 0
    pct_3m = ((cur / float(close.iloc[-63])) - 1) * 100 if len(close) > 63 else 0

    vol = hist['Volume'].tail(20)
    if isinstance(vol, pd.DataFrame):
        vol = vol.iloc[:, 0]
    vol_ratio = float(vol.iloc[-1] / vol.mean()) if vol.mean() > 0 else 1.0

    max_dd = _compute_max_drawdown(close)

    info = info or {}
    roe_raw = _safe(info.get('returnOnEquity', 0))
    roe = roe_raw * 100 if 0 < roe_raw < 1 else roe_raw

    return {
        'symbol': symbol,
        'current_price': cur,
        '52_week_high': high_52w,
        '52_week_low': low_52w,
        'volatility': vol_20d,
        'volatility_20d': vol_20d,
        'enhanced_rsi_14': rsi_14,
        'rsi': rsi_14,
        'enhanced_macd_histogram': macd_hist,
        'enhanced_price_change_20d': pct_1m,
        'price_change_1m': pct_1m,
        'price_change_3m': pct_3m,
        'sma_50': sma_50,
        'ma_50': sma_50,
        'sma_200': sma_200,
        'enhanced_volume_ratio': vol_ratio,
        'volume_ratio': vol_ratio,
        'max_drawdown_6m': max_dd,
        'beta': _safe(info.get('beta'), 1.0),
        'pe_ratio': _safe(info.get('trailingPE'), 15),
        'pb_ratio': _safe(info.get('priceToBook'), 2.0),
        'roe': roe,
        'debt_to_equity': _safe(info.get('debtToEquity'), 50),
        'market_cap': _safe(info.get('marketCap'), 1e10),
        'revenue_growth': _safe(info.get('revenueGrowth'), 0),
        'profit_margin': _safe(info.get('profitMargins'), 0),
        'sector': info.get('sector', ''),
        'industry': info.get('industry', ''),
        'enhanced_stoch_k': 50,
        'mtf_timeframe_agreement': 0,
        'mtf_trend_strength': 0,
        'mtf_composite_score': 0,
        'mtf_momentum_strength': 0,
        'mtf_analysis_status': 'unavailable',
        'ml_model_source': None,
    }


def _compute_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1] if not rsi.empty else 50.0
    return 50.0 if (np.isnan(val) or val == 0) else float(val)


def _compute_macd_histogram(close: pd.Series) -> float:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    val = hist.iloc[-1] if not hist.empty else 0
    return 0 if np.isnan(val) else float(val)


def _compute_max_drawdown(close: pd.Series) -> float:
    peak = close.expanding().max()
    dd = (close - peak) / peak
    return abs(float(dd.min())) * 100 if not dd.empty else 0


# ---------------------------------------------------------------------------
# Data quality scoring (mirrors analyze_top200_stocks_enhanced logic)
# ---------------------------------------------------------------------------
def _compute_data_quality(sd: Dict) -> float:
    """Compute data quality score (0-100). Baseline 70, earn up via field presence."""
    score = 70.0
    for field in ('current_price', 'market_cap', 'pe_ratio', 'pb_ratio',
                  'roe', 'debt_to_equity', 'revenue_growth', 'profit_margin',
                  'sma_50', 'sma_200', 'volatility', '52_week_high', '52_week_low'):
        val = sd.get(field)
        if val is not None and val != 0:
            score += 2.0

    pe = _safe(sd.get('pe_ratio'), 0)
    roe = _safe(sd.get('roe'), 0)
    mcap = _safe(sd.get('market_cap'), 0)

    if pe < 0 and roe > 0:
        score -= 10
    if mcap < 1e9 and pe > 50:
        score -= 10
    if sd.get('revenue_growth', 0) == 0 and sd.get('profit_margin', 0) == 0:
        score -= 5

    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# Transaction cost model (Zerodha delivery)
# ---------------------------------------------------------------------------
def _zerodha_cost(trade_value: float, is_sell: bool = False) -> float:
    """Compute Zerodha delivery trade costs for a single leg.

    Components:
      - Brokerage: min(0.03% of value, Rs 20)
      - STT: 0.1% on sell side only (delivery)
      - Exchange txn charges: 0.00345% (NSE)
      - GST: 18% on (brokerage + exchange charges)
      - Stamp duty: 0.015% on buy side only
      - SEBI turnover fee: 0.0001%
    """
    brokerage = min(trade_value * 0.0003, 20.0)
    stt = trade_value * 0.001 if is_sell else 0.0
    exchange = trade_value * 0.0000345
    gst = (brokerage + exchange) * 0.18
    stamp = trade_value * 0.00015 if not is_sell else 0.0
    sebi = trade_value * 0.000001
    return brokerage + stt + exchange + gst + stamp + sebi


# ---------------------------------------------------------------------------
# Crisis detection from historical data
# ---------------------------------------------------------------------------
def _detect_crisis_from_data(crisis_assets: Dict[str, pd.DataFrame],
                             as_of: pd.Timestamp) -> Dict:
    """Replicate CrisisDetector.detect() logic using pre-downloaded data."""

    def _pct_change(df, days=1):
        if df is None or df.empty:
            return 0.0
        sliced = df[df.index <= as_of]
        if len(sliced) < days + 1:
            return 0.0
        c = sliced['Close']
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        today = float(c.iloc[-1])
        prev = float(c.iloc[-(days + 1)])
        return ((today - prev) / prev * 100) if prev != 0 else 0.0

    nifty_chg = _pct_change(crisis_assets.get('nifty'), 1)
    crude_chg = _pct_change(crisis_assets.get('crude'), 5)
    gold_chg = _pct_change(crisis_assets.get('gold'), 5)
    usdinr_chg = _pct_change(crisis_assets.get('usdinr'), 5)
    sp500_chg = _pct_change(crisis_assets.get('sp500'), 5)

    vix_spike = 0.0
    vix_abs = 15.0
    vix_df = crisis_assets.get('vix')
    if vix_df is not None and not vix_df.empty:
        vs = vix_df[vix_df.index <= as_of]
        c = vs['Close'] if 'Close' in vs.columns else pd.Series(dtype=float)
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        if len(c) >= 5:
            avg5 = float(c.iloc[-5:-1].mean())
            now = float(c.iloc[-1])
            vix_spike = ((now - avg5) / avg5 * 100) if avg5 > 0 else 0.0
            vix_abs = now

    signals = {
        'nifty': {'value': 0, 'change_pct': round(nifty_chg, 3)},
        'crude': {'value': 0, 'change_pct': round(crude_chg, 3)},
        'gold': {'value': 0, 'change_pct': round(gold_chg, 3)},
        'usdinr': {'value': 0, 'change_pct': round(usdinr_chg, 3)},
        'sp500': {'value': 0, 'change_pct': round(sp500_chg, 3)},
        'vix_spike_pct': round(vix_spike, 1),
        'vix_absolute': round(vix_abs, 2),
    }

    # Classification (same logic as CrisisDetector._classify_event)
    if crude_chg > 3.0 and gold_chg > 1.0 and usdinr_chg > 0.3:
        crisis_type = 'GEOPOLITICAL_WAR'
    elif crude_chg > 5.0 and gold_chg < 1.0:
        crisis_type = 'OIL_SHOCK'
    elif sp500_chg < -2.0 and nifty_chg < -1.5 and crude_chg < 2.0:
        crisis_type = 'US_MARKET_CRISIS'
    elif usdinr_chg > 1.5 and nifty_chg < -1.0:
        crisis_type = 'CURRENCY_CRISIS'
    elif vix_spike > 30.0 and nifty_chg < -2.0:
        crisis_type = 'MARKET_PANIC'
    else:
        crisis_type = 'NONE'

    # Severity (same logic as CrisisDetector._calculate_severity)
    severity = 0
    if crisis_type != 'NONE':
        nd = abs(nifty_chg)
        cm = abs(crude_chg)
        s = 0
        if nd > 3: s += 3
        elif nd > 2: s += 2
        elif nd > 1: s += 1
        if vix_spike > 50: s += 2
        elif vix_spike > 30: s += 1
        if cm > 8: s += 2
        elif cm > 4: s += 1
        severity = 3 if s >= 5 else (2 if s >= 3 else 1)

    return {
        'crisis_detected': crisis_type != 'NONE',
        'crisis_type': crisis_type,
        'severity': severity,
        'severity_label': ['NONE', 'MILD', 'MODERATE', 'SEVERE'][min(severity, 3)],
        'description': crisis_type,
        'sector_adjustments': CrisisDetector.SECTOR_RULES.get(crisis_type, {}),
        'signals': signals,
        'timestamp': str(as_of),
    }


# ---------------------------------------------------------------------------
# Sector performance adjustment from historical data
# ---------------------------------------------------------------------------
def _compute_sector_adj(sector: str, nifty_hist: pd.DataFrame,
                        sector_hist_cache: Dict[str, pd.DataFrame],
                        as_of: pd.Timestamp) -> float:
    """Compute sector vs Nifty relative return adjustment."""
    sector_lower = str(sector or '').lower()
    ticker = None
    for key, val in SECTOR_INDEX_MAP.items():
        if key in sector_lower:
            ticker = val
            break
    if not ticker:
        return 0.0

    sh = sector_hist_cache.get(ticker)
    if sh is None or sh.empty:
        return 0.0

    lookback_3m = as_of - timedelta(days=90)

    nh = nifty_hist[(nifty_hist.index >= lookback_3m) & (nifty_hist.index <= as_of)]
    si = sh[(sh.index >= lookback_3m) & (sh.index <= as_of)]

    nc = nh['Close'] if not nh.empty else pd.Series(dtype=float)
    sc = si['Close'] if not si.empty else pd.Series(dtype=float)
    if isinstance(nc, pd.DataFrame):
        nc = nc.iloc[:, 0]
    if isinstance(sc, pd.DataFrame):
        sc = sc.iloc[:, 0]

    if nc.empty or sc.empty or len(nc) < 5 or len(sc) < 5:
        return 0.0

    n0 = float(nc.iloc[0])
    s0 = float(sc.iloc[0])
    if n0 == 0 or s0 == 0 or np.isnan(n0) or np.isnan(s0):
        return 0.0

    nifty_ret = (float(nc.iloc[-1]) / n0 - 1) * 100
    sector_ret = (float(sc.iloc[-1]) / s0 - 1) * 100
    relative = sector_ret - nifty_ret
    return round(max(-3.0, min(3.0, relative * 0.3)), 2)


class BacktestResult:
    def __init__(self):
        self.equity_curve: List[Dict] = []
        self.trades: List[Dict] = []
        self.metrics: Dict = {}
        self.benchmark_curve: List[Dict] = []
        self.regime_log: List[Dict] = []

    def to_summary_df(self) -> pd.DataFrame:
        rows = []
        for k, v in self.metrics.items():
            rows.append({'Metric': k, 'Value': v})
        return pd.DataFrame(rows)

    def to_equity_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.equity_curve)


class BacktestEngine:
    def __init__(self):
        self.scorer = HybridOptimizedScoringEngine()
        self.adaptive_strategy = AdaptiveMarketRegimeStrategy()
        self.crisis_detector = CrisisDetector()

    @staticmethod
    def _detect_regime_from_data(nifty_df: pd.DataFrame) -> str:
        """Detect market regime from historical Nifty OHLCV data.

        Replicates the MarketRegimeDetector signal logic (trend + momentum +
        volatility + breadth) so the backtest can classify regime at each
        historical rebalance point without making live API calls.

        Returns one of: 'BULL', 'BEAR', 'SIDEWAYS'.
        """
        if nifty_df is None or nifty_df.empty or len(nifty_df) < 50:
            return 'SIDEWAYS'

        close = nifty_df['Close'].dropna()
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if len(close) < 50:
            return 'SIDEWAYS'

        ma_20 = close.rolling(20).mean()
        ma_50 = close.rolling(50).mean()
        ma_100 = close.rolling(100).mean()
        ma_200 = close.rolling(200).mean() if len(close) >= 200 else ma_100
        cur = float(close.iloc[-1])
        trend = 0.0
        trend += 0.25 if cur > float(ma_20.iloc[-1]) else -0.25
        trend += 0.25 if cur > float(ma_50.iloc[-1]) else -0.25
        trend += 0.25 if float(ma_50.iloc[-1]) > float(ma_100.iloc[-1]) else -0.25
        if len(ma_200) > 0:
            trend += 0.25 if float(ma_100.iloc[-1]) > float(ma_200.iloc[-1]) else -0.25
        else:
            trend -= 0.25

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1]) if not rsi.empty and not np.isnan(rsi.iloc[-1]) else 50.0
        rsi_score = (rsi_val - 50) / 50

        close_20 = float(close.iloc[-20]) if len(close) >= 20 else float(close.iloc[0])
        close_20 = close_20 if close_20 != 0 else 1.0
        roc_20 = ((cur - close_20) / close_20) * 100
        roc_score = float(np.clip(roc_20 / 10, -1.0, 1.0))
        momentum = rsi_score * 0.6 + roc_score * 0.4

        rets = close.pct_change()
        vol_series = rets.rolling(20).std() * np.sqrt(252) * 100
        cur_vol = float(vol_series.iloc[-1]) if not np.isnan(vol_series.iloc[-1]) else 0
        avg_vol = float(vol_series.mean()) if not np.isnan(vol_series.mean()) else 1
        if avg_vol == 0:
            avg_vol = 1.0
        if cur_vol < avg_vol * 0.8:
            volatility = 1.0
        elif cur_vol < avg_vol:
            volatility = 0.5
        elif cur_vol < avg_vol * 1.2:
            volatility = -0.5
        else:
            volatility = -1.0

        sma50 = close.rolling(50).mean()
        recent_n = min(20, len(close) - 50) if len(close) > 50 else 0
        if recent_n > 0:
            rc = close.iloc[-recent_n:]
            rs2 = sma50.iloc[-recent_n:]
            valid = rs2.notna()
            pct_above = (rc[valid] > rs2[valid]).sum() / valid.sum() if valid.sum() > 0 else 0.5
            breadth = (pct_above - 0.5) * 2.0
        else:
            breadth = 0.0

        regime_score = (
            trend * 0.35 +
            float(np.clip(momentum, -1, 1)) * 0.25 +
            volatility * 0.20 +
            float(np.clip(breadth, -1, 1)) * 0.20
        )
        regime_score = max(-1.0, min(1.0, regime_score))

        if regime_score > 0.5:
            return 'BULL'
        elif regime_score < -0.5:
            return 'BEAR'
        return 'SIDEWAYS'

    def run_backtest(self, symbols: List[str], lookback_months: int = 12,
                     top_n: int = 20, rebalance_freq: str = 'monthly',
                     initial_capital: float = 1_000_000) -> BacktestResult:

        result = BacktestResult()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_months * 30)
        download_start = (start_date - timedelta(days=400)).strftime('%Y-%m-%d')
        download_end = end_date.strftime('%Y-%m-%d')

        print(f"\n{'='*70}")
        print(f"BACKTEST ENGINE — Enhanced Walk-Forward Simulation")
        print(f"{'='*70}")
        print(f"  Period     : {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"  Symbols    : {len(symbols)}")
        print(f"  Top N      : {top_n}")
        print(f"  Rebalance  : {rebalance_freq}")
        print(f"  Capital    : Rs {initial_capital:,.0f}")
        print(f"  Adaptive   : YES (regime-based weights)")
        print(f"  Costs      : Zerodha delivery model")
        print(f"  Allocation : Power-2 spread (score-weighted)")
        print(f"  Stop-Loss  : -10% per stock (daily check)")
        print(f"  Cash Res.  : 50% after -5% month, 75% after -3%")
        print(f"  Sector Cap : Max 5 stocks per sector")
        print(f"  Turnover   : +3 pt loyalty bonus for held stocks")
        print(f"  Pipeline   : hybrid + crisis + quality + sector adj")
        print(f"{'='*70}\n")

        # ── 1. Download stock OHLCV ──────────────────────────────────────────
        print("  Downloading stock OHLCV data...")
        ns_symbols = [s + '.NS' if not s.endswith('.NS') else s for s in symbols]
        try:
            bulk = yf.download(
                ns_symbols,
                start=download_start, end=download_end,
                group_by='ticker', progress=False, threads=True
            )
        except Exception as e:
            print(f"  [FAIL] Data download failed: {e}")
            return result

        # ── 2. Fetch fundamentals (ticker.info) once per symbol ──────────────
        print("  Fetching fundamentals (ticker.info)...")
        info_cache: Dict[str, dict] = {}
        for sym in symbols:
            ns = sym + '.NS' if not sym.endswith('.NS') else sym
            try:
                info_cache[sym] = yf.Ticker(ns).info or {}
            except Exception:
                info_cache[sym] = {}
        funded = sum(1 for v in info_cache.values() if v.get('sector'))
        print(f"  Fundamentals loaded: {funded}/{len(symbols)} with sector data")

        # ── 3. Download Nifty + crisis assets ────────────────────────────────
        print("  Downloading Nifty + crisis assets...")
        crisis_tickers = {
            'nifty': '^NSEI', 'vix': '^INDIAVIX', 'crude': 'BZ=F',
            'gold': 'GC=F', 'usdinr': 'USDINR=X', 'sp500': '^GSPC',
        }
        crisis_assets: Dict[str, pd.DataFrame] = {}
        nifty_hist = pd.DataFrame()
        for name, ticker in crisis_tickers.items():
            try:
                df = yf.download(ticker, start=download_start, end=download_end,
                                 progress=False)
                crisis_assets[name] = df
                if name == 'nifty':
                    nifty_hist = df
            except Exception:
                crisis_assets[name] = pd.DataFrame()

        # ── 4. Download sector indices ───────────────────────────────────────
        print("  Downloading sector indices...")
        unique_sector_tickers = set(SECTOR_INDEX_MAP.values())
        sector_hist_cache: Dict[str, pd.DataFrame] = {}
        for stk in unique_sector_tickers:
            try:
                sector_hist_cache[stk] = yf.download(
                    stk, start=download_start, end=download_end, progress=False)
            except Exception:
                sector_hist_cache[stk] = pd.DataFrame()
        print(f"  Sector indices loaded: {sum(1 for v in sector_hist_cache.values() if not v.empty)}"
              f"/{len(unique_sector_tickers)}")

        # ── 5. Run walk-forward simulation ───────────────────────────────────
        rebalance_days = 30 if rebalance_freq == 'monthly' else 7
        dates = pd.date_range(start=start_date, end=end_date, freq=f'{rebalance_days}D')

        capital = initial_capital
        prev_portfolio_symbols: set = set()
        regime_log = []
        total_costs = 0.0
        total_crisis_events = 0
        total_stopped = 0

        print(f"\n  Running {len(dates)-1} rebalance periods...\n")

        for i, rebal_date in enumerate(dates[:-1]):
            next_date = dates[i + 1]

            # --- Fix 2: Drawdown-based cash reserve ---
            deploy_pct = 1.0
            if i > 0 and result.equity_curve:
                prev_return = result.equity_curve[-1]['return_pct']
                if prev_return < -5:
                    deploy_pct = 0.50
                elif prev_return < -3:
                    deploy_pct = 0.75
            deployable_capital = capital * deploy_pct

            # --- Regime detection ---
            regime = 'SIDEWAYS'
            adaptive_weights = None
            if not nifty_hist.empty:
                nifty_slice = nifty_hist[nifty_hist.index <= rebal_date].tail(260)
                regime = self._detect_regime_from_data(nifty_slice)
                adaptive_weights = self.adaptive_strategy.get_adaptive_scoring_weights(regime)

            # --- Crisis detection ---
            crisis_data = _detect_crisis_from_data(crisis_assets, rebal_date)
            crisis_tag = ''
            if crisis_data['crisis_detected']:
                total_crisis_events += 1
                crisis_tag = f"  CRISIS: {crisis_data['crisis_type']} ({crisis_data['severity_label']})"

            regime_log.append({
                'date': rebal_date.strftime('%Y-%m-%d'),
                'regime': regime,
                'crisis': crisis_data['crisis_type'],
                'crisis_severity': crisis_data['severity'],
            })
            print(f"  [{i+1}/{len(dates)-1}] {rebal_date.strftime('%Y-%m-%d')} -> "
                  f"{next_date.strftime('%Y-%m-%d')}  [Regime: {regime}]{crisis_tag}")

            # --- Score all stocks ---
            scores = {}
            stock_data_cache = {}
            for sym in symbols:
                ns = sym + '.NS' if not sym.endswith('.NS') else sym
                try:
                    if len(ns_symbols) == 1:
                        sym_hist = bulk
                    else:
                        sym_hist = bulk[ns] if ns in bulk.columns.get_level_values(0) else pd.DataFrame()

                    if isinstance(sym_hist, pd.DataFrame) and not sym_hist.empty:
                        sym_hist = sym_hist.dropna(subset=['Close'])
                        hist_slice = sym_hist[sym_hist.index <= rebal_date].tail(260)
                        if len(hist_slice) < 20:
                            continue

                        sd = build_stock_data_from_hist(sym, hist_slice, info_cache.get(sym))
                        if not sd:
                            continue
                        sd['market_regime'] = regime

                        # Hybrid score
                        res = self.scorer.calculate_hybrid_score(
                            sym, sd, adaptive_weights=adaptive_weights
                        )
                        hybrid_score = res.get('hybrid_score', 0)

                        # Crisis adjustment
                        sector_str = sd.get('sector', '')
                        crisis_adj = self.crisis_detector.get_stock_crisis_adjustment(
                            sym, sector_str, crisis_data)

                        # Data quality adjustment
                        dq = _compute_data_quality(sd)
                        quality_adj = (dq - 70) * 0.10

                        # Sector performance adjustment
                        sector_adj = _compute_sector_adj(
                            sector_str, nifty_hist, sector_hist_cache, rebal_date)

                        final_score = max(0, min(100,
                            hybrid_score + crisis_adj + quality_adj + sector_adj))

                        scores[sym] = final_score
                        stock_data_cache[sym] = {
                            'hybrid': hybrid_score, 'crisis': crisis_adj,
                            'quality': round(quality_adj, 2), 'sector': sector_adj,
                            'final': final_score,
                        }
                except Exception:
                    continue

            if not scores:
                continue

            # --- Fix 4: Loyalty bonus for held stocks (reduce turnover) ---
            LOYALTY_BONUS = 3.0
            for sym in scores:
                if sym in prev_portfolio_symbols:
                    scores[sym] += LOYALTY_BONUS

            # --- Fix 3: Sector concentration cap ---
            MAX_PER_SECTOR = 5
            ranked_all = sorted(scores.items(), key=lambda x: -x[1])
            ranked = []
            sector_count: Dict[str, int] = {}
            for sym, score in ranked_all:
                sec = (info_cache.get(sym) or {}).get('sector', 'Unknown')
                if sector_count.get(sec, 0) < MAX_PER_SECTOR:
                    ranked.append((sym, score))
                    sector_count[sec] = sector_count.get(sec, 0) + 1
                if len(ranked) >= top_n:
                    break

            # --- Fix 5: Power-2 spread for allocation weights ---
            min_score = min(s for _, s in ranked) if ranked else 0
            spread_scores = [(sym, (score - min_score + 1) ** 2) for sym, score in ranked]
            total_spread = sum(s for _, s in spread_scores)
            if total_spread <= 0:
                total_spread = 1.0

            current_symbols = set(s for s, _ in ranked)

            # --- Transaction costs for changed positions ---
            new_entries = current_symbols - prev_portfolio_symbols
            exits = prev_portfolio_symbols - current_symbols
            turnover_count = len(new_entries) + len(exits)

            new_portfolio = {}
            spread_map = {sym: sp for sym, sp in spread_scores}
            for sym, score in ranked:
                ns = sym + '.NS' if not sym.endswith('.NS') else sym
                try:
                    if len(ns_symbols) == 1:
                        sym_hist = bulk
                    else:
                        sym_hist = bulk[ns] if ns in bulk.columns.get_level_values(0) else pd.DataFrame()
                    if isinstance(sym_hist, pd.DataFrame) and not sym_hist.empty:
                        sym_hist = sym_hist.dropna(subset=['Close'])
                        prices_at = sym_hist[sym_hist.index <= rebal_date]['Close']
                        if isinstance(prices_at, pd.DataFrame):
                            prices_at = prices_at.iloc[:, 0]
                        if not prices_at.empty:
                            price = float(prices_at.iloc[-1])
                            if price > 0:
                                weight = spread_map.get(sym, 1.0) / total_spread
                                allocation = deployable_capital * weight
                                shares = allocation / price
                                new_portfolio[sym] = {
                                    'shares': shares, 'entry_price': price,
                                    'score': score, 'allocation': allocation,
                                    'weight': weight,
                                }
                except Exception:
                    continue

            # Deduct transaction costs for turnover
            period_costs = 0.0
            for sym, pos in new_portfolio.items():
                if sym in new_entries:
                    period_costs += _zerodha_cost(pos['allocation'], is_sell=False)
            avg_exit_value = capital / max(len(prev_portfolio_symbols), 1)
            for sym in exits:
                period_costs += _zerodha_cost(avg_exit_value, is_sell=True)

            capital -= period_costs
            total_costs += period_costs

            # --- Fix 1: Per-stock stop-loss + compute period returns ---
            STOP_LOSS_PCT = -0.10
            period_pnl = 0.0
            count = 0
            period_stopped = 0
            for sym, pos in new_portfolio.items():
                ns = sym + '.NS' if not sym.endswith('.NS') else sym
                try:
                    if len(ns_symbols) == 1:
                        sym_hist = bulk
                    else:
                        sym_hist = bulk[ns] if ns in bulk.columns.get_level_values(0) else pd.DataFrame()
                    if isinstance(sym_hist, pd.DataFrame) and not sym_hist.empty:
                        sym_hist = sym_hist.dropna(subset=['Close'])

                        daily_prices = sym_hist[
                            (sym_hist.index > rebal_date) & (sym_hist.index <= next_date)
                        ]['Close']
                        if isinstance(daily_prices, pd.DataFrame):
                            daily_prices = daily_prices.iloc[:, 0]
                        if daily_prices.empty:
                            continue

                        entry_price = pos['entry_price']
                        alloc = pos['allocation']
                        exit_price = None
                        was_stopped = False
                        sl_sell_cost = 0.0

                        for dt, price in daily_prices.items():
                            p = float(price) if not isinstance(price, pd.Series) else float(price.iloc[0])
                            drawdown = (p - entry_price) / entry_price
                            if drawdown <= STOP_LOSS_PCT:
                                exit_price = p
                                was_stopped = True
                                period_stopped += 1
                                sl_sell_cost = _zerodha_cost(alloc * (1 + drawdown), is_sell=True)
                                total_costs += sl_sell_cost
                                break

                        if not was_stopped:
                            end_prices = sym_hist[sym_hist.index >= next_date]['Close']
                            if isinstance(end_prices, pd.DataFrame):
                                end_prices = end_prices.iloc[:, 0]
                            if not end_prices.empty:
                                exit_price = float(end_prices.iloc[0])

                        if exit_price is not None:
                            ret = (exit_price - entry_price) / entry_price
                            pnl = alloc * ret - sl_sell_cost
                            period_pnl += pnl
                            weight = pos.get('weight', 1.0 / max(len(new_portfolio), 1))
                            count += 1
                            result.trades.append({
                                'rebalance_date': rebal_date.strftime('%Y-%m-%d'),
                                'symbol': sym,
                                'score': round(pos['score'], 1),
                                'weight_pct': round(weight * 100, 1),
                                'entry': round(entry_price, 2),
                                'exit': round(exit_price, 2),
                                'return_pct': round(ret * 100, 2),
                                'regime': regime,
                                'stopped_out': was_stopped,
                            })
                except Exception:
                    continue

            period_return_pct = (period_pnl / deployable_capital * 100) if deployable_capital > 0 else 0.0
            total_stopped += period_stopped
            capital += period_pnl
            prev_portfolio_symbols = current_symbols

            result.equity_curve.append({
                'date': rebal_date.strftime('%Y-%m-%d'),
                'capital': round(capital, 2),
                'return_pct': round(period_return_pct, 2),
                'stocks_held': count,
                'regime': regime,
                'crisis': crisis_data['crisis_type'],
                'turnover': turnover_count,
                'costs': round(period_costs, 2),
                'deploy_pct': deploy_pct,
                'stopped_out': period_stopped,
            })

        # ── Benchmark curve ──────────────────────────────────────────────────
        if not nifty_hist.empty and 'Close' in nifty_hist.columns:
            nifty_close = nifty_hist['Close'].dropna()
            if isinstance(nifty_close, pd.DataFrame):
                nifty_close = nifty_close.iloc[:, 0]
            bench_start = nifty_close[nifty_close.index >= start_date]
            if not bench_start.empty:
                nifty_start = float(bench_start.iloc[0])
                if nifty_start > 0:
                    for dt, price in bench_start.items():
                        try:
                            _p = float(price) if not isinstance(price, pd.Series) else float(price.iloc[0])
                            result.benchmark_curve.append({
                                'date': dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt),
                                'nifty_value': round(initial_capital * (_p / nifty_start), 2),
                            })
                        except (TypeError, ValueError):
                            continue

        # ── Compute summary metrics ──────────────────────────────────────────
        total_return = (capital - initial_capital) / initial_capital * 100
        eq_df = pd.DataFrame(result.equity_curve)
        if not eq_df.empty and 'return_pct' in eq_df.columns:
            rets = eq_df['return_pct'] / 100
            ann_factor = 12 if rebalance_freq == 'monthly' else 52
            sharpe = float(rets.mean() / rets.std() * np.sqrt(ann_factor)) if rets.std() > 0 else 0
            cum = (1 + rets).cumprod()
            peak = cum.expanding().max()
            dd = (cum - peak) / peak
            max_dd = float(dd.min()) * 100
        else:
            sharpe = 0
            max_dd = 0

        nifty_return = 0
        if result.benchmark_curve:
            nifty_return = (result.benchmark_curve[-1]['nifty_value'] - initial_capital) / initial_capital * 100

        regime_counts = {}
        for entry in regime_log:
            r = entry['regime']
            regime_counts[r] = regime_counts.get(r, 0) + 1
        regime_summary = ', '.join(f'{r}={c}' for r, c in sorted(regime_counts.items()))

        # Retention rate (% of held stocks that survive to next period)
        retention_rates = []
        if not eq_df.empty and 'stocks_held' in eq_df.columns:
            turnovers = eq_df['turnover'].tolist() if 'turnover' in eq_df.columns else []
            held_counts = eq_df['stocks_held'].tolist()
            for j in range(1, len(held_counts)):
                if held_counts[j] > 0 and j < len(turnovers):
                    new_entries_j = turnovers[j] / 2 if turnovers[j] > 0 else 0
                    retained = held_counts[j] - new_entries_j
                    retention_rates.append(max(0, retained / held_counts[j] * 100))
        avg_retention = sum(retention_rates) / len(retention_rates) if retention_rates else 0

        # Sector concentration from trades
        max_sector_pct = 0.0
        if result.trades:
            from collections import Counter
            for rebal_dt in set(t['rebalance_date'] for t in result.trades):
                period_trades = [t for t in result.trades if t['rebalance_date'] == rebal_dt]
                sectors = []
                for t in period_trades:
                    sym = t['symbol']
                    sec = (info_cache.get(sym) or {}).get('sector', 'Unknown')
                    sectors.append(sec)
                if sectors:
                    ctr = Counter(sectors)
                    top_pct = ctr.most_common(1)[0][1] / len(sectors) * 100
                    if top_pct > max_sector_pct:
                        max_sector_pct = top_pct

        result.metrics = {
            'Initial Capital': f'Rs {initial_capital:,.0f}',
            'Final Capital': f'Rs {capital:,.0f}',
            'Total Return': f'{total_return:.1f}%',
            'Nifty 50 Return': f'{nifty_return:.1f}%',
            'Alpha': f'{total_return - nifty_return:.1f}%',
            'Sharpe Ratio': f'{sharpe:.2f}',
            'Max Drawdown': f'{max_dd:.1f}%',
            'Total Trades': str(len(result.trades)),
            'Stop-Loss Exits': str(total_stopped),
            'Avg Retention Rate': f'{avg_retention:.0f}%',
            'Max Sector Conc.': f'{max_sector_pct:.0f}%',
            'Rebalance Periods': str(len(result.equity_curve)),
            'Transaction Costs': f'Rs {total_costs:,.0f}',
            'Crisis Events': str(total_crisis_events),
            'Regime Distribution': regime_summary,
        }
        result.regime_log = regime_log

        print(f"\n{'='*70}")
        print("  BACKTEST RESULTS (Enhanced)")
        print(f"{'='*70}")
        for k, v in result.metrics.items():
            print(f"  {k:25s}: {v}")
        print(f"{'='*70}\n")

        return result


def main():
    parser = argparse.ArgumentParser(description='Enhanced Backtest Engine')
    parser.add_argument('--months', type=int, default=12, help='Lookback months')
    parser.add_argument('--top', type=int, default=20, help='Top N stocks per rebalance')
    parser.add_argument('--rebalance', type=str, default='monthly', choices=['monthly', 'weekly'])
    parser.add_argument('--capital', type=float, default=1_000_000, help='Initial capital')
    args = parser.parse_args()

    try:
        symbols_df = pd.read_csv('stock_list_template.csv')
        col = 'Symbol' if 'Symbol' in symbols_df.columns else symbols_df.columns[0]
        symbols = symbols_df[col].dropna().str.strip().tolist()[:100]
    except Exception:
        symbols = [
            'RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY', 'SBIN',
            'BHARTIARTL', 'ITC', 'KOTAKBANK', 'LT', 'AXISBANK', 'BAJFINANCE',
            'HCLTECH', 'MARUTI', 'SUNPHARMA', 'TITAN', 'NTPC', 'COALINDIA',
            'WIPRO', 'DRREDDY',
        ]

    engine = BacktestEngine()
    result = engine.run_backtest(
        symbols=symbols,
        lookback_months=args.months,
        top_n=args.top,
        rebalance_freq=args.rebalance,
        initial_capital=args.capital,
    )

    if result.equity_curve:
        out_file = f'data/backtest_result_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        try:
            with pd.ExcelWriter(out_file, engine='xlsxwriter') as writer:
                result.to_summary_df().to_excel(writer, sheet_name='Summary', index=False)
                result.to_equity_df().to_excel(writer, sheet_name='Equity Curve', index=False)
                pd.DataFrame(result.trades).to_excel(writer, sheet_name='Trades', index=False)
                if result.benchmark_curve:
                    pd.DataFrame(result.benchmark_curve).to_excel(writer, sheet_name='Benchmark', index=False)
                if result.regime_log:
                    pd.DataFrame(result.regime_log).to_excel(writer, sheet_name='Regime Log', index=False)
            print(f"  Results saved: {out_file}")
        except Exception as e:
            print(f"  [WARN] Could not save results: {e}")


if __name__ == '__main__':
    main()
