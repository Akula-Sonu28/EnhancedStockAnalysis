#!/usr/bin/env python3
"""
Pre-Breakout VCP-Hybrid Scanner + Backtest

Reverse-engineered from Jun 1 2026 breakout stocks:
  WOCKPHARMA (+19%), NMDC (+18%), PTCIL (+14%), NSLNISP (+14%),
  NIITLTD (+20%), COALINDIA (+4%), INDIGO (+5%), KPRMILL (+2.6%),
  AIAENG (+4.3%)

Common pre-move fingerprint (T-2 / T-1):
  1. Price within ~7% of 20-day high (coiled near resistance)
  2. RSI 40-65 (not overbought, momentum building)
  3. Volume contracting (10d avg vol < 50d avg vol)
  4. Tight range (5-day range < 8% of price)
  5. Above 50-day SMA (trend intact)
  6. Positive 20d return (not in breakdown)

Strategy categories identified:
  A. COIL-VCP: Tight base near highs + volume dry-up (AIAENG, KPRMILL, COALINDIA)
  B. EARNINGS-DRIFT: Post-results momentum (NMDC, PTCIL, INDIGO)
  C. NEWS-GAP: Unpredictable catalyst gap (WOCKPHARMA FDA, NIIT)
  
We can only systematically catch A and partially B. C is excluded.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ─── Strategy parameters (tuned from reverse-engineering) ───

DIST_20D_HIGH_MAX = 7.0     # within 7% of 20-day high
RSI_MIN = 35.0
RSI_MAX = 68.0
VOL_CONTRACTION = True      # 10d avg vol < 50d avg vol
RANGE_5D_MAX = 8.0          # 5-day range < 8% of price
ABOVE_SMA50 = True          # price > 50 SMA
RET_20D_MIN = -2.0          # 20-day return > -2% (not collapsing)
BB_SQUEEZE_WIDTH_MAX = 15.0 # Bollinger bandwidth < 15%

HOLD_DAYS = 5               # hold for 5 trading days after signal
STOP_LOSS_PCT = -5.0        # stop at -5%


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def scan_day(hist: pd.DataFrame, day_idx: int) -> Optional[Dict[str, Any]]:
    """Check if the stock passes the pre-breakout screen on day_idx."""
    if day_idx < 55:
        return None
    
    close = hist['Close'].iloc[:day_idx + 1]
    high = hist['High'].iloc[:day_idx + 1]
    low = hist['Low'].iloc[:day_idx + 1]
    volume = hist['Volume'].iloc[:day_idx + 1]
    
    cp = float(close.iloc[-1])
    if cp <= 0:
        return None
    
    # 1. Distance to 20d high
    h20 = float(high.tail(20).max())
    dist_20d = (h20 - cp) / h20 * 100 if h20 > 0 else 999
    if dist_20d > DIST_20D_HIGH_MAX:
        return None
    
    # 2. RSI
    rsi_series = compute_rsi(close)
    rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else 50
    if rsi < RSI_MIN or rsi > RSI_MAX:
        return None
    
    # 3. Volume contraction
    if ABOVE_SMA50 and len(volume) >= 50:
        vol10 = float(volume.tail(10).mean())
        vol50 = float(volume.tail(50).mean())
        if vol10 > vol50:
            return None
    
    # 4. 5-day range
    if len(close) >= 5:
        h5 = float(high.tail(5).max())
        l5 = float(low.tail(5).min())
        range5 = (h5 - l5) / l5 * 100 if l5 > 0 else 999
        if range5 > RANGE_5D_MAX:
            return None
    
    # 5. Above 50 SMA
    if ABOVE_SMA50 and len(close) >= 50:
        sma50 = float(close.tail(50).mean())
        if cp < sma50:
            return None
    
    # 6. 20d return
    if len(close) >= 20:
        ret20 = (cp / float(close.iloc[-20]) - 1) * 100
        if ret20 < RET_20D_MIN:
            return None
    else:
        ret20 = 0
    
    # 7. Bollinger squeeze
    if len(close) >= 20:
        sma20 = float(close.tail(20).mean())
        std20 = float(close.tail(20).std())
        bb_width = (4 * std20 / sma20 * 100) if sma20 > 0 else 999
        if bb_width > BB_SQUEEZE_WIDTH_MAX:
            return None
    else:
        bb_width = 0
    
    vol10 = float(volume.tail(10).mean()) if len(volume) >= 10 else 0
    vol50 = float(volume.tail(50).mean()) if len(volume) >= 50 else vol10
    vol_ratio = vol10 / vol50 if vol50 > 0 else 1.0
    
    return {
        'price': cp,
        'dist_20d': round(dist_20d, 2),
        'rsi': round(rsi, 1),
        'vol_ratio_10_50': round(vol_ratio, 2),
        'range5_pct': round(range5 if len(close) >= 5 else 0, 2),
        'ret_20d': round(ret20, 2),
        'bb_width': round(bb_width, 2),
    }


def backtest_symbol(
    symbol: str,
    start: str = "2025-12-01",
    end: str = "2026-06-02",
) -> List[Dict[str, Any]]:
    """Backtest the pre-breakout screen on one symbol."""
    try:
        hist = yf.Ticker(f"{symbol}.NS").history(start=start, end=end, auto_adjust=True)
    except Exception:
        return []
    if hist.empty or len(hist) < 60:
        return []
    if hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)
    
    trades: List[Dict[str, Any]] = []
    cooldown_until = -1
    
    for i in range(55, len(hist)):
        if i <= cooldown_until:
            continue
        
        signal = scan_day(hist, i)
        if signal is None:
            continue
        
        entry_date = hist.index[i]
        entry_price = float(hist['Close'].iloc[i])
        
        # Hold for HOLD_DAYS, track max gain and exit
        exit_idx = min(i + HOLD_DAYS, len(hist) - 1)
        max_gain = 0
        exit_price = entry_price
        exit_reason = 'hold_expiry'
        actual_exit_idx = exit_idx
        
        for j in range(i + 1, exit_idx + 1):
            day_close = float(hist['Close'].iloc[j])
            day_low = float(hist['Low'].iloc[j])
            day_high = float(hist['High'].iloc[j])
            pnl_close = (day_close / entry_price - 1) * 100
            pnl_low = (day_low / entry_price - 1) * 100
            pnl_high = (day_high / entry_price - 1) * 100
            max_gain = max(max_gain, pnl_high)
            
            if pnl_low <= STOP_LOSS_PCT:
                exit_price = entry_price * (1 + STOP_LOSS_PCT / 100)
                exit_reason = 'stop_loss'
                actual_exit_idx = j
                break
            exit_price = day_close
            actual_exit_idx = j
        
        pnl = (exit_price / entry_price - 1) * 100
        exit_date = hist.index[actual_exit_idx]
        
        trades.append({
            'symbol': symbol,
            'entry_date': str(entry_date.date()),
            'entry_price': round(entry_price, 2),
            'exit_date': str(exit_date.date()),
            'exit_price': round(exit_price, 2),
            'pnl_pct': round(pnl, 2),
            'max_gain_pct': round(max_gain, 2),
            'exit_reason': exit_reason,
            **signal,
        })
        
        cooldown_until = actual_exit_idx + 2
    
    return trades


def main():
    stock_file = ROOT / "data" / "nifty200_stocks.csv"
    if not stock_file.exists():
        stock_file = ROOT / "data" / "stock_list_template.csv"
    
    df = pd.read_csv(stock_file, sep=None, engine='python')
    sym_col = next(c for c in df.columns if 'symbol' in c.lower() or c == 'Symbol')
    symbols = df[sym_col].dropna().str.strip().tolist()
    
    # Add our known breakout names for validation
    extra = ['WOCKPHARMA', 'NMDC', 'PTCIL', 'NSLNISP', 'NIITLTD', 'COALINDIA', 'INDIGO', 'KPRMILL', 'AIAENG']
    for s in extra:
        if s not in symbols:
            symbols.append(s)
    
    print(f"Backtesting pre-breakout VCP-hybrid on {len(symbols)} symbols (Dec 2025 - Jun 2026)")
    print(f"Parameters: dist20<{DIST_20D_HIGH_MAX}% RSI {RSI_MIN}-{RSI_MAX} vol_contract range5<{RANGE_5D_MAX}% bb<{BB_SQUEEZE_WIDTH_MAX}%")
    print(f"Hold {HOLD_DAYS}d, stop {STOP_LOSS_PCT}%\n")
    
    all_trades: List[Dict[str, Any]] = []
    errors = 0
    
    for i, sym in enumerate(symbols):
        try:
            trades = backtest_symbol(sym)
            all_trades.extend(trades)
            if (i + 1) % 25 == 0:
                print(f"  processed {i+1}/{len(symbols)}... ({len(all_trades)} signals so far)")
        except Exception as e:
            errors += 1
    
    if not all_trades:
        print("No trades found!")
        return
    
    tdf = pd.DataFrame(all_trades)
    
    # Stats
    total = len(tdf)
    winners = (tdf['pnl_pct'] > 0).sum()
    losers = (tdf['pnl_pct'] <= 0).sum()
    win_rate = winners / total * 100 if total > 0 else 0
    avg_pnl = tdf['pnl_pct'].mean()
    avg_win = tdf[tdf['pnl_pct'] > 0]['pnl_pct'].mean() if winners > 0 else 0
    avg_loss = tdf[tdf['pnl_pct'] <= 0]['pnl_pct'].mean() if losers > 0 else 0
    max_gain = tdf['pnl_pct'].max()
    max_loss = tdf['pnl_pct'].min()
    profit_factor = (tdf[tdf['pnl_pct']>0]['pnl_pct'].sum() / abs(tdf[tdf['pnl_pct']<0]['pnl_pct'].sum())) if losers > 0 and tdf[tdf['pnl_pct']<0]['pnl_pct'].sum() != 0 else 999
    stopped = (tdf['exit_reason'] == 'stop_loss').sum()
    
    # Big winners (>5%)
    big5 = (tdf['pnl_pct'] > 5).sum()
    big10 = (tdf['pnl_pct'] > 10).sum()
    
    # Did we catch known breakouts?
    known_breakouts = {
        'AIAENG': '2026-05-25', 'WOCKPHARMA': '2026-05-27', 'NMDC': '2026-05-27',
        'INDIGO': '2026-05-27', 'COALINDIA': '2026-05-27', 'KPRMILL': '2026-05-25',
    }
    
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS: Pre-Breakout VCP-Hybrid Scanner")
    print("=" * 80)
    print(f"Period:        Dec 2025 — Jun 2026")
    print(f"Universe:      {len(symbols)} NSE stocks")
    print(f"Total signals: {total}")
    print(f"Winners:       {winners} ({win_rate:.1f}%)")
    print(f"Losers:        {losers}")
    print(f"Avg P&L:       {avg_pnl:+.2f}%")
    print(f"Avg Win:       {avg_win:+.2f}%")
    print(f"Avg Loss:      {avg_loss:+.2f}%")
    print(f"Max Gain:      {max_gain:+.2f}%")
    print(f"Max Loss:      {max_loss:+.2f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Stop-outs:     {stopped} ({stopped/total*100:.1f}%)")
    print(f">5% gains:     {big5} ({big5/total*100:.1f}%)")
    print(f">10% gains:    {big10} ({big10/total*100:.1f}%)")
    print(f"Errors:        {errors}")
    
    # Check known breakout captures
    print(f"\n--- Known breakout capture check ---")
    for sym, target_date in known_breakouts.items():
        matches = tdf[(tdf['symbol'] == sym)]
        target = pd.Timestamp(target_date)
        near = matches[
            (pd.to_datetime(matches['entry_date']) >= target - timedelta(days=4)) &
            (pd.to_datetime(matches['entry_date']) <= target + timedelta(days=1))
        ]
        if not near.empty:
            r = near.iloc[0]
            print(f"  {sym:12} CAUGHT on {r['entry_date']} → {r['pnl_pct']:+.1f}% ({r['exit_reason']})")
        else:
            earliest = matches['entry_date'].min() if not matches.empty else 'never'
            print(f"  {sym:12} MISSED near {target_date} (first signal: {earliest})")
    
    # Top 15 trades
    print(f"\n--- Top 15 trades by P&L ---")
    top = tdf.nlargest(15, 'pnl_pct')
    for _, r in top.iterrows():
        print(f"  {r['symbol']:12} {r['entry_date']} {r['pnl_pct']:+6.1f}% (RSI {r['rsi']:.0f}, dist20 {r['dist_20d']:.1f}%, vr {r['vol_ratio_10_50']:.2f})")
    
    # Bottom 10 trades
    print(f"\n--- Bottom 10 trades by P&L ---")
    bot = tdf.nsmallest(10, 'pnl_pct')
    for _, r in bot.iterrows():
        print(f"  {r['symbol']:12} {r['entry_date']} {r['pnl_pct']:+6.1f}% (RSI {r['rsi']:.0f}, dist20 {r['dist_20d']:.1f}%)")
    
    # Monthly distribution
    tdf['month'] = pd.to_datetime(tdf['entry_date']).dt.to_period('M')
    print(f"\n--- Monthly P&L ---")
    for m, g in tdf.groupby('month'):
        print(f"  {m}: {len(g)} trades, avg {g['pnl_pct'].mean():+.2f}%, win rate {(g['pnl_pct']>0).mean()*100:.0f}%")
    
    # Save results
    out = ROOT / "data" / "prebreakout_backtest_results.csv"
    tdf.to_csv(out, index=False)
    print(f"\nResults saved to {out}")


if __name__ == "__main__":
    main()
