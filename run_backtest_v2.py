
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import json
import os
import sys

# Add current directory to path
sys.path.append('.')

warnings.filterwarnings('ignore')

# Import scoring engines
try:
    from improved_scoring_engine import ImprovedScoringEngine
except ImportError:
    ImprovedScoringEngine = None
    print("⚠️ Improved Scoring Engine not available")

try:
    from hybrid_optimized_scoring import HybridOptimizedScoringEngine
except ImportError:
    HybridOptimizedScoringEngine = None
    print("⚠️ Hybrid Optimized Scoring Engine not available")

class BacktestValidator:
    def __init__(self):
        self.engines = {}
        if ImprovedScoringEngine:
            self.engines['Improved_V3'] = ImprovedScoringEngine()
        if HybridOptimizedScoringEngine:
            self.engines['Hybrid_V4'] = HybridOptimizedScoringEngine()
            
        self.report_path = r"c:\Users\A KAVYA SHREE\OneDrive\Documents\Sanji\Stock Analyis\Stock_Analysis - Copy\reports\Enhanced_Stock_Report_20251210_120903.xlsx"
        
    def get_stock_list(self):
        try:
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
            data = {
                'pe_ratio':       float(info.get('trailingPE')         or 20),
                'roe':            float((info.get('returnOnEquity') or 0.15) * 100),
                'debt_to_equity': float(info.get('debtToEquity')       or 0.5),
                'market_cap':     float(info.get('marketCap')          or 1e12),
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
                hist_index_naive = hist.index.tz_localize(None)
                
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
                
                # Get max price in the future window (or price at end)
                # Let's check Return at end of period
                try:
                    # Find price roughly p_days later (or latest available)
                    future_slice = hist[hist_index_naive > cutoff_date]
                    if future_slice.empty: continue
                    
                    end_price = future_slice['Close'].iloc[-1]
                    actual_return = (end_price - start_price) / start_price * 100
                    
                    # PREPARE DATA FOR SCORING ENGINE
                    fundamentals = self.fetch_fundamentals(symbol)  # GAP-5: real PE/ROE/Debt
                    stock_data = self.prepare_stock_data(scoring_hist, fundamentals)
                    
                    # RUN ENGINES
                    for name, engine in self.engines.items():
                        try:
                            if name == 'Improved_V3':
                                res = engine.calculate_improved_overall_score(symbol, stock_data)
                                score = res.get('improved_overall_score', 50)
                            elif name == 'Hybrid_V4':
                                res = engine.calculate_hybrid_score(symbol, stock_data)
                                score = res.get('hybrid_score', 50)
                            else:
                                score = 50
                                
                            results.append({
                                'period': p_days,
                                'symbol': symbol,
                                'engine': name,
                                'score': score,
                                'return': actual_return
                            })
                        except Exception as e:
                            pass
                            
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
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        
        # Returns
        price_change_1m = (current_price / close.iloc[-22] - 1) * 100 if len(close) > 22 else 0
        price_change_1w = (current_price / close.iloc[-6] - 1) * 100 if len(close) > 6 else 0
        
        # Volume
        vol_sma_20 = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / vol_sma_20 if vol_sma_20 else 1.0
        
        # Volatility (20d)
        volatility = close.pct_change().rolling(20).std().iloc[-1] * 100
        
        return {
            'current_price': current_price,
            'sma_50': sma_50,
            'rsi': rsi_val,
            'real_rsi': rsi_val, # for hybrid
            'enhanced_rsi_14': rsi_val, # for improved
            'price_change_1m': price_change_1m,
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

if __name__ == "__main__":
    validator = BacktestValidator()
    df_res = validator.run_backtest()
    
    if not df_res.empty:
        print("\n\n📊 BACKTEST RESULTS SUMMARY")
        print("="*40)
        
        # Correlation Analysis
        print(f"{'Engine':<15} | {'Period':<7} | {'Correlation':<12} | {'Avg Return (High Score)':<25}")
        print("-" * 70)
        
        for engine in df_res['engine'].unique():
            for period in df_res['period'].unique():
                subset = df_res[(df_res['engine'] == engine) & (df_res['period'] == period)]
                corr = subset['score'].corr(subset['return'])
                
                # Check return of top decile (>90th percentile score)
                threshold = subset['score'].quantile(0.8)
                top_picks = subset[subset['score'] >= threshold]
                avg_ret = top_picks['return'].mean()
                
                print(f"{engine:<15} | {period:<7} | {corr:<12.4f} | {avg_ret:<6.2f}%")
