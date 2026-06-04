#!/usr/bin/env python3
"""
Validate pre-breakout / coil / turbo gates on recent NSE breakouts (web-sourced),
checking T-2 and T-1 trading days before the breakout session.

Not limited to names from Enhanced_Stock_Report.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import get_config
from early_breakout_detector import EarlyBreakoutDetector
from src.breakout_radar import classify_breakout_tier
from src.turbo_entry import compute_turbo_score, evaluate_turbo_entry_gate

# Web-sourced Jun 1 2026 movers (HDFC Sky / ET / Outlook — not from project reports)
CASES = [
    ("WOCKPHARMA", "2026-06-01", "~+19%", "FDA Zaynich approval"),
    ("NSLNISP", "2026-06-01", "~+14%", "NSE top gainer Jun 1"),
    ("PTCIL", "2026-06-01", "~+14%", "NSE top gainer Jun 1"),
    ("NIITLTD", "2026-06-01", "~+20%", "NSE circuit gainer Jun 1"),
    ("COALINDIA", "2026-06-01", "~+4%", "Offtake data Jun 1"),
    ("INDIGO", "2026-06-01", "~+5%", "IndiGo rally Jun 1"),
    ("NMDC", "2026-06-01", "~+18%", "NMDC Ltd — steel/profit news cluster"),
    ("KPRMILL", "2026-05-27", "~+2.6%", "Post-earnings move (prior session check)"),
    ("TEGA", "2026-05-30", "B-IGNITE", "User radar name — Fri before weekend"),
]


def _rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] else 0
    return float(100 - (100 / (1 + rs))) if rs else 50.0


def _trading_days_before(hist: pd.DataFrame, breakout_date: str, n: int) -> Optional[pd.Timestamp]:
    target = pd.Timestamp(breakout_date)
    prior = hist[hist.index < target]
    if len(prior) < n:
        return None
    return prior.index[-n]


def build_row_from_hist(hist: pd.DataFrame, as_of: pd.Timestamp, symbol: str) -> Dict[str, Any]:
    h = hist[hist.index <= as_of].copy()
    if len(h) < 25:
        return {}
    close = h["Close"]
    vol = h["Volume"]
    cp = float(close.iloc[-1])
    chg1 = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) >= 2 else 0.0
    chg5 = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0.0
    h20 = float(h["High"].tail(20).max())
    dist20 = float(max(0.0, (h20 - cp) / h20 * 100)) if h20 > 0 else 0.0
    vol_avg = float(vol.tail(10).mean()) if len(vol) >= 10 else float(vol.mean())
    volr = float(vol.iloc[-1] / vol_avg) if vol_avg > 0 else 1.0
    volr_raw = float(vol.iloc[-1] / vol.iloc[-2]) if len(vol) >= 2 and vol.iloc[-2] > 0 else volr
    rsi = _rsi(close)

    # Proxy hybrid subscores from price action (universe-free; oracle % not computed)
    mom = float(np.clip(50 + chg5 * 2.5 + chg1 * 1.5, 0, 100))
    mtf = float(np.clip(55 + (chg5 if chg5 > 0 else 0) * 2 + (10 if close.iloc[-1] > close.tail(20).mean() else 0), 0, 100))
    vol_str = float(np.clip(40 + min(volr, 5) * 12, 0, 100))
    fund = 70.0
    blended = float(np.clip(52 + mom * 0.15 + mtf * 0.1, 0, 100))
    v2 = float(np.clip(50 + mom * 0.12 + mtf * 0.12, 0, 100))

    return {
        "symbol": symbol,
        "current_price": cp,
        "enhanced_price_change_1d": chg1,
        "enhanced_price_change_5d": chg5,
        "enhanced_volume_ratio": volr,
        "enhanced_volume_ratio_raw": volr_raw,
        "volume_ratio": volr,
        "real_rsi": rsi,
        "enhanced_rsi_14": rsi,
        "hybrid_momentum_technical": mom,
        "hybrid_multi_timeframe": mtf,
        "hybrid_fundamental_quality": fund,
        "hybrid_volume_strength": vol_str,
        "final_blended_score": blended,
        "hybrid_overall_score_v2": v2,
        "overall_score_with_value": blended,
        "risk_adjusted_score": blended,
        "dist_20d_high_pct": dist20,
        "high_20d": h20,
    }


def would_recommend(cfg, row: Dict[str, Any], pre: Dict[str, Any]) -> Dict[str, Any]:
    turbo = evaluate_turbo_entry_gate(row, cfg, new_this_week=0)
    tier, _, treasons = classify_breakout_tier(row, cfg)
    volr = float(row.get("enhanced_volume_ratio", 1))
    volr_raw = float(row.get("enhanced_volume_ratio_raw", volr))
    ignite_vol = float(getattr(cfg, "BREAKOUT_IGNITE_VOL_RATIO", 2.5))
    ignite_ret = float(getattr(cfg, "BREAKOUT_IGNITE_1D_MIN", 2.5))
    ignite_raw = (
        float(row.get("enhanced_price_change_1d", 0)) >= ignite_ret
        and volr_raw >= ignite_vol
    )
    pre_ok = bool(pre.get("pre_breakout_detected")) and float(pre.get("breakout_probability", 0)) >= 70
    coil_ok = tier in ("A-COIL", "A+-READY")
    ignite_ok = tier == "B-IGNITE" or ignite_raw
    turbo_ok = turbo.allowed
    # Current production NEW path (oracle not simulated — needs 500-name cross-section)
    legacy_new = turbo_ok and (pre_ok or coil_ok or ignite_ok)
    return {
        "pre_breakout": pre_ok,
        "pre_prob": round(float(pre.get("breakout_probability", 0)), 1),
        "breakout_tier": tier or "—",
        "turbo_pass": turbo_ok,
        "turbo_reasons": "; ".join(turbo.reasons[:2]),
        "ignite_raw": ignite_raw,
        "proxy_would_flag": legacy_new,
    }


def main() -> None:
    cfg = get_config()
    det = EarlyBreakoutDetector()
    rows: List[Dict[str, Any]] = []

    print("Recent breakout validation (T-2 / T-1 vs current gates)\n")
    print(f"{'Symbol':<12} {'Breakout':<12} {'Check':<12} {'Chg1d':>6} {'Pre':>5} {'Tier':<10} {'Turbo':>5} {'Flag?':>6}  Note")
    print("-" * 95)

    for symbol, breakout_str, move, note in CASES:
        ticker = f"{symbol}.NS"
        try:
            hist = yf.Ticker(ticker).history(start="2025-12-01", end="2026-06-05", auto_adjust=True)
        except Exception as e:
            print(f"{symbol:<12} fetch failed: {e}")
            continue
        if hist.empty:
            print(f"{symbol:<12} no history")
            continue
        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)

        for label, n in (("T-2", 2), ("T-1", 1)):
            as_of = _trading_days_before(hist, breakout_str, n)
            if as_of is None:
                continue
            row = build_row_from_hist(hist, as_of, symbol)
            if not row:
                continue
            h_slice = hist[hist.index <= as_of]
            pre = det.detect_pre_breakout_setup(h_slice, row)
            verdict = would_recommend(cfg, row, pre)
            chg1 = row["enhanced_price_change_1d"]
            flag = "YES" if verdict["proxy_would_flag"] else "no"
            print(
                f"{symbol:<12} {breakout_str:<12} {str(as_of.date()):<12} {chg1:>5.1f}% "
                f"{verdict['pre_prob']:>4.0f}% {verdict['breakout_tier']:<10} "
                f"{'Y' if verdict['turbo_pass'] else 'N':>5} {flag:>6}  {note[:35]}"
            )
            rows.append(
                {
                    "symbol": symbol,
                    "breakout_date": breakout_str,
                    "check_date": str(as_of.date()),
                    "offset": label,
                    "move": move,
                    "chg1d": chg1,
                    **verdict,
                }
            )

    # Summary
    if rows:
        t2 = [r for r in rows if r["offset"] == "T-2"]
        t1 = [r for r in rows if r["offset"] == "T-1"]
        print("\n--- Summary ---")
        print(f"T-2: proxy flag YES on {sum(1 for r in t2 if r['proxy_would_flag'])}/{len(t2)} cases")
        print(f"T-1: proxy flag YES on {sum(1 for r in t1 if r['proxy_would_flag'])}/{len(t1)} cases")
        print(f"T-2: pre-breakout >=70% on {sum(1 for r in t2 if r['pre_breakout'])}/{len(t2)}")
        print(f"T-1: pre-breakout >=70% on {sum(1 for r in t1 if r['pre_breakout'])}/{len(t1)}")
        print("\nNote: proxy_would_flag = turbo PASS AND (pre>=70% OR coil tier OR ignite).")
        print("Production also requires oracle top-20% (not simulated here).")


if __name__ == "__main__":
    main()
