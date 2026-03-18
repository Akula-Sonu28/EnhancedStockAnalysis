"""
Scoring Engine Validation Framework
====================================
Walk-forward backtest that measures predictive accuracy of all 3 scoring engines
and the final blended score against actual forward returns.

Tests: IC, Quintile Spread, Hit Rate, Component IC, Cross-Correlation,
       Sector Bias, Score Stability.

Usage:
    python validate_scoring_accuracy.py              # default 100 stocks, 6 windows
    python validate_scoring_accuracy.py --stocks 200 # full universe
    python validate_scoring_accuracy.py --stocks 50  # quick test
"""

import argparse
import logging
import os
import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING)

sys.path.append(".")

from hybrid_optimized_scoring import HybridOptimizedScoringEngine
from improved_scoring_engine import ImprovedScoringEngine
from corrected_scoring_engine import CorrectedScoringEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sf(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def load_stock_list(max_stocks=200):
    csv_path = Path("stock_list_template.csv")
    if not csv_path.exists():
        print("[WARN] stock_list_template.csv not found, using fallback list")
        return ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
                "SBIN", "KOTAKBANK", "LT", "WIPRO", "TATAMOTORS"]
    df = pd.read_csv(csv_path)
    symbols = df["Symbol"].dropna().unique().tolist()
    return symbols[:max_stocks]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

_fundamentals_cache = {}


def fetch_fundamentals(symbol):
    if symbol in _fundamentals_cache:
        return _fundamentals_cache[symbol]
    try:
        info = yf.Ticker(f"{symbol}.NS").info
        data = {
            "pe_ratio": _sf(info.get("trailingPE"), 20),
            "roe": _sf(info.get("returnOnEquity"), 0.15) * 100,
            "debt_to_equity": _sf(info.get("debtToEquity"), 50),
            "market_cap": _sf(info.get("marketCap"), 1e12),
            "pb_ratio": _sf(info.get("priceToBook"), 3),
            "net_margin": _sf(info.get("profitMargins"), 0.1) * 100,
            "revenue_growth": _sf(info.get("revenueGrowth"), 0.05) * 100,
            "sector": info.get("sector", "Unknown"),
        }
    except Exception:
        data = {
            "pe_ratio": 20, "roe": 15, "debt_to_equity": 50,
            "market_cap": 1e12, "pb_ratio": 3, "net_margin": 10,
            "revenue_growth": 5, "sector": "Unknown",
        }
    _fundamentals_cache[symbol] = data
    return data


def fetch_history(symbol, days=400):
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period=f"{days}d")
        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Build stock_data dict from OHLCV slice + fundamentals
# ---------------------------------------------------------------------------

