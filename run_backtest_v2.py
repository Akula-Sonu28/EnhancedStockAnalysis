"""run_backtest_v2.py — Scoring accuracy validator and walk-forward backtest.

M7 Known limitation: The stock universe used by this validator may differ from
production (analyze_top200_stocks_enhanced.py). The BacktestValidator uses up to
50 random stocks from the latest report (or 5 fallback blue-chips), while
production analyzes up to 200 stocks. Backtest results should not be interpreted
as a comprehensive validation of the full production universe.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import json
import os
import sys
import glob
import logging

# Add current directory to path
sys.path.append('.')

warnings.filterwarnings('ignore')

# HI-02: Only HybridOptimizedScoringEngine is active; ImprovedScoringEngine removed.
try:
    from hybrid_optimized_scoring import HybridOptimizedScoringEngine
except ImportError:
    HybridOptimizedScoringEngine = None
    print("⚠️ Hybrid Optimized Scoring Engine not available")

class BacktestValidator:
    def __init__(self):
        self.engines = {}
        if HybridOptimizedScoringEngine:
            self.engines['Hybrid_V4'] = HybridOptimizedScoringEngine()
        reports = sorted(glob.glob('reports/Enhanced_Stock_Report_*.xlsx'))
        self.report_path = reports[-1] if reports else None
        if self.report_path:
            print(f"Using report: {self.report_path}")
        else:
            print("⚠️ No enhanced report found in reports/. Falling back to default stock list.")
        
    def get_stock_list(self):
        try:
            if not self.report_path or not os.path.exists(self.report_path):
                return ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
            print(f"Loading stocks from: {self.report_path}")
            xls = pd.ExcelFile(self.report_path)
            # Try to find a sheet with 'Complete Data' or just first sheet
            if 'Complete Data' in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name='Complete Data')
            else:
                df = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
            
            # Look for symbol column
            cols = [c for c in df.columns if 'symbol' in str(c).lower()]
            if cols:
                symbols = df[cols[0]].dropna().unique().tolist()
                print(f"Found {len(symbols)} stocks.")
                # Return 50 random stocks for broader validation
                import random
                if len(symbols) > 50:
                    return random.sample(symbols, 50)
                return symbols
            else:
                print("Symbol column not found.")
                return ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
        except Exception as e:
            print(f"Error loading stock list: {e}")
            return ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']

    def fetch_history(self, symbol, lookback_days=180):
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            hist = ticker.history(period=f"{lookback_days}d")
            return hist
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()

    def fetch_fundamentals(self, symbol):
        """GAP-5 FIX: Fetch real fundamental data from yfinance, cached per symbol.
        Note: these are current-year values (minor look-ahead bias) but far more
        accurate than the previous pe=20/roe=15 constants applied to all 500 stocks."""
        if not hasattr(self, '_fund_cache'):
            self._fund_cache = {}
        if symbol in self._fund_cache:
            return self._fund_cache[symbol]
        try:
            info = yf.Ticker(f"{symbol}.NS").info
            def _sf_bt(v, d):
                if v is None: return d
                try:
                    f = float(v)
                    return d if (np.isnan(f) or np.isinf(f)) else f
                except (TypeError, ValueError):
                    return d
            data = {
                'pe_ratio':       _sf_bt(info.get('trailingPE'), 20),
                'roe':            _sf_bt(info.get('returnOnEquity'), 0.15) * 100,
                'debt_to_equity': _sf_bt(info.get('debtToEquity'), 0.5),
                'market_cap':     _sf_bt(info.get('marketCap'), 1e12),
            }
        except Exception:
            data = {'pe_ratio': 20, 'roe': 15, 'debt_to_equity': 0.5, 'market_cap': 1e12}
        self._fund_cache[symbol] = data
        return data

    def prepare_data_slice(self, full_hist, cutoff_date):
        # Data available UP TO cutoff_date (for scoring)
        # We need enough history BEFORE cutoff date for indicators (e.g. 50 DMA)
        scoring_hist = full_hist[full_hist.index <= cutoff_date]
        if len(scoring_hist) < 50:
            return None
        return scoring_hist

    def run_backtest(self, test_periods=[30, 45, 60, 90]):
        symbols = self.get_stock_list()
        results = []
        
        print(f"\n🚀 Running Backtest on {len(symbols)} stocks for periods: {test_periods} days")
        
        for p_days in test_periods:
            print(f"\n--- Period: {p_days} Days ---")
            
            # We want to predict returns for the LAST p_days
            # So Scoring Date = Now - p_days
            end_date = datetime.now()
            cutoff_date = end_date - timedelta(days=p_days)
            # Need buffer for indicators (manual fetch might be needed if history fetch wasn't enough, but 180d should be fine)
            
            for symbol in symbols:
                hist = self.fetch_history(symbol, lookback_days=180) # 6 months
                if hist.empty: continue
                
                # Ensure both are naive or both are aware
                # yfinance returns tz-aware (usually local market time). cutoff_date is currently naive (datetime.now())
                # Let's make hist index naive
                hist_index_naive = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
                
                if hist_index_naive[-1] < cutoff_date:
                    # Stock might be delisted or data missing
                    continue
                
                # Slice data for SCORING (up to cutoff)
                # Use boolean masking on the naive index
                scoring_hist = hist[hist_index_naive <= cutoff_date]
                if len(scoring_hist) < 50: continue
                
                # Slice data for RETURN (cutoff to now)
                # Actually we just need price at cutoff and price at end
                start_price = scoring_hist['Close'].iloc[-1]
                if start_price == 0 or np.isnan(start_price):
                    continue
                
                # Get max price in the future window (or price at end)
                # Let's check Return at end of period
                try:
                    # Find price roughly p_days later (or latest available)
                    future_slice = hist[hist_index_naive > cutoff_date]
                    if future_slice.empty: continue
                    
                    end_price = future_slice['Close'].iloc[-1]
                    actual_return = (end_price - start_price) / start_price * 100 if start_price != 0 else 0
                    
                    # PREPARE DATA FOR SCORING ENGINE
                    fundamentals = self.fetch_fundamentals(symbol)  # GAP-5: real PE/ROE/Debt
                    stock_data = self.prepare_stock_data(scoring_hist, fundamentals)
                    
                    # RUN ENGINES
                    for name, engine in self.engines.items():
                        try:
                            res = engine.calculate_hybrid_score(symbol, stock_data)
                            score = res.get('hybrid_score', 50)
                                
                            results.append({
                                'period': p_days,
                                'symbol': symbol,
                                'engine': name,
                                'score': score,
                                'return': actual_return
                            })
                        except Exception as e:
                            logging.warning(f"Engine {name} failed for {symbol}: {e}")
                            
                except Exception as e:
                    print(f"Error processing {symbol}: {e}")
                    continue
                    
        return pd.DataFrame(results)

    def prepare_stock_data(self, df, fundamentals=None):
        # Convert DataFrame to dictionary expected by scoring engines
        # Need to calculate indicators manually since we are working with raw DF slice
        
        # Simple helper for tech indicators
        close = df['Close']
        volume = df['Volume']
        
        current_price = close.iloc[-1]
        
        # SMA 50
        sma_50 = close.rolling(50).mean().iloc[-1]
        
        # RSI 14
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        loss = loss.replace(0, np.nan)
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).fillna(50.0)
        rsi_val = rsi.iloc[-1]
        if np.isnan(rsi_val):
            rsi_val = 50.0
        
        # Returns
        _denom_22 = close.iloc[-22] if len(close) > 22 else 0
        price_change_1m = ((current_price / _denom_22 - 1) * 100) if (len(close) > 22 and _denom_22 != 0 and not np.isnan(_denom_22)) else 0
        _denom_6 = close.iloc[-6] if len(close) > 6 else 0
        price_change_1w = ((current_price / _denom_6 - 1) * 100) if (len(close) > 6 and _denom_6 != 0 and not np.isnan(_denom_6)) else 0
        
        # Volume
        vol_sma_20 = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / vol_sma_20 if (vol_sma_20 and not np.isnan(vol_sma_20)) else 1.0
        
        # Volatility (20d)
        volatility = close.pct_change().rolling(20).std().iloc[-1] * 100
        
        return {
            'current_price': current_price,
            'sma_50': sma_50,
            'rsi': rsi_val,
            'real_rsi': rsi_val, # for hybrid
            'enhanced_rsi_14': rsi_val, # for improved
            'price_change_1m': price_change_1m,
            'enhanced_price_change_20d': price_change_1m,
            'price_change_1w': price_change_1w,
            'volume': volume.iloc[-1],
            'volume_sma_20': vol_sma_20,
            'volume_ratio': vol_ratio,
            'enhanced_volume_ratio': vol_ratio,
            'volatility': volatility,
            
            # GAP-5 FIX: Real fundamentals (fetched once per run, cached per symbol).
            # Note: current-year values introduce minor look-ahead bias, but are far
            # more accurate than pe=20/roe=15 applied uniformly to all 500 stocks.
            'pe_ratio':       (fundamentals or {}).get('pe_ratio', 20),
            'roe':            (fundamentals or {}).get('roe', 15),
            'debt_to_equity': (fundamentals or {}).get('debt_to_equity', 0.5),
            'market_cap':     (fundamentals or {}).get('market_cap', 1000000000000)
        }

class WalkForwardBacktest:
    """
    Rolling-window walk-forward backtest.
    Score at T, measure return at T+forward_days, roll forward by step_days.
    Fundamentals are fetched once and re-used (minor look-ahead for fundamentals
    but no price look-ahead).
    """

    def __init__(self, symbols=None, forward_days=30, step_days=30,
                 total_windows=6, history_days=365):
        self.validator = BacktestValidator()
        self.symbols = symbols or self.validator.get_stock_list()
        self.forward_days = forward_days
        self.step_days = step_days
        self.total_windows = total_windows
        self.history_days = history_days

    def run(self):
        """Execute the walk-forward backtest and return a DataFrame of results."""
        all_results = []
        now = datetime.now()

        for w in range(self.total_windows):
            score_date = now - timedelta(days=self.forward_days + w * self.step_days)
            eval_date = score_date + timedelta(days=self.forward_days)
            window_label = score_date.strftime('%Y-%m-%d')
            print(f"\n[Window {w+1}/{self.total_windows}] Score@{window_label}  Eval@{eval_date.strftime('%Y-%m-%d')}")

            for symbol in self.symbols:
                try:
                    hist = self.validator.fetch_history(symbol, lookback_days=self.history_days)
                    if hist.empty or len(hist) < 60:
                        continue

                    idx = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
                    scoring_hist = hist[idx <= score_date]
                    if len(scoring_hist) < 50:
                        continue

                    future_hist = hist[(idx > score_date) & (idx <= eval_date)]
                    if future_hist.empty:
                        continue

                    start_price = scoring_hist['Close'].iloc[-1]
                    if start_price == 0 or np.isnan(start_price):
                        continue
                    end_price = future_hist['Close'].iloc[-1]
                    actual_return = (end_price - start_price) / start_price * 100

                    fundamentals = self.validator.fetch_fundamentals(symbol)
                    stock_data = self.validator.prepare_stock_data(scoring_hist, fundamentals)

                    for name, engine in self.validator.engines.items():
                        try:
                            res = engine.calculate_hybrid_score(symbol, stock_data)
                            score = res.get('hybrid_score', 50)

                            all_results.append({
                                'window': window_label,
                                'symbol': symbol,
                                'engine': name,
                                'score': score,
                                'return': actual_return,
                                'start_price': start_price,
                                'end_price': end_price,
                            })
                        except Exception as e:
                            logging.warning(f"Walk-forward engine failed for {symbol}: {e}")
                except Exception as e:
                    print(f"  Skip {symbol}: {e}")

        df = pd.DataFrame(all_results)
        if df.empty:
            print("No results generated.")
            return df

        print("\n\n" + "=" * 80)
        print("WALK-FORWARD BACKTEST RESULTS")
        print("=" * 80)
        print(f"{'Engine':<15} | {'Window':<12} | {'N':>4} | {'Corr':>8} | {'Top-20% Ret':>12} | {'Bot-20% Ret':>12} | {'Spread':>8}")
        print("-" * 85)

        for engine in df['engine'].unique():
            for window in sorted(df['window'].unique()):
                sub = df[(df['engine'] == engine) & (df['window'] == window)]
                if len(sub) < 5:
                    continue
                corr = sub['score'].corr(sub['return'])
                q80 = sub['score'].quantile(0.80)
                q20 = sub['score'].quantile(0.20)
                top_ret = sub[sub['score'] >= q80]['return'].mean()
                bot_ret = sub[sub['score'] <= q20]['return'].mean()
                spread = top_ret - bot_ret
                print(f"{engine:<15} | {window:<12} | {len(sub):>4} | {corr:>8.4f} | {top_ret:>11.2f}% | {bot_ret:>11.2f}% | {spread:>7.2f}%")

        for engine in df['engine'].unique():
            sub = df[df['engine'] == engine]
            corr = sub['score'].corr(sub['return'])
            q80 = sub['score'].quantile(0.80)
            q20 = sub['score'].quantile(0.20)
            top_ret = sub[sub['score'] >= q80]['return'].mean()
            bot_ret = sub[sub['score'] <= q20]['return'].mean()
            print(f"\n  {engine} OVERALL — N={len(sub)}, Corr={corr:.4f}, Top-20%={top_ret:.2f}%, Bot-20%={bot_ret:.2f}%, Spread={top_ret - bot_ret:.2f}%")

        return df


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else 'snapshot'

    if mode == 'walkforward':
        wf = WalkForwardBacktest()
        wf.run()
    else:
        validator = BacktestValidator()
        df_res = validator.run_backtest()
        
        if not df_res.empty:
            print("\n\n📊 BACKTEST RESULTS SUMMARY")
            print("="*40)
            
            print(f"{'Engine':<15} | {'Period':<7} | {'Correlation':<12} | {'Avg Return (High Score)':<25}")
            print("-" * 70)
            
            for engine in df_res['engine'].unique():
                for period in df_res['period'].unique():
                    subset = df_res[(df_res['engine'] == engine) & (df_res['period'] == period)]
                    corr = subset['score'].corr(subset['return'])
                    
                    threshold = subset['score'].quantile(0.8)
                    top_picks = subset[subset['score'] >= threshold]
                    avg_ret = top_picks['return'].mean()
                    
                    print(f"{engine:<15} | {period:<7} | {corr:<12.4f} | {avg_ret:<6.2f}%")
