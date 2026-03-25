#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML Model Trainer for NSE Stock Analysis
========================================
Trains the GradientBoostingClassifier in ml_predictor.py on live NSE data
and saves it to models/ml_predictor_latest.pkl so the main engine stops
using rule-based fallback.

Usage
-----
    python train_ml_model.py                    # train on full stock list (slow)
    python train_ml_model.py --stocks 50        # train on first N stocks
    python train_ml_model.py --forward-days 10  # change prediction horizon

Label definition
----------------
For each stock, we download 5Y daily history, slide a 60-day window to
build feature rows, then label each row by the 10-day (default) forward
close-to-close return:
    +1 (UP)   if fwd_return >  +2 %
    -1 (DOWN) if fwd_return <  -2 %
     0 (HOLD) otherwise

Requirements
------------
    pip install scikit-learn yfinance pandas numpy
"""

import sys, os, argparse, logging, pickle, warnings
from datetime import datetime
from pathlib import Path

sys.path.append('.')
sys.path.append('src')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score, GroupShuffleSplit, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score
from sklearn.utils.class_weight import compute_sample_weight

# ── logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/train_ml_model.log', encoding='utf-8', mode='a')
    ]
)
os.makedirs('logs', exist_ok=True)
os.makedirs('models', exist_ok=True)

logger = logging.getLogger('train_ml_model')


# ── default stock universe (top 120 liquid NSE stocks) ────────────────────────
DEFAULT_STOCKS = [
    # Mega caps & Nifty50
    'RELIANCE','TCS','HDFCBANK','ICICIBANK','INFY','HINDUNILVR','ITC','SBIN',
    'BHARTIARTL','KOTAKBANK','LT','AXISBANK','BAJFINANCE','ASIANPAINT','MARUTI',
    'HCLTECH','ULTRACEMCO','SUNPHARMA','WIPRO','TITAN','NESTLEIND','TECHM',
    'BAJAJFINSV','POWERGRID','NTPC','COALINDIA','HINDALCO','TATASTEEL','JSWSTEEL',
    'INDUSINDBK','HEROMOTOCO','M&M','TATACONSUM','DIVISLAB','BRITANNIA','DRREDDY',
    'CIPLA','HDFCLIFE','SBILIFE','BAJAJ-AUTO','EICHERMOT','SHRIRAMFIN','APOLLOHOSP',
    'ADANIENT','ADANIPORTS','GRASIM','BPCL','IOC','ONGC','VEDL',
    # Banks & Financials
    'BANKBARODA','PNB','CANBK','UNIONBANK','BANKINDIA','INDIANB','KARURVYSYA',
    'FEDERALBNK','IDFCFIRSTB','BANDHANBNK','CHOLAFIN','MUTHOOTFIN','MANAPPURAM',
    'BAJAJHLDNG','HDFC','LICSGFIN','PFC','RECLTD','IRFC','HUDCO',
    # Industrials & Infra
    'SIEMENS','ABB','HAVELLS','POLYCAB','VOLTAS','CROMPTON','WHIRLPOOL',
    'BEL','HAL','BHEL','TIINDIA','CUMMINSIND','THERMAX','GRINDWELL',
    'LTTS','LTIM','MPHASIS','PERSISTENT','COFORGE','KPIT',
    # Consumer & Retail
    'PIDILITIND','BERGEPAINT','KANSAINER','JUBLFOOD','TRENT','DMART',
    'NYKAA','ZOMATO','IRCTC','RAILTEL','RVNL','PAYTM','POLICYBZR',
    'MCDOWELL-N','RADICO','UNITDSPR','ABCAPITAL','ICICIGI','HDFCAMC',
    # Pharma & Healthcare
    'LUPIN','AUROPHARMA','GLENMARK','IPCALAB','ALKEM','TORNTPHARM',
    'APOLLOHOSP','FORTIS','MAXHEALTH','METROPOLIS',
    # Cement & Materials
    'AMBUJACEM','ACC','SHREECEM','RAMCOCEM','JKCEMENT','HEIDELBERG',
    # Energy & Utilities
    'TATAPOWER','ADANIGREEN','ADANIPOWER','TORNTPOWER','CESC',
]


# ── feature builder ────────────────────────────────────────────────────────────
def _safe(val, default=0.0):
    try:
        v = float(val)
        return default if (np.isnan(v) or np.isinf(v)) else v
    except Exception:
        return default


def build_features_from_hist(hist: pd.DataFrame, info: dict = None,
                              hist_full: pd.DataFrame = None) -> np.ndarray:
    """
    Build a 65-feature vector matching ml_predictor.prepare_features() EXACTLY.

    Groups (must stay in this order so the trained pkl works with the predictor):
      1. Technical Indicators   (20)
      2. Price Momentum         (10)
      3. Volume Patterns         (8)
      4. Fundamental Metrics    (15)  ← from ticker.info (static per stock)
      5. Sentiment & Flow        (7)  ← neutral defaults (cannot backfill)
      6. Multi-Timeframe         (5)
    Total: 65 features
    """
    if hist is None or len(hist) < 60:
        return None

    info = info or {}

    close = hist['Close'].values.astype(float)
    high  = hist['High'].values.astype(float)
    low   = hist['Low'].values.astype(float)
    vol   = hist['Volume'].values.astype(float)
    n     = len(close)
    cur   = close[-1]

    # ─── tiny helpers ─────────────────────────────────────────────────────────
    def sma(arr, p):
        return float(np.mean(arr[-p:])) if len(arr) >= p else float(np.mean(arr))

    def ema_vec(arr, span):
        alpha = 2.0 / (span + 1)
        out = np.empty(len(arr), dtype=float)
        out[0] = arr[0]
        for k in range(1, len(arr)):
            out[k] = alpha * arr[k] + (1 - alpha) * out[k - 1]
        return out

    # ─── Group 1: Technical (20) ──────────────────────────────────────────────
    # RSI(14)
    diff  = np.diff(close)
    gain  = np.where(diff > 0, diff, 0.0)
    loss  = np.where(diff < 0, -diff, 0.0)
    ag14  = np.mean(gain[-14:]) if len(gain) >= 14 else np.mean(gain)
    al14  = np.mean(loss[-14:]) if len(loss) >= 14 else np.mean(loss)
    rsi14 = 100.0 - 100.0 / (1.0 + ag14 / (al14 + 1e-9))

    # MACD(12,26) + signal(9)
    ema12    = ema_vec(close, 12)
    ema26    = ema_vec(close, 26)
    macd_arr = ema12 - ema26
    sig_arr  = ema_vec(macd_arr, 9)
    macd_val = float(macd_arr[-1])
    sig_val  = float(sig_arr[-1])

    # Bollinger Bands(20)
    ma20_v = sma(close, 20)
    std20  = float(np.std(close[-20:])) if n >= 20 else float(np.std(close))
    upper  = ma20_v + 2 * std20
    lower  = ma20_v - 2 * std20
    bb_rng = upper - lower
    bb_pos = (cur - lower) / (bb_rng + 1e-9)
    bb_wid = bb_rng / (ma20_v + 1e-9)

    # ATR(14) as % of price
    trs = [max(high[i] - low[i],
               abs(high[i] - close[i - 1]),
               abs(low[i]  - close[i - 1])) for i in range(-14, 0)]
    atr14 = np.mean(trs) / (cur + 1e-9) * 100.0

    # ADX(14) — simplified DX average
    try:
        h14 = high[-15:]; l14 = low[-15:]; c14 = close[-15:]
        pdm = np.maximum(np.diff(h14), 0)
        mdm = np.maximum(-np.diff(l14), 0)
        pdm = np.where(pdm > mdm, pdm, 0)
        mdm = np.where(mdm > pdm, mdm, 0)  # type: ignore[assignment]
        atr_s = np.mean(trs)
        pdi = 100.0 * np.mean(pdm) / (atr_s + 1e-9)
        mdi = 100.0 * np.mean(mdm) / (atr_s + 1e-9)
        adx = 100.0 * abs(pdi - mdi) / (pdi + mdi + 1e-9)
    except Exception:
        adx = 25.0

    # CCI(20)
    tp   = (high[-20:] + low[-20:] + close[-20:]) / 3.0 if n >= 20 else (high + low + close) / 3.0
    cci  = (tp[-1] - np.mean(tp)) / (0.015 * (np.mean(np.abs(tp - np.mean(tp))) + 1e-9))

    # Stochastic(14,3)
    lo14 = np.min(low[-14:])  if n >= 14 else np.min(low)
    hi14 = np.max(high[-14:]) if n >= 14 else np.max(high)
    stk  = (cur - lo14) / (hi14 - lo14 + 1e-9) * 100.0
    # %D = 3-period SMA of %K — use positive indices to avoid empty-slice edge case
    stk3 = []
    for _idx in range(n - 3, n):
        _lo = np.min(low[max(0, _idx - 13): _idx + 1])
        _hi = np.max(high[max(0, _idx - 13): _idx + 1])
        stk3.append((close[_idx] - _lo) / (_hi - _lo + 1e-9) * 100.0)
    std3 = float(np.mean(stk3)) if stk3 else stk

    # Williams %R(14)
    wpr = (hi14 - cur) / (hi14 - lo14 + 1e-9) * -100.0

    # ROC(10)
    roc = (cur - close[-11]) / (close[-11] + 1e-9) * 100.0 if n >= 11 else 0.0

    # MFI(14)
    try:
        tp15  = (high[-15:] + low[-15:] + close[-15:]) / 3.0
        mf15  = tp15 * vol[-15:]
        pmf = sum(mf15[k] for k in range(1, 15) if tp15[k] > tp15[k - 1])
        nmf = sum(mf15[k] for k in range(1, 15) if tp15[k] <= tp15[k - 1])
        mfi = 100.0 - 100.0 / (1.0 + pmf / (nmf + 1e-9))
    except Exception:
        mfi = 50.0

    # OBV slope (10-day, normalised)
    try:
        obv = np.zeros(10)
        obv[0] = vol[-10]
        for k in range(1, 10):
            obv[k] = obv[k - 1] + (vol[-10 + k] if close[-10 + k] > close[-10 + k - 1]
                                    else -vol[-10 + k])
        obv_trend = (obv[-1] - obv[0]) / (abs(obv[0]) + 1e-9)
    except Exception:
        obv_trend = 0.0

    # VWAP distance (20-day session approximation)
    try:
        typ = (high[-20:] + low[-20:] + close[-20:]) / 3.0
        vwap = np.sum(typ * vol[-20:]) / (np.sum(vol[-20:]) + 1e-9)
        vwap_dist = (cur - vwap) / (vwap + 1e-9) * 100.0
    except Exception:
        vwap_dist = 0.0

    ma50_v  = sma(close, 50)
    ma200_v = sma(close, 200)
    pvsma20 = (cur - ma20_v) / (ma20_v + 1e-9) * 100.0

    g1 = [
        _safe(rsi14, 50),    _safe(rsi14, 50),       # real_rsi, enhanced_rsi_14
        _safe(macd_val),     _safe(sig_val),          # macd, signal_line
        _safe(bb_pos, 0.5),  _safe(bb_wid),           # bb_position, bb_width
        _safe(atr14),        _safe(adx, 25),          # atr_14, adx
        _safe(cci),          _safe(stk, 50),          # cci, stoch_k
        _safe(std3, 50),     _safe(wpr, -50),         # stoch_d, williams_r
        _safe(roc),          _safe(mfi, 50),          # roc, mfi
        _safe(obv_trend),    _safe(vwap_dist),        # obv_trend, vwap_distance
        _safe(ma20_v),       _safe(ma50_v),           # ma_20, ma_50
        _safe(ma200_v),      _safe(pvsma20),          # ma_200, price_vs_ma20
    ]  # 20 features

    # ─── Group 2: Price Momentum (10) ─────────────────────────────────────────
    r1d  = (cur - close[-2]) / (close[-2] + 1e-9) * 100 if n >= 2  else 0.0
    r5d  = (cur - close[-6]) / (close[-6] + 1e-9) * 100 if n >= 6  else 0.0
    r20d = (cur - close[-21]) / (close[-21] + 1e-9) * 100 if n >= 21 else 0.0
    r50d = (cur - close[-51]) / (close[-51] + 1e-9) * 100 if n >= 51 else 0.0

    mom5d  = float(np.sum(np.diff(close[-6:]) / (close[-6:-1] + 1e-9))) * 100 if n >= 6  else 0.0
    mom20d = float(np.sum(np.diff(close[-21:]) / (close[-21:-1] + 1e-9))) * 100 if n >= 21 else 0.0

    vol20d = float(np.std(np.diff(close[-21:]) / (close[-21:-1] + 1e-9))) * np.sqrt(252) * 100 \
             if n >= 21 else 10.0

    # 6-month volatility — prefer full history if available
    v_src  = hist_full['Close'].values.astype(float) \
             if (hist_full is not None and len(hist_full) >= 127) else close
    vol6m  = float(np.std(np.diff(v_src[-127:]) / (v_src[-127:-1] + 1e-9))) * np.sqrt(252) * 100 \
             if len(v_src) >= 127 else vol20d

    hl_rng = (high[-1] - low[-1]) / (cur + 1e-9) * 100.0

    h52_src = hist_full['High'].values.astype(float) \
              if (hist_full is not None and len(hist_full) >= 252) else high
    hi52    = float(np.max(h52_src[-252:])) if len(h52_src) >= 252 else float(np.max(h52_src))
    pvs52h  = cur / (hi52 + 1e-9)

    g2 = [
        _safe(r1d),  _safe(r5d),  _safe(r20d), _safe(r50d),   # price_change 1/5/20/50d
        _safe(mom5d), _safe(mom20d),                            # momentum 5d/20d
        _safe(vol20d), _safe(vol6m),                            # volatility 20d/6m
        _safe(hl_rng), _safe(pvs52h, 1.0),                     # hl_range, price_vs_52wh
    ]  # 10 features

    # ─── Group 3: Volume Patterns (8) ─────────────────────────────────────────
    vol5avg  = float(np.mean(vol[-5:]))
    vol20avg = float(np.mean(vol[-20:])) if n >= 20 else float(np.mean(vol))
    v_ratio  = vol5avg / (vol20avg + 1e-9)
    v_slope  = (float(np.mean(vol[-5:])) - float(np.mean(vol[-10:-5]))) / \
               (float(np.mean(vol[-10:])) + 1e-9) if n >= 10 else 0.0
    v_cv     = float(np.std(vol[-20:])) / (vol20avg + 1e-9) if n >= 20 else 0.5
    v_spike  = 1.0 if vol[-1] > 2 * vol20avg else 0.0
    v_mratio = vol[-1] / (vol20avg + 1e-9)

    obv_norm = 0.0
    try:
        o = 0.0
        w = min(n, 60)
        for k in range(-w, 0):
            o += vol[k] if close[k] > close[k - 1] else -vol[k]
        obv_norm = o / (vol20avg * w + 1e-9)
    except Exception:
        pass

    g3 = [
        _safe(v_ratio, 1.0),        # enhanced_volume_ratio
        _safe(v_slope),             # enhanced_volume_trend
        _safe(v_cv, 0.5),           # enhanced_volume_volatility
        _safe(v_spike),             # volume_spike
        _safe(vol20avg / 1e6),      # avg_volume (millions)
        _safe(v_mratio, 1.0),       # volume_ma_ratio
        _safe(obv_norm),            # enhanced_obv
        _safe(mfi, 50),             # enhanced_mfi (reuse Group1 value)
    ]  # 8 features

    # ─── Group 4: Fundamental Metrics (15) ────────────────────────────────────
    # Static per stock — same value for every sliding window of the same ticker.
    # This is an approximation acceptable for training; what matters is the
    # cross-sectional ranking signal, which is preserved.
    mktcap = float(info.get('marketCap') or 1)
    g4 = [
        _safe(info.get('trailingPE'),                              15.0),  # pe_ratio
        _safe(info.get('priceToBook'),                              3.0),  # pb_ratio
        _safe(info.get('debtToEquity') or 0,                        1.0),  # debt_to_equity
        _safe(info.get('currentRatio') or 0,                        1.5),  # current_ratio
        _safe((info.get('returnOnEquity')  or 0) * 100,            15.0),  # roe
        _safe((info.get('returnOnAssets')  or 0) * 100,            10.0),  # roa
        _safe((info.get('profitMargins')   or 0) * 100,            10.0),  # profit_margin
        _safe((info.get('operatingMargins') or 0) * 100,           15.0),  # operating_margin
        _safe((info.get('revenueGrowth')   or 0) * 100,            10.0),  # revenue_growth
        _safe((info.get('earningsGrowth')  or 0) * 100,            10.0),  # earnings_growth
        _safe((info.get('dividendYield')   or 0) * 100,             2.0),  # dividend_yield
        _safe((info.get('freeCashflow')    or 0) / mktcap * 100,    0.0),  # free_cash_flow
        _safe(info.get('bookValue'),                                 0.0),  # book_value_per_share
        _safe(info.get('priceToSalesTrailing12Months'),              3.0),  # price_to_sales
        _safe((info.get('enterpriseValue') or 0) / 1e9,             0.0),  # enterprise_value (B)
    ]  # 15 features

    # ─── Group 5: Sentiment & Flow proxies (7) ──────────────────────────────────
    # Historical institutional/sentiment data unavailable from OHLCV.
    # Use OHLCV-derived proxies that are CORRELATED with live analyzer outputs.
    # These replace the 6 previous neutral constants — key accuracy improvement.

    # 1. institutional_score proxy: volume-price trend (50-centred, 0-100)
    try:
        vpt_sum = sum(
            (close[k] - close[k - 1]) / (close[k - 1] + 1e-9) * vol[k] / (vol20avg + 1e-9)
            for k in range(-20, 0)
        )
        inst_proxy = float(np.clip(50.0 + vpt_sum * 50.0, 0.0, 100.0))
    except Exception:
        inst_proxy = 50.0

    # 2. fii_activity proxy: Chaikin Money Flow 20-day (-1 to +1)
    try:
        mfm20 = ((close[-20:] - low[-20:]) - (high[-20:] - close[-20:])) / \
                (high[-20:] - low[-20:] + 1e-9)
        cmf20 = float(np.sum(mfm20 * vol[-20:]) / (np.sum(vol[-20:]) + 1e-9))
    except Exception:
        cmf20 = 0.0

    # 3. dii_activity proxy: Accumulation-Distribution line 10-day slope (-1 to +1)
    try:
        ad_val, ad_arr = 0.0, []
        for k in range(max(0, n - 10), n):
            hl_k = high[k] - low[k]
            clv  = ((close[k] - low[k]) - (high[k] - close[k])) / (hl_k + 1e-9)
            ad_val += clv * vol[k]
            ad_arr.append(ad_val)
        dii_proxy = (ad_arr[-1] - ad_arr[0]) / (abs(ad_arr[0]) + abs(ad_arr[-1]) + 1e-9)
    except Exception:
        dii_proxy = 0.0

    # 4. mtf_trend_strength proxy: MA alignment score (0=all bearish, 100=all bullish)
    mtf_ts = 0.0
    if cur    > ma20_v:  mtf_ts += 33.3
    if ma20_v > ma50_v:  mtf_ts += 33.3
    if ma50_v > ma200_v: mtf_ts += 33.4

    # 5. mtf_momentum_strength proxy: RSI rate-of-change vs 5 days ago (0-100)
    try:
        n5     = max(14, n - 5)
        diff5_ = np.diff(close[:n5])
        g5_    = np.where(diff5_ > 0, diff5_, 0.0)
        l5_    = np.where(diff5_ < 0, -diff5_, 0.0)
        rsi_5d = 100.0 - 100.0 / (1.0 + np.mean(g5_[-14:]) / (np.mean(l5_[-14:]) + 1e-9))
        mtf_ms = float(np.clip(50.0 + (rsi14 - rsi_5d) * 2.0, 0.0, 100.0))
    except Exception:
        mtf_ms = 50.0

    # 6. mtf_timeframe_agreement proxy: % of last 20 closes above 20-day VWAP
    try:
        _vwap = np.sum((high[-20:] + low[-20:] + close[-20:]) / 3.0 * vol[-20:]) / \
                (np.sum(vol[-20:]) + 1e-9)
        mtf_ta = sum(1 for k in range(-20, 0) if close[k] > _vwap) / 20.0 * 100.0
    except Exception:
        mtf_ta = 50.0

    # 7. real_technical_score: derived composite from RSI, MACD, BB
    rsi_sc  = 100.0 - abs(rsi14 - 50) * 2.0
    macd_sc = 60.0 if macd_val > sig_val else 40.0
    bb_sc   = _safe(bb_pos * 100.0, 50.0)
    rt_sc   = rsi_sc * 0.4 + macd_sc * 0.3 + bb_sc * 0.3

    g5 = [
        _safe(inst_proxy, 50.0),  # institutional_score proxy (VPT-based)
        _safe(cmf20),              # fii_activity proxy (Chaikin Money Flow)
        _safe(dii_proxy),          # dii_activity proxy (A/D line slope)
        _safe(mtf_ts, 50.0),       # mtf_trend_strength proxy (MA alignment)
        _safe(mtf_ms, 50.0),       # mtf_momentum_strength proxy (RSI-RoC)
        _safe(mtf_ta, 50.0),       # mtf_timeframe_agreement proxy (% above VWAP)
        _safe(rt_sc,  50.0),       # real_technical_score (derived)
    ]  # 7 features

    # ─── Group 6: Multi-Timeframe (5) ─────────────────────────────────────────
    # GAP-4 FIX: Replaced binary ±1 direction flags with continuous normalised % returns.
    # Old: 1 bit each — a 0.1% and a 5% move both gave +1.0, losing all magnitude info.
    # New: actual magnitude encoded in ±1 using realistic clip thresholds (5/10/20%).
    # Feature count stays 65. ⚠️  RETRAIN REQUIRED — run: python train_ml_model.py --stocks 40
    daily_tr   = float(np.clip(r1d  / 5.0,  -1.0, 1.0))   # ±5% daily  → ±1
    weekly_tr  = float(np.clip(r5d  / 10.0, -1.0, 1.0))   # ±10% weekly → ±1
    monthly_tr = float(np.clip(r20d / 20.0, -1.0, 1.0))   # ±20% monthly → ±1
    mtf_comp   = (daily_tr + weekly_tr + monthly_tr + 3.0) / 6.0 * 100.0  # 0-100

    adv_sc = (rsi_sc * 0.3 + macd_sc * 0.3 + bb_sc * 0.2 +
              (50.0 + stk / 2.0) * 0.1 +
              max(0.0, 100.0 - abs(_safe(cci)) / 4.0) * 0.1)

    g6 = [
        daily_tr, weekly_tr, monthly_tr,    # daily/weekly/monthly_trend
        _safe(mtf_comp, 50.0),              # mtf_composite_score
        _safe(adv_sc,   50.0),              # advanced_technical_score_final
    ]  # 5 features

    features = np.array(g1 + g2 + g3 + g4 + g5 + g6, dtype=float)
    assert len(features) == 65, f"BUG: {len(features)} features produced, expected 65"
    features = np.nan_to_num(features, nan=0.0, posinf=100.0, neginf=-100.0)
    return features


def build_dataset(stock_list: list, forward_days: int = 10,
                  up_threshold: float = 2.0, down_threshold: float = -2.0):
    """
    Download 5Y history + ticker.info for each stock, slide a 60-day window,
    label by forward_days return, return (X, y, groups) arrays.
    Feature count is exactly 65 — matches ml_predictor.prepare_features().
    groups = integer stock index per row — used by GroupShuffleSplit to ensure
    all windows from the same stock land in either train OR test, never both.
    """
    X_all, y_all, groups_all = [], [], []

    for i, sym in enumerate(stock_list):
        try:
            logger.info(f"[{i+1}/{len(stock_list)}] Fetching {sym}...")
            ticker     = yf.Ticker(f"{sym}.NS")
            hist_full  = ticker.history(period='5y', interval='1d').copy()

            if hist_full.empty or len(hist_full) < 130:
                logger.warning(f"  {sym}: insufficient data ({len(hist_full)} rows) — skip")
                continue

            # Fetch fundamentals once per stock (best-effort)
            try:
                info = ticker.info or {}
            except Exception:
                info = {}

            hist_full = hist_full.reset_index()
            # yfinance may return 'Date' or 'Datetime' as the first column
            date_col  = hist_full.columns[0]
            # Flatten timezone-aware index if present
            if hasattr(hist_full[date_col], 'dt'):
                try:
                    hist_full[date_col] = hist_full[date_col].dt.tz_localize(None)
                except Exception:
                    pass
            closes    = hist_full['Close'].values.astype(float)
            n         = len(closes)

            # Build full-history df indexed by date for Group-2 look-backs
            hist_full_idx = hist_full.set_index(date_col)

            rows_added = 0
            for start in range(0, n - 60 - forward_days, 15):  # step=15: less autocorrelation
                window_end = start + 60
                if window_end + forward_days >= n:
                    break

                window = hist_full.iloc[start:window_end].set_index(date_col)
                # FIX (A-017): only pass history UP TO window_end as hist_full.
                # Passing the entire history caused look-ahead bias: the 52-week
                # high and 6-month volatility were read from FUTURE rows.
                hist_up_to_now = hist_full.iloc[:window_end].set_index(date_col)
                feats  = build_features_from_hist(window, info=info,
                                                  hist_full=hist_up_to_now)
                if feats is None:
                    continue

                entry = closes[window_end - 1]
                exit_ = closes[window_end + forward_days - 1]
                fwd   = (exit_ - entry) / (entry + 1e-9) * 100.0

                label = 1 if fwd > up_threshold else (-1 if fwd < down_threshold else 0)

                X_all.append(feats)
                y_all.append(label)
                groups_all.append(i)  # stock index — used by GroupShuffleSplit
                rows_added += 1

            logger.info(f"  {sym}: {rows_added} training rows added")

        except Exception as e:
            logger.warning(f"  {sym}: error — {e}")

    if not X_all:
        raise ValueError("No training data collected. Check internet connection / stock list.")

    X      = np.array(X_all,      dtype=float)
    y      = np.array(y_all,      dtype=int)
    groups = np.array(groups_all, dtype=int)

    unique, counts = np.unique(y, return_counts=True)
    logger.info(f"Dataset: {len(X)} samples, features={X.shape[1]}, unique stocks={len(np.unique(groups))}")
    logger.info(f"Label distribution: { {int(k): int(v) for k, v in zip(unique, counts)} }")

    # Hard validation — must match predictor's expected shape
    if X.shape[1] != 65:
        raise ValueError(
            f"FATAL: Feature count is {X.shape[1]}, expected 65. "
            "Fix build_features_from_hist() before training."
        )

    return X, y, groups


def _verify_ml_pickle_roundtrip(path: Path, payload: dict, X_check: np.ndarray) -> None:
    """Reload pickle and confirm model+scaler reproduce predictions on X_check."""
    if X_check.size == 0:
        raise ValueError('Integrity check needs at least one feature row')
    with open(path, 'rb') as f:
        loaded = pickle.load(f)
    for key in ('model', 'scaler'):
        if key not in loaded:
            raise ValueError(f"Reloaded pickle missing '{key}'")
    po = payload['model'].predict(payload['scaler'].transform(X_check))
    pl = loaded['model'].predict(loaded['scaler'].transform(X_check))
    if not np.array_equal(po, pl):
        raise ValueError('Reloaded model predictions differ from in-memory model')


# ── training ───────────────────────────────────────────────────────────────────
def train(stock_list: list, forward_days: int, n_estimators: int, max_depth: int,
          learning_rate: float, test_size: float):

    logger.info("=" * 60)
    logger.info("NSE ML MODEL TRAINER")
    logger.info(f"  Stocks      : {len(stock_list)}")
    logger.info(f"  Horizon     : {forward_days} trading days")
    logger.info(f"  Up/Down thr : ±2 %")
    logger.info("=" * 60)

    X, y, groups = build_dataset(stock_list, forward_days=forward_days)

    # Validate shape — must match ml_predictor.prepare_features() = 65 features
    if X.shape[1] != 65:
        raise ValueError(
            f"Feature shape mismatch: trainer produced {X.shape[1]} features, "
            "but ml_predictor.prepare_features() returns 65. "
            "Fix build_features_from_hist() before training."
        )
    logger.info(f"Feature shape validated: {X.shape[1]} features OK")

    # GroupShuffleSplit: all windows from the same stock go to train OR test — no leakage
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    logger.info(f"GroupShuffleSplit: {len(train_idx)} train / {len(test_idx)} test rows "
                f"({len(np.unique(groups[train_idx]))} / {len(np.unique(groups[test_idx]))} stocks)")

    scaler    = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    # Class-balanced sample weights — counteracts HOLD label dominance
    sample_weights = compute_sample_weight('balanced', y_train)

    logger.info(f"Training GradientBoostingClassifier "
                f"(n_estimators={n_estimators}, depth={max_depth}, lr={learning_rate}, "
                f"balanced class weights)...")

    clf = GradientBoostingClassifier(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        subsample=0.7,             # stronger row subsampling vs 0.8
        min_samples_leaf=30,       # stronger leaf regularization vs 15
        min_impurity_decrease=1e-4,  # prune splits that barely help
        random_state=42,
        verbose=0
    )
    clf.fit(X_train_s, y_train, sample_weight=sample_weights)

    # ── evaluation ────────────────────────────────────────────────────────────
    train_acc = accuracy_score(y_train, clf.predict(X_train_s))
    test_acc  = accuracy_score(y_test,  clf.predict(X_test_s))

    logger.info(f"Train accuracy : {train_acc:.2%}")
    logger.info(f"Test  accuracy : {test_acc:.2%}")
    logger.info("\n" + classification_report(y_test, clf.predict(X_test_s),
                                             target_names=['DOWN', 'HOLD', 'UP']))

    # ── save FIRST (before optional CV) ──────────────────────────────────────
    model_path = Path('models/ml_predictor_latest.pkl')
    cv_mean    = 0.0   # placeholder; updated below if CV succeeds
    payload = {
        'model':          clf,
        'scaler':         scaler,
        'feature_count':  X.shape[1],       # must be 65
        'trained_date':   datetime.now().strftime('%Y-%m-%d %H:%M'),
        'num_samples':    len(X),
        'train_accuracy': train_acc,
        'test_accuracy':  test_acc,
        'cv_mean':        cv_mean,
        'forward_days':   forward_days,
        'stock_count':    len(stock_list),
        'trainer_version': '3.0',           # v3.0 = look-ahead bias fix (A-017) + GroupKFold CV
    }
    with open(model_path, 'wb') as f:
        pickle.dump(payload, f)
    logger.info(f"\nModel saved  -> {model_path.resolve()}")

    _n_check = min(32, len(X_test) if len(X_test) > 0 else len(X_train))
    X_integrity = (X_test if len(X_test) > 0 else X_train)[:_n_check]
    try:
        _verify_ml_pickle_roundtrip(model_path, payload, X_integrity)
        logger.info("Post-save integrity check: reload OK, predictions match in-memory model")
    except Exception as ver_err:
        logger.error(f"Post-save model integrity check failed: {ver_err}")
        raise

    # ── 5-fold GroupKFold CV (group-aware: no stock appears in both train & val) ──────
    try:
        # Use Pipeline so each fold fits its own scaler (no leakage across folds)
        pipe = Pipeline([
            ('scaler', StandardScaler()),
            ('clf',    GradientBoostingClassifier(
                n_estimators=n_estimators, learning_rate=learning_rate,
                max_depth=max_depth, subsample=0.7, min_samples_leaf=30,
                min_impurity_decrease=1e-4, random_state=42, verbose=0
            ))
        ])
        gkf = GroupKFold(n_splits=5)
        cv_scores = cross_val_score(pipe, X, y, cv=gkf, groups=groups, scoring='accuracy')
        cv_mean = float(cv_scores.mean())
        cv_std  = float(cv_scores.std())
        logger.info(f"5-fold GroupKFold CV accuracy: {cv_mean:.2%} ± {cv_std:.2%}")
        # Update pkl with CV result
        payload['cv_mean'] = cv_mean
        payload['cv_std']  = cv_std
        with open(model_path, 'wb') as f:
            pickle.dump(payload, f)
        logger.info(f"Model updated with CV score -> {model_path.resolve()}")
        try:
            _verify_ml_pickle_roundtrip(model_path, payload, X_integrity)
            logger.info("Post-CV-save integrity check: reload OK, predictions match")
        except Exception as ver_err:
            logger.error(f"Post-CV-save integrity check failed: {ver_err}")
            raise
    except Exception as cv_err:
        logger.warning(f"5-fold CV skipped ({cv_err}). Model already saved above.")

    logger.info("Re-run the main analyzer — it will now use the trained model "
                "and ml_using_fallback=False in all results.")
    return test_acc


# ── CLI ────────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description='Train the NSE ML model used by analyze_top200_stocks_enhanced.py'
    )
    p.add_argument('--stocks', type=int, default=len(DEFAULT_STOCKS),
                   help=f'Number of stocks to use (default: {len(DEFAULT_STOCKS)})')
    p.add_argument('--forward-days', type=int, default=10,
                   help='Prediction horizon in trading days (default: 10)')
    p.add_argument('--n-estimators', type=int, default=200,
                   help='GBM n_estimators (default: 200)')
    p.add_argument('--max-depth', type=int, default=3,
                   help='GBM max_depth (default: 3 — reduces overfitting)')
    p.add_argument('--learning-rate', type=float, default=0.08,
                   help='GBM learning_rate (default: 0.08)')
    p.add_argument('--test-size', type=float, default=0.20,
                   help='Fraction held out for test (default: 0.20)')
    return p.parse_args()


if __name__ == '__main__':
    args  = parse_args()
    stocks = DEFAULT_STOCKS[:args.stocks]

    acc = train(
        stock_list    = stocks,
        forward_days  = args.forward_days,
        n_estimators  = args.n_estimators,
        max_depth     = args.max_depth,
        learning_rate = args.learning_rate,
        test_size     = args.test_size,
    )

    print(f"\n{'='*60}")
    print(f"  Training complete. Test accuracy: {acc:.2%}")
    print(f"  models/ml_predictor_latest.pkl written.")
    print(f"  Run the main analyzer to use the trained model.")
    print(f"{'='*60}")