def build_stock_data(hist_slice, fundamentals, symbol=""):
    if hist_slice is None or len(hist_slice) < 20:
        return None

    close = hist_slice["Close"]
    high = hist_slice["High"]
    low = hist_slice["Low"]
    volume = hist_slice["Volume"]
    current_price = close.iloc[-1]

    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else current_price
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else current_price

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    loss_safe = loss.replace(0, np.nan)
    rs = gain / loss_safe
    rsi_series = (100 - (100 / (1 + rs))).fillna(50.0)
    rsi_val = _sf(rsi_series.iloc[-1], 50)

    def _pct(n):
        if len(close) <= n:
            return 0.0
        d = close.iloc[-n]
        return ((current_price / d) - 1) * 100 if (d and not np.isnan(d) and d != 0) else 0.0

    price_change_5d = _pct(5)
    price_change_20d = _pct(22)
    price_change_1m = price_change_20d

    vol_sma_20 = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()
    vol_ratio = (volume.iloc[-1] / vol_sma_20) if (vol_sma_20 and not np.isnan(vol_sma_20) and vol_sma_20 > 0) else 1.0

    volatility = close.pct_change().rolling(20).std().iloc[-1] * 100 if len(close) >= 21 else 25.0
    if np.isnan(volatility):
        volatility = 25.0

    high_52w = close.max() if len(close) >= 200 else close.max()
    low_52w = close.min() if len(close) >= 200 else close.min()

    macd_line = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    macd_signal_line = macd_line.ewm(span=9).mean()
    macd_hist = macd_line - macd_signal_line

    # Stochastic %K (14-period)
    if len(close) >= 14:
        _low14 = low.rolling(14).min()
        _high14 = high.rolling(14).max()
        _denom = _high14 - _low14
        _denom = _denom.replace(0, np.nan)
        stoch_k = ((close - _low14) / _denom * 100).iloc[-1]
        stoch_k = _sf(stoch_k, 50)
    else:
        stoch_k = 50.0

    # Beta proxy (rolling 60d correlation with index approximated by own returns std)
    beta_val = fundamentals.get("beta", 1.0)
    if beta_val is None or (isinstance(beta_val, float) and np.isnan(beta_val)):
        beta_val = 1.0

    # Max drawdown over available period
    cummax = close.cummax()
    drawdown_series = (close - cummax) / cummax * 100
    max_dd = abs(drawdown_series.min()) if len(drawdown_series) > 0 else 15.0
    max_dd = _sf(max_dd, 15)

    return {
        "symbol": symbol,
        "current_price": current_price,
        "sma_50": sma_50,
        "ma_50": sma_50,
        "sma_20": sma_20,
        "rsi": rsi_val,
        "real_rsi": rsi_val,
        "enhanced_rsi_14": rsi_val,
        "price_change_1m": price_change_1m,
        "enhanced_price_change_20d": price_change_20d,
        "enhanced_price_change_5d": price_change_5d,
        "price_change_1w": _pct(5),
        "volume": volume.iloc[-1],
        "volume_sma_20": vol_sma_20,
        "volume_ratio": vol_ratio,
        "enhanced_volume_ratio": vol_ratio,
        "volatility": volatility,
        "volatility_20d": volatility,
        "52_week_high": high_52w,
        "52_week_low": low_52w,
        "pe_ratio": fundamentals.get("pe_ratio", 20),
        "roe": fundamentals.get("roe", 15),
        "debt_to_equity": fundamentals.get("debt_to_equity", 50),
        "market_cap": fundamentals.get("market_cap", 1e12),
        "pb_ratio": fundamentals.get("pb_ratio", 3),
        "net_margin": fundamentals.get("net_margin", 10),
        "revenue_growth": fundamentals.get("revenue_growth", 5),
        "sector": fundamentals.get("sector", "Unknown"),
        "macd_histogram": _sf(macd_hist.iloc[-1], 0),
        "enhanced_macd_histogram": _sf(macd_hist.iloc[-1], 0),
        "enhanced_stoch_k": stoch_k,
        "beta": beta_val,
        "max_drawdown_6m": max_dd,
        "mtf_timeframe_agreement": 50,
        "mtf_trend_strength": 50,
        "mtf_composite_score": 50,
        "mtf_momentum_strength": 50,
        "overall_score": 50,
        "momentum_flags": 0,
        "breakout_patterns": 0,
        "market_regime": "",
    }


# ---------------------------------------------------------------------------
# Score a single stock for a given window
# ---------------------------------------------------------------------------

