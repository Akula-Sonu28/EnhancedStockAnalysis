#!/usr/bin/env python3
"""
RSI Pullback Weekly Scanner — standalone CLI.

Scans Nifty 200 stocks for RSI pullback entries (RSI 35-45, above 50 SMA, RSI rising).
Run weekly (e.g., every Monday) to find 1-2 short-term trade candidates.

Usage:
    python3 scripts/run_rsi_pullback.py
    python3 scripts/run_rsi_pullback.py --top 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description='RSI Pullback Weekly Scanner')
    parser.add_argument('--top', type=int, default=10, help='Max candidates to show (default 10)')
    parser.add_argument('--csv', type=str, default=None, help='Stock list CSV (default: nifty200)')
    args = parser.parse_args()

    import pandas as pd
    import yfinance as yf

    from src.rsi_pullback_scanner import scan_from_price_history

    stock_file = args.csv or str(ROOT / 'data' / 'nifty200_stocks.csv')
    try:
        df = pd.read_csv(stock_file, sep=None, engine='python')
    except Exception as e:
        print(f"Error loading {stock_file}: {e}")
        return

    sym_col = next((c for c in df.columns if 'symbol' in c.lower() or c == 'Symbol'), None)
    if sym_col is None:
        print("No 'symbol' column found in stock list")
        return

    symbols = df[sym_col].dropna().str.strip().tolist()
    print(f"RSI Pullback Scanner — scanning {len(symbols)} stocks...\n")

    history_dict = {}
    errors = 0
    for i, sym in enumerate(symbols):
        try:
            h = yf.Ticker(f"{sym}.NS").history(period='3mo', auto_adjust=True)
            if h.index.tz is not None:
                h.index = h.index.tz_localize(None)
            if len(h) >= 55:
                history_dict[sym] = h
        except Exception:
            errors += 1
        if (i + 1) % 50 == 0:
            print(f"  fetched {i + 1}/{len(symbols)}...")

    print(f"  loaded {len(history_dict)} stocks ({errors} errors)\n")

    results = scan_from_price_history(list(history_dict.keys()), history_dict)

    if results.empty:
        print("No RSI Pullback candidates found today.")
        print("Criteria: RSI 35-45, above 50-day SMA, RSI rising vs yesterday")
        return

    top = results.head(args.top)
    print("=" * 70)
    print("RSI PULLBACK CANDIDATES (buy pullback in uptrend, hold 5 days)")
    print("=" * 70)
    print(f"{'Symbol':12} {'Price':>10} {'RSI':>6} {'Prev RSI':>9} {'Dist 40':>8} {'Above SMA50':>12}")
    print("-" * 70)
    for _, r in top.iterrows():
        print(
            f"{r['symbol']:12} "
            f"{r['current_price']:>10.2f} "
            f"{r['rsi']:>6.1f} "
            f"{r.get('rsi_prev', 0):>9.1f} "
            f"{r['distance_to_40']:>8.1f} "
            f"{r['above_sma50_pct']:>+11.1f}%"
        )

    print(f"\nTotal candidates: {len(results)}, showing top {len(top)}")
    print("Strategy: Buy closest to RSI 40, hold 5 days, -3% stop. 60% WR proven.")


if __name__ == '__main__':
    main()