def score_stock(symbol, hist_slice, fundamentals, engines):
    sd = build_stock_data(hist_slice, fundamentals, symbol)
    if sd is None:
        return None

    result = {"symbol": symbol, "sector": fundamentals.get("sector", "Unknown")}

    try:
        h = engines["hybrid"].calculate_hybrid_score(symbol, sd)
        result["hybrid_score"] = _sf(h.get("hybrid_score"), 50)
        result["hybrid_fundamental"] = _sf(h.get("components", {}).get("fundamental_quality"), 50)
        result["hybrid_momentum"] = _sf(h.get("components", {}).get("momentum_technical"), 50)
        result["hybrid_volume"] = _sf(h.get("components", {}).get("volume_strength"), 50)
        result["hybrid_sector"] = _sf(h.get("components", {}).get("sector_momentum"), 50)
        result["hybrid_risk"] = _sf(h.get("components", {}).get("risk_adjustment"), 50)
        result["hybrid_mtf"] = _sf(h.get("components", {}).get("multi_timeframe"), 50)
        result["hybrid_ml"] = _sf(h.get("components", {}).get("ml_signal"), 50)
    except Exception:
        result["hybrid_score"] = 50
        for k in ["hybrid_fundamental", "hybrid_momentum", "hybrid_volume", "hybrid_sector", "hybrid_risk", "hybrid_mtf", "hybrid_ml"]:
            result[k] = 50

    try:
        imp = engines["improved"].calculate_improved_overall_score(symbol, sd)
        result["improved_score"] = _sf(imp.get("improved_overall_score"), 50)
        result["improved_fundamental"] = _sf(imp.get("fundamental_quality"), 50)
        result["improved_momentum"] = _sf(imp.get("momentum_technical"), 50)
        result["improved_contrarian"] = _sf(imp.get("contrarian_momentum"), 50)
        result["improved_quality"] = _sf(imp.get("quality_multiplier"), 50)
    except Exception:
        result["improved_score"] = 50
        for k in ["improved_fundamental", "improved_momentum", "improved_contrarian", "improved_quality"]:
            result[k] = 50

    try:
        cor = engines["corrected"].calculate_corrected_overall_score(symbol, sd)
        result["corrected_score"] = _sf(cor.get("corrected_overall_score"), 50)
        result["corrected_contrarian_tech"] = _sf(cor.get("contrarian_technical"), 50)
        result["corrected_contrarian_mom"] = _sf(cor.get("contrarian_momentum"), 50)
        result["corrected_fundamental"] = _sf(cor.get("fundamental_quality"), 50)
        result["corrected_value"] = _sf(cor.get("value_opportunity"), 50)
    except Exception:
        result["corrected_score"] = 50
        for k in ["corrected_contrarian_tech", "corrected_contrarian_mom", "corrected_fundamental", "corrected_value"]:
            result[k] = 50

    hs = result["hybrid_score"]
    ims = result["improved_score"]
    result["blended_score"] = hs if hs > 0 else ims

    return result


# ---------------------------------------------------------------------------
# Walk-forward engine
# ---------------------------------------------------------------------------

def run_walk_forward(symbols, n_windows=6, forward_days=30, history_days=400):
    engines = {
        "hybrid": HybridOptimizedScoringEngine(),
        "improved": ImprovedScoringEngine(),
        "corrected": CorrectedScoringEngine(),
    }

    now = datetime.now()
    all_rows = []
    total = len(symbols)

    print(f"\n{'='*70}")
    print(f"  SCORING ENGINE VALIDATION — WALK-FORWARD BACKTEST")
    print(f"  Stocks: {total} | Windows: {n_windows} | Forward: {forward_days}d")
    print(f"{'='*70}\n")

    for si, symbol in enumerate(symbols):
        t0 = time.time()
        hist = fetch_history(symbol, history_days)
        if hist.empty or len(hist) < 100:
            print(f"  [{si+1:3d}/{total}] {symbol:<12} SKIP (insufficient data)")
            continue

        fundamentals = fetch_fundamentals(symbol)

        for w in range(n_windows):
            score_date = now - timedelta(days=forward_days * (w + 1))
            eval_start = score_date
            eval_7d = score_date + timedelta(days=7)
            eval_30d = score_date + timedelta(days=forward_days)

            scoring_hist = hist[hist.index <= score_date]
            if len(scoring_hist) < 50:
                continue

            start_price = scoring_hist["Close"].iloc[-1]
            if start_price == 0 or np.isnan(start_price):
                continue

            future_7d = hist[(hist.index > score_date) & (hist.index <= eval_7d)]
            future_30d = hist[(hist.index > score_date) & (hist.index <= eval_30d)]

            ret_7d = None
            ret_30d = None
            if not future_7d.empty:
                ret_7d = (future_7d["Close"].iloc[-1] - start_price) / start_price * 100
            if not future_30d.empty:
                ret_30d = (future_30d["Close"].iloc[-1] - start_price) / start_price * 100

            if ret_30d is None:
                continue

            scores = score_stock(symbol, scoring_hist, fundamentals, engines)
            if scores is None:
                continue

            scores["window"] = w + 1
            scores["score_date"] = score_date.strftime("%Y-%m-%d")
            scores["start_price"] = round(start_price, 2)
            scores["return_7d"] = round(ret_7d, 4) if ret_7d is not None else None
            scores["return_30d"] = round(ret_30d, 4)
            all_rows.append(scores)

        elapsed = time.time() - t0
        n_rows = sum(1 for r in all_rows if r["symbol"] == symbol)
        print(f"  [{si+1:3d}/{total}] {symbol:<12} {n_rows} obs  ({elapsed:.1f}s)")
        time.sleep(0.15)

    df = pd.DataFrame(all_rows)
    print(f"\n  Total observations: {len(df)}")
    return df


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

SCORE_COLS = ["hybrid_score", "improved_score", "corrected_score", "blended_score"]
ENGINE_NAMES = ["Hybrid V4", "Improved V3", "Corrected V2", "Blended (Final)"]

COMPONENT_COLS = [
    "hybrid_fundamental", "hybrid_momentum", "hybrid_volume",
    "hybrid_sector", "hybrid_risk", "hybrid_mtf", "hybrid_ml",
    "improved_fundamental", "improved_momentum",
    "improved_contrarian", "improved_quality",
    "corrected_contrarian_tech", "corrected_contrarian_mom",
    "corrected_fundamental", "corrected_value",
]


def compute_ic(df, score_col, return_col="return_30d"):
    valid = df[[score_col, return_col]].dropna()
    if len(valid) < 10:
        return np.nan
    corr, _ = stats.spearmanr(valid[score_col], valid[return_col])
    return corr


def analyze_ic(df):
    rows = []
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        for horizon in ["return_7d", "return_30d"]:
            horizon_label = "7d" if "7d" in horizon else "30d"
            per_window = []
            for w in df["window"].unique():
                wdf = df[df["window"] == w]
                ic = compute_ic(wdf, sc, horizon)
                per_window.append(ic)
                rows.append({
                    "engine": name, "horizon": horizon_label,
                    "window": w, "n_stocks": len(wdf),
                    "ic": round(ic, 4) if not np.isnan(ic) else None,
                })
            mean_ic = np.nanmean(per_window)
            rows.append({
                "engine": name, "horizon": horizon_label,
                "window": "MEAN", "n_stocks": len(df),
                "ic": round(mean_ic, 4) if not np.isnan(mean_ic) else None,
            })
    return pd.DataFrame(rows)


def analyze_quintiles(df):
    rows = []
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        for horizon in ["return_7d", "return_30d"]:
            horizon_label = "7d" if "7d" in horizon else "30d"
            valid = df[[sc, horizon]].dropna()
            if len(valid) < 25:
                continue
            valid["quintile"] = pd.qcut(valid[sc], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
            for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
                qdf = valid[valid["quintile"] == q]
                if qdf.empty:
                    continue
                rows.append({
                    "engine": name, "horizon": horizon_label,
                    "quintile": q, "n_stocks": len(qdf),
                    "avg_return": round(qdf[horizon].mean(), 4),
                    "median_return": round(qdf[horizon].median(), 4),
                    "avg_score": round(qdf[sc].mean(), 1),
                })
            q5_ret = valid[valid["quintile"] == "Q5"][horizon].mean() if "Q5" in valid["quintile"].values else 0
            q1_ret = valid[valid["quintile"] == "Q1"][horizon].mean() if "Q1" in valid["quintile"].values else 0
            rows.append({
                "engine": name, "horizon": horizon_label,
                "quintile": "Q5-Q1 SPREAD", "n_stocks": len(valid),
                "avg_return": round(q5_ret - q1_ret, 4),
                "median_return": None, "avg_score": None,
            })
    return pd.DataFrame(rows)


def analyze_hit_rates(df):
    rows = []
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        for horizon in ["return_7d", "return_30d"]:
            horizon_label = "7d" if "7d" in horizon else "30d"
            valid = df[[sc, horizon]].dropna()

            buy_zone = valid[valid[sc] >= 70]
            avoid_zone = valid[valid[sc] < 40]

            buy_hit = (buy_zone[horizon] > 0).mean() * 100 if len(buy_zone) > 0 else None
            avoid_hit = (avoid_zone[horizon] < 0).mean() * 100 if len(avoid_zone) > 0 else None

            rows.append({
                "engine": name, "horizon": horizon_label,
                "zone": "BUY (score>=70)", "n_stocks": len(buy_zone),
                "hit_rate_pct": round(buy_hit, 1) if buy_hit is not None else None,
                "avg_return": round(buy_zone[horizon].mean(), 2) if len(buy_zone) > 0 else None,
            })
            rows.append({
                "engine": name, "horizon": horizon_label,
                "zone": "AVOID (score<40)", "n_stocks": len(avoid_zone),
                "hit_rate_pct": round(avoid_hit, 1) if avoid_hit is not None else None,
                "avg_return": round(avoid_zone[horizon].mean(), 2) if len(avoid_zone) > 0 else None,
            })
    return pd.DataFrame(rows)


def analyze_component_ic(df):
    rows = []
    for comp in COMPONENT_COLS:
        if comp not in df.columns:
            continue
        for horizon in ["return_7d", "return_30d"]:
            horizon_label = "7d" if "7d" in horizon else "30d"
            ic = compute_ic(df, comp, horizon)
            rows.append({
                "component": comp, "horizon": horizon_label,
                "ic": round(ic, 4) if not np.isnan(ic) else None,
                "n_obs": df[[comp, horizon]].dropna().shape[0],
            })
    return pd.DataFrame(rows)


def analyze_correlation_matrix(df):
    all_score_cols = SCORE_COLS + [c for c in COMPONENT_COLS if c in df.columns]
    valid = df[all_score_cols].dropna()
    if len(valid) < 10:
        return pd.DataFrame()
    corr = valid.corr(method="pearson")
    return corr.round(3)


def analyze_sector_bias(df):
    rows_avg = []
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        for sector, grp in df.groupby("sector"):
            if len(grp) < 5:
                continue
            rows_avg.append({
                "engine": name, "sector": sector,
                "n_stocks": len(grp),
                "avg_score": round(grp[sc].mean(), 1),
                "std_score": round(grp[sc].std(), 1),
            })

    rows_ic = []
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        raw_ic = compute_ic(df, sc, "return_30d")

        sector_ranked = df.copy()
        sector_ranked["_sector_rank"] = sector_ranked.groupby("sector")[sc].rank(pct=True)
        neutral_ic = compute_ic(sector_ranked, "_sector_rank", "return_30d")

        rows_ic.append({
            "engine": name,
            "raw_ic": round(raw_ic, 4) if not np.isnan(raw_ic) else None,
            "sector_neutral_ic": round(neutral_ic, 4) if not np.isnan(neutral_ic) else None,
            "ic_drop": round((raw_ic - neutral_ic), 4) if (not np.isnan(raw_ic) and not np.isnan(neutral_ic)) else None,
        })

    return pd.DataFrame(rows_avg), pd.DataFrame(rows_ic)


def analyze_stability(df):
    rows = []
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        for symbol, grp in df.groupby("symbol"):
            if len(grp) < 2:
                continue
            scores = grp[sc].dropna().values
            score_range = scores.max() - scores.min()
            score_std = scores.std()
            rows.append({
                "engine": name, "symbol": symbol,
                "n_windows": len(scores),
                "min_score": round(scores.min(), 1),
                "max_score": round(scores.max(), 1),
                "range": round(score_range, 1),
                "std": round(score_std, 1),
                "unstable": score_range > 20,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Summary with PASS / FAIL
# ---------------------------------------------------------------------------

def build_summary(ic_df, quintile_df, hit_df, component_ic_df, corr_df, sector_ic_df, stability_df):
    results = []

    # Test 1: IC
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        mean_row = ic_df[(ic_df["engine"] == name) & (ic_df["horizon"] == "30d") & (ic_df["window"] == "MEAN")]
        if not mean_row.empty:
            ic_val = mean_row.iloc[0]["ic"]
            passed = ic_val is not None and ic_val > 0.05
            results.append({
                "test": f"IC — {name} (30d)",
                "metric": f"{ic_val}" if ic_val is not None else "N/A",
                "threshold": "> 0.05",
                "verdict": "PASS" if passed else "FAIL",
            })

    # Test 2: Quintile spread
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        spread_row = quintile_df[(quintile_df["engine"] == name) & (quintile_df["horizon"] == "30d") & (quintile_df["quintile"] == "Q5-Q1 SPREAD")]
        if not spread_row.empty:
            spread_val = spread_row.iloc[0]["avg_return"]
            passed = spread_val is not None and spread_val > 0
            results.append({
                "test": f"Quintile Spread — {name} (30d)",
                "metric": f"{spread_val}%" if spread_val is not None else "N/A",
                "threshold": "> 0%",
                "verdict": "PASS" if passed else "FAIL",
            })

    # Test 3: Hit rate
    for sc, name in zip(SCORE_COLS, ENGINE_NAMES):
        buy_row = hit_df[(hit_df["engine"] == name) & (hit_df["horizon"] == "30d") & (hit_df["zone"].str.contains("BUY"))]
        avoid_row = hit_df[(hit_df["engine"] == name) & (hit_df["horizon"] == "30d") & (hit_df["zone"].str.contains("AVOID"))]
        if not buy_row.empty:
            hr = buy_row.iloc[0]["hit_rate_pct"]
            n_stocks = buy_row.iloc[0]["n_stocks"]
            has_data = hr is not None and not (isinstance(hr, float) and np.isnan(hr)) and n_stocks > 0
            passed = has_data and hr > 50
            results.append({
                "test": f"BUY Hit Rate — {name} (30d)",
                "metric": f"{hr:.1f}% (n={n_stocks})" if has_data else f"N/A (n={n_stocks})",
                "threshold": "> 50%",
                "verdict": "PASS" if passed else ("SKIP" if not has_data else "FAIL"),
            })
        if not avoid_row.empty:
            hr = avoid_row.iloc[0]["hit_rate_pct"]
            n_stocks = avoid_row.iloc[0]["n_stocks"]
            has_data = hr is not None and not (isinstance(hr, float) and np.isnan(hr)) and n_stocks > 0
            passed = has_data and hr > 50
            results.append({
                "test": f"AVOID Hit Rate — {name} (30d)",
                "metric": f"{hr:.1f}% (n={n_stocks})" if has_data else f"N/A (n={n_stocks})",
                "threshold": "> 50%",
                "verdict": "PASS" if passed else ("SKIP" if not has_data else "FAIL"),
            })

    # Test 4: Double-counting
    if not corr_df.empty:
        high_corr_pairs = []
        cols = corr_df.columns
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                val = corr_df.iloc[i, j]
                if abs(val) > 0.7:
                    high_corr_pairs.append(f"{cols[i]} <-> {cols[j]} ({val})")
        n_redundant = len(high_corr_pairs)
        results.append({
            "test": "Double-counting (correlation > 0.7)",
            "metric": f"{n_redundant} redundant pairs",
            "threshold": "0 pairs",
            "verdict": "PASS" if n_redundant == 0 else "FAIL",
        })

    # Test 5: Sector bias
    if not sector_ic_df.empty:
        for _, row in sector_ic_df.iterrows():
            drop = row.get("ic_drop")
            passed = drop is not None and abs(drop) < 0.05
            results.append({
                "test": f"Sector Bias — {row['engine']}",
                "metric": f"IC drop: {drop}" if drop is not None else "N/A",
                "threshold": "drop < 0.05",
                "verdict": "PASS" if passed else "FAIL",
            })

    # Test 6: Stability
    if not stability_df.empty:
        for name in ENGINE_NAMES:
            eng_stab = stability_df[stability_df["engine"] == name]
            if eng_stab.empty:
                continue
            unstable_pct = eng_stab["unstable"].mean() * 100
            results.append({
                "test": f"Score Stability — {name}",
                "metric": f"{unstable_pct:.0f}% unstable (range>20)",
                "threshold": "< 30%",
                "verdict": "PASS" if unstable_pct < 30 else "FAIL",
            })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_summary(summary_df, ic_df, quintile_df, hit_df):
    print(f"\n{'='*70}")
    print(f"  VALIDATION RESULTS — SUMMARY")
    print(f"{'='*70}\n")

    n_pass = (summary_df["verdict"] == "PASS").sum()
    n_fail = (summary_df["verdict"] == "FAIL").sum()
    n_total = len(summary_df)
    print(f"  Overall: {n_pass}/{n_total} PASS, {n_fail}/{n_total} FAIL\n")

    for _, row in summary_df.iterrows():
        tag = "PASS" if row["verdict"] == "PASS" else "FAIL"
        print(f"  [{tag:4s}] {row['test']:<45s} = {row['metric']:<20s} (threshold: {row['threshold']})")

    print(f"\n{'='*70}")
    print(f"  IC BY ENGINE (30-day forward returns)")
    print(f"{'='*70}")
    mean_ics = ic_df[(ic_df["window"] == "MEAN") & (ic_df["horizon"] == "30d")]
    for _, row in mean_ics.iterrows():
        ic_val = row["ic"]
        print(f"  {row['engine']:<20s}  IC = {ic_val}" if ic_val is not None else f"  {row['engine']:<20s}  IC = N/A")

    print(f"\n{'='*70}")
    print(f"  QUINTILE RETURNS (30-day)")
    print(f"{'='*70}")
    q30 = quintile_df[quintile_df["horizon"] == "30d"]
    for name in ENGINE_NAMES:
        eng_q = q30[q30["engine"] == name]
        if eng_q.empty:
            continue
        print(f"\n  {name}:")
        for _, row in eng_q.iterrows():
            q = row["quintile"]
            ret = row["avg_return"]
            n = row["n_stocks"]
            if q == "Q5-Q1 SPREAD":
                print(f"    {'SPREAD':<8s}  {ret:>8.2f}%")
            else:
                print(f"    {q:<8s}  {ret:>8.2f}%  (n={n})")

    print(f"\n{'='*70}")
    print(f"  HIT RATES (30-day)")
    print(f"{'='*70}")
    hr30 = hit_df[hit_df["horizon"] == "30d"]
    for name in ENGINE_NAMES:
        eng_hr = hr30[hr30["engine"] == name]
        if eng_hr.empty:
            continue
        print(f"\n  {name}:")
        for _, row in eng_hr.iterrows():
            hr = row["hit_rate_pct"]
            n = row["n_stocks"]
            zone = row["zone"]
            avg_r = row["avg_return"]
            hr_str = f"{hr:.1f}%" if (hr is not None and not np.isnan(hr)) else "N/A"
            avg_str = f"{avg_r}%" if (avg_r is not None and not np.isnan(avg_r)) else "N/A"
            print(f"    {zone:<25s}  Hit: {hr_str:<8s}  Avg Return: {avg_str:<8s}  (n={n})")

    print()


# ---------------------------------------------------------------------------
# Excel report
# ---------------------------------------------------------------------------

def write_excel_report(summary_df, ic_df, quintile_df, hit_df,
                       component_ic_df, corr_df, sector_avg_df,
                       sector_ic_df, stability_df, raw_df):
    os.makedirs("reports", exist_ok=True)
    path = "reports/scoring_validation_report.xlsx"

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        ic_df.to_excel(writer, sheet_name="IC by Engine", index=False)
        quintile_df.to_excel(writer, sheet_name="Quintile Returns", index=False)
        hit_df.to_excel(writer, sheet_name="Hit Rates", index=False)
        component_ic_df.to_excel(writer, sheet_name="Component IC", index=False)
        if not corr_df.empty:
            corr_df.to_excel(writer, sheet_name="Correlation Matrix")
        if not sector_avg_df.empty:
            sector_avg_df.to_excel(writer, sheet_name="Sector Avg Scores", index=False)
        if not sector_ic_df.empty:
            sector_ic_df.to_excel(writer, sheet_name="Sector Bias IC", index=False)
        if not stability_df.empty:
            stability_df.to_excel(writer, sheet_name="Score Stability", index=False)

        limitations = pd.DataFrame([
            {"#": 1, "limitation": "Fundamental look-ahead bias: yfinance provides current PE/ROE/debt, not historical values as of scoring date. Fundamental component results are optimistic."},
            {"#": 2, "limitation": "6-month lookback only: 6 windows of 30-day returns. Not statistically robust for long-horizon claims."},
            {"#": 3, "limitation": "Survivorship bias: Current stock list may differ from the actual top-200 at historical scoring dates."},
            {"#": 4, "limitation": "Market regime: If the entire period was bearish/bullish, results are regime-specific and may not generalize."},
            {"#": 5, "limitation": "Sector multipliers in Hybrid engine apply a permanent bias (e.g., Banking 1.20x) that inflates sector-level IC."},
        ])
        limitations.to_excel(writer, sheet_name="Known Limitations", index=False)

        if not raw_df.empty:
            raw_df.to_excel(writer, sheet_name="Raw Data", index=False)

    print(f"\n  Report saved: {path}")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scoring Engine Validation")
    parser.add_argument("--stocks", type=int, default=100, help="Number of stocks to validate (default 100)")
    parser.add_argument("--windows", type=int, default=6, help="Number of walk-forward windows (default 6)")
    parser.add_argument("--forward-days", type=int, default=30, help="Forward return period in days (default 30)")
    args = parser.parse_args()

    symbols = load_stock_list(args.stocks)
    print(f"\n  Loaded {len(symbols)} stocks from stock_list_template.csv")

    raw_df = run_walk_forward(symbols, n_windows=args.windows,
                              forward_days=args.forward_days)

    if raw_df.empty:
        print("\n  ERROR: No data generated. Check internet connection and yfinance availability.")
        return

    print(f"\n  Running analysis on {len(raw_df)} observations...\n")

    ic_df = analyze_ic(raw_df)
    quintile_df = analyze_quintiles(raw_df)
    hit_df = analyze_hit_rates(raw_df)
    component_ic_df = analyze_component_ic(raw_df)
    corr_df = analyze_correlation_matrix(raw_df)
    sector_avg_df, sector_ic_df = analyze_sector_bias(raw_df)
    stability_df = analyze_stability(raw_df)

    summary_df = build_summary(ic_df, quintile_df, hit_df, component_ic_df,
                               corr_df, sector_ic_df, stability_df)

    print_summary(summary_df, ic_df, quintile_df, hit_df)
    write_excel_report(summary_df, ic_df, quintile_df, hit_df,
                       component_ic_df, corr_df, sector_avg_df,
                       sector_ic_df, stability_df, raw_df)

    print(f"\n{'='*70}")
    print(f"  VALIDATION COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
