
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta
import sys
import os
import contextlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

# Add paths to ensure imports work
sys.path.append('src')

# Import the analyzer class
from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer 
import analyze_top200_stocks_enhanced # Import module to patch its globals
import src.technical_analyzer  # Import the module to mock
import src.enhanced_fundamental_analyzer # Import module to mock fundamentals

# ==============================================================================
# CONFIGURATION
# ==============================================================================
BENCHMARK = "^NSEI"  # Nifty 50 Index

# Scenarios to Test
SCENARIOS = {
    "2019_SLOWDOWN": {"start": "2019-01-01", "end": "2019-12-31"},
    "2020_COVID_CRASH": {"start": "2020-01-01", "end": "2020-06-01"},
    "2021_BULL_RUN": {"start": "2021-01-01", "end": "2021-12-31"},
    "LONG_TERM_TEST": {"start": "2019-01-01", "end": "2024-12-30"},
    "MEGA_LONG_TERM_TEST": {"start": "2010-01-01", "end": "2025-11-30"},
    "PARTIAL_TEST": {"start": "2019-01-01", "end": "2019-04-01"}
}

# Global dictionary to hold historical data
HISTORY_CACHE = {}
SIMULATION_DATE = None

def load_comprehensive_universe():
    """Load stock universe ONLY from stock_list_template.csv"""
    hardcoded = [
        "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", 
        "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT",
        "HINDUNILVR", "AXISBANK", "BAJFINANCE", "ADANIENT", "MARUTI"
    ]
    try:
        # Load ONLY standard template
        if os.path.exists("stock_list_template.csv"):
            try:
                df = pd.read_csv("stock_list_template.csv")
                if 'Symbol' in df.columns:
                    stocks = [str(s).strip() for s in df['Symbol'].tolist()]
                    # Remove duplicates and sort
                    final_list = sorted(list(set(stocks)))
                    print(f"   ✅ Loaded {len(final_list)} stocks from stock_list_template.csv")
                    return final_list
            except Exception as e:
                print(f"   ⚠️ Error reading stock_list_template.csv: {e}")
        
        print("   ⚠️ stock_list_template.csv not found, using hardcoded fallback.")
        return hardcoded

    except Exception as e:
        print(f"Error loading universe: {e}")
        return hardcoded

    except Exception as e:
        print(f"Error loading universe: {e}")
        return hardcoded

STOCKS = load_comprehensive_universe()

# ==============================================================================
# MOCKING INFRASTRUCTURE
# ==============================================================================

class MockTicker:
    """Replaces yfinance.Ticker to serve cached data based on SIMULATION_DATE"""
    def __init__(self, ticker):
        self.ticker = ticker.replace('.NS', '')
        self.full_ticker = ticker
        
    def history(self, period="1y", interval="1d", start=None, end=None, **kwargs):
        # Get cached data
        df = HISTORY_CACHE.get(self.ticker)
        if df is None:
             df = HISTORY_CACHE.get(self.full_ticker)
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Filter data available UP TO simulation date (Point-in-Time)
        if SIMULATION_DATE:
            df = df.loc[df.index <= SIMULATION_DATE]
            
        # Handle explicit start/end if provided (overrides period)
        if start:
            s_date = pd.to_datetime(start).tz_localize(None) if pd.to_datetime(start).tzinfo is None else pd.to_datetime(start)
            # Ensure index is tz-naive for comparison if input is naive
            if df.index.tz is not None and s_date.tzinfo is None:
                df = df.copy()
                df.index = df.index.tz_localize(None)
            
            df = df.loc[df.index >= s_date]
            
        if end:
            e_date = pd.to_datetime(end).tz_localize(None) if pd.to_datetime(end).tzinfo is None else pd.to_datetime(end)
            if df.index.tz is not None and e_date.tzinfo is None:
                 if df.index.tz is not None: df.index = df.index.tz_localize(None)
            df = df.loc[df.index <= e_date]
            
        return df

    @property
    def info(self):
        # Return dummy info sufficient to prevent crashes
        return {
            'previousClose': 1000.0,
            'trailingPE': 20.0,
            'marketCap': 500000000000,
            'sector': 'Financial Services',
            'industry': 'Banks'
        }

# Global Monkeypatch
yf.Ticker = MockTicker

def safe_extract_scalar(val):
    """Robustly extract scalar float from Series/DataFrame/Scalar"""
    try:
        if isinstance(val, (int, float, np.number)):
            return float(val)
        if hasattr(val, 'values'):
            # If array/series, take first element
            if val.size > 0:
                return float(val.values.flatten()[0])
        if hasattr(val, 'iloc'):
            return float(val.iloc[0])
        return float(val)
    except:
        return 0.0

def mock_get_ohlcv(symbol, period="1y", interval="1d"):
    """Mock replacement for technical_analyzer.get_ohlcv"""
    ticker = MockTicker(symbol)
    return ticker.history(period, interval)

def mock_get_comprehensive_stock_data(symbol):
    """Mock fundamental data fetcher"""
    # Just return basic structure to satisfy the analyzer
    # The real scoring relies heavily on Technicals in this stress test context
    # unless we have fundamental history. For now, we mock reasonable defaults.
    
    # Try to get current price from history
    current_price = 100.0 # Safe default
    try:
        t = MockTicker(symbol)
        hist = t.history()
        if not hist.empty:
            val = hist['Close'].iloc[-1]
            current_price = safe_extract_scalar(val)
            if current_price <= 0: current_price = 100.0
    except:
        pass
        
    return {
        'current_price': float(current_price),
        'market_cap': 100000000000,
        'pe_ratio': 20.0,
        'roe': 15.0,
        'debt_to_equity': 0.5,
        'EPS': 10.0,
        'book_value': current_price * 0.3,
        'dividend_yield': 1.0,
        'quarterly_revenue_growth': 10.0,
        'quarterly_profit_growth': 10.0,
        'promoter_holding': 50.0,
        'pledged_promoter_holding': 0.0,
        'company_name': symbol
    }

# ==============================================================================
# BACKTEST LOGIC
# ==============================================================================

def fetch_data_for_scenario(scenario_name):
    """Prefetch all data for the scenario duration + buffer"""
    cfg = SCENARIOS[scenario_name]
    start_date = pd.to_datetime(cfg['start'])
    end_date = pd.to_datetime(cfg['end'])
    
    # Buffer: we need 1 year prior to start date for indicators
    fetch_start = start_date - relativedelta(years=1, months=2)
    fetch_end = end_date + relativedelta(months=2) # Buffer for forward returns
    
    print(f"\n📥 Fetching Data for {scenario_name} ({fetch_start.date()} to {fetch_end.date()})...")
    
    tickers = [f"{s}.NS" for s in STOCKS]
    # Ensure BENCHMARK is first to guarantee it gets fetched
    if BENCHMARK not in tickers:
        tickers.insert(0, BENCHMARK)
        
    # Batch download with retry and pause
    BATCH_SIZE = 20
    all_tickers = tickers
    # Deduplicate while preserving order (important if benchmark inserted)
    all_tickers = list(dict.fromkeys(all_tickers))
    
    total_batches = (len(all_tickers) + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"   Downloading {len(all_tickers)} stocks in {total_batches} batches...")
    
    for i in range(0, len(all_tickers), BATCH_SIZE):
        batch = all_tickers[i:i + BATCH_SIZE]
        print(f"   - Batch {i//BATCH_SIZE + 1}/{total_batches} ({len(batch)} stocks)...")
        
        try:
            # Download batch
            data = yf.download(batch, start=fetch_start, end=fetch_end, group_by='ticker', auto_adjust=True, progress=False, threads=True)
            
            # Process batch immediately to free memory/organize
            for t in batch:
                try:
                    # Clean ticker for cache key
                    clean_sym = t.replace('.NS', '')
                    
                    if len(batch) == 1:
                        df = data
                    else:
                        # Handle different yf download structures
                        if isinstance(data.columns, pd.MultiIndex):
                            if t not in data.columns.levels[0]:
                                continue
                            try:
                                df = data[t]
                            except KeyError:
                                continue
                        else:
                            # Scalar column structure (unlikely with group_by='ticker' but possible)
                            continue
                    
                    # Flatten MultiIndex if present
                    if isinstance(df.columns, pd.MultiIndex):
                        try:
                            # Try to find 'Close' in levels
                            levels = [0, 1]
                            for l in levels:
                                if 'Close' in df.columns.get_level_values(l):
                                    df.columns = df.columns.get_level_values(l)
                                    break
                        except:
                            pass
                    
                    # Remove duplicate columns
                    df = df.loc[:, ~df.columns.duplicated()]

                    # Basic validation
                    if df.empty or 'Close' not in df.columns:
                        continue
                        
                    HISTORY_CACHE[clean_sym] = df
                    HISTORY_CACHE[f"{clean_sym}.NS"] = df # Store with suffix too
                    
                except Exception as e:
                    pass
            
            # Pause to be nice to API
            time.sleep(1.0)
            
        except Exception as e:
            print(f"   ❌ Batch failed: {e}")
            time.sleep(2) # Longer pause on error
            
    print(f"✅ Data fetched for {len(HISTORY_CACHE)//2} assets.")

def run_simulation(scenario_name, top_n=20):
    global SIMULATION_DATE
    
    cfg = SCENARIOS[scenario_name]
    start_date = pd.to_datetime(cfg['start'])
    end_date = pd.to_datetime(cfg['end'])
    
    print(f"\n🚀 STARTING BACKTEST: {scenario_name}")
    print("=" * 60)
    
    # Initialize Analyzer
    analyzer = EnhancedTop200StockAnalyzer(max_workers=1) 
    
    # Patch functions
    original_get_ohlcv = src.technical_analyzer.get_ohlcv
    src.technical_analyzer.get_ohlcv = mock_get_ohlcv
    
    # Patch the function imported inside the analyzer module
    if hasattr(analyze_top200_stocks_enhanced, 'get_comprehensive_stock_data'):
        original_get_funds = analyze_top200_stocks_enhanced.get_comprehensive_stock_data
        analyze_top200_stocks_enhanced.get_comprehensive_stock_data = mock_get_comprehensive_stock_data
    else:
        # Fallback if structure changes
        original_get_funds = src.enhanced_fundamental_analyzer.get_comprehensive_stock_data
        src.enhanced_fundamental_analyzer.get_comprehensive_stock_data = mock_get_comprehensive_stock_data
    
    # Helper to analyze batch of stocks
    def analyze_batch(symbol_list):
        results = []
        for sym in symbol_list:
            try:
                # check if data exists
                hist = HISTORY_CACHE.get(sym)
                if hist is None: hist = HISTORY_CACHE.get(f"{sym}.NS")
                
                if hist is None or hist.empty:
                     continue
                     
                # STRICT VALIDATION: Check if data exists BEFORE simulation date with sufficient history
                valid_hist = hist[hist.index <= SIMULATION_DATE]
                if len(valid_hist) < 50: # Require at least 50 trading days
                    continue
                    
                # Check for NaNs in the recent data window
                recent = valid_hist['Close'].tail(30)
                if recent.isnull().any() or (recent == 0).any():
                     continue
                
                res = analyzer.analyze_single_stock(sym)
                if res and isinstance(res, dict) and 'status' in res and res['status'] != 'error':
                    results.append(res)
            except Exception as e:
                pass
        return results

    analysis_results = []
    
    # Initialize Portfolios (Start Value: 100)
    p_values = {
        'Legacy (V1)': 100.0,
        'Improved (V3)': 100.0,
        'Hybrid (V4)': 100.0,
        'Final (V4+ML)': 100.0
    }
    benchmark_value = 100.0
    
    start_time = time.time()
    months_processed = 0

    try:
        current_date = start_date
        while current_date <= end_date:
            SIMULATION_DATE = current_date
            
            # Check for Benchmark Data (Trading Day alignment)
            bench = HISTORY_CACHE.get('^NSEI')
            if bench is not None:
                idx = bench.index.get_indexer([current_date], method='pad')[0]
                if idx < 0:
                     current_date += relativedelta(months=1)
                     continue
                SIMULATION_DATE = bench.index[idx]
            
            print(f"\n📅 Simulation Date: {SIMULATION_DATE.date()}")
            
            # 1. Analyze Stocks
            results = analyze_batch(STOCKS)
            
            if not results:
                print("   ⚠️ No results generated")
                current_date += relativedelta(months=1)
                continue

            # 2. Portfolio Selection (Top N for each system)
            
            # V1: Legacy Score (phase1_blended_score)
            v1_picks = sorted(results, key=lambda x: float(x.get('phase1_blended_score', 0) or 0), reverse=True)[:top_n]
            v1_symbols = [r['symbol'] for r in v1_picks]

            # V3: Improved Score (improved_score_used)
            v3_picks = sorted(results, key=lambda x: float(x.get('improved_score_used', 0) or 0), reverse=True)[:top_n]
            v3_symbols = [r['symbol'] for r in v3_picks]
            
            # V4 Base: Hybrid Score (hybrid_score_used)
            v4b_picks = sorted(results, key=lambda x: float(x.get('hybrid_score_used', 0) or 0), reverse=True)[:top_n]
            v4b_symbols = [r['symbol'] for r in v4b_picks]
            
            # V4 Final: Final Blended (final_blended_score)
            v4f_picks = sorted(results, key=lambda x: float(x.get('final_blended_score', 0) or 0), reverse=True)[:top_n]
            v4f_symbols = [r['symbol'] for r in v4f_picks]
            
            print(f"   🤖 V1 (Legacy) Picks: {v1_symbols[:5]}")
            print(f"   🤖 V3 (Improved) Picks: {v3_symbols[:5]}")
            print(f"   🤖 V4 (Hybrid) Picks: {v4b_symbols[:5]}")
            print(f"   🤖 V4+ (Final) Picks: {v4f_symbols[:5]}")

            # 3. Calculate Performance (Next Month Return)
            next_month = current_date + relativedelta(months=1)
            
            # Helper to calc return
            def calc_portfolio_return(symbols):
                if not symbols: return 0.0
                total_ret = 0.0
                count = 0
                for sym in symbols:
                    try:
                        hist = HISTORY_CACHE.get(sym)
                        if hist is None: hist = HISTORY_CACHE.get(f"{sym}.NS")
                        if hist is None: continue

                        p_start_idx = hist.index.get_indexer([SIMULATION_DATE], method='pad')[0]
                        p_end = min(next_month, hist.index[-1])
                        p_end_idx = hist.index.get_indexer([p_end], method='pad')[0]
                        
                        v_start = hist.iloc[p_start_idx]['Close']
                        v_end = hist.iloc[p_end_idx]['Close']
                        
                        price_start = safe_extract_scalar(v_start)
                        price_end = safe_extract_scalar(v_end)

                        if price_start == 0: continue
                        ret = (price_end - price_start) / price_start
                        total_ret += ret
                        count += 1
                    except:
                        pass
                return total_ret / count if count > 0 else 0.0

            # Calc Returns
            r_v1 = calc_portfolio_return(v1_symbols)
            r_v3 = calc_portfolio_return(v3_symbols)
            r_v4b = calc_portfolio_return(v4b_symbols)
            r_v4f = calc_portfolio_return(v4f_symbols)
            
            # Benchmark Return
            bench_ret = 0.0
            if bench is not None:
                try:
                    b_start_idx = bench.index.get_indexer([SIMULATION_DATE], method='pad')[0]
                    b_end = min(next_month, bench.index[-1])
                    b_end_idx = bench.index.get_indexer([b_end], method='pad')[0]
                    b_v_start = safe_extract_scalar(bench.iloc[b_start_idx]['Close'])
                    b_v_end = safe_extract_scalar(bench.iloc[b_end_idx]['Close'])
                    if b_v_start != 0:
                        bench_ret = (b_v_end - b_v_start) / b_v_start
                except:
                    pass
            
            # Handle NaN/Inf in benchmark return
            if np.isnan(bench_ret) or np.isinf(bench_ret):
                bench_ret = 0.0
            
            # Update Portfolio Values
            p_values['Legacy (V1)'] *= (1 + r_v1)
            p_values['Improved (V3)'] *= (1 + r_v3)
            p_values['Hybrid (V4)'] *= (1 + r_v4b)
            p_values['Final (V4+ML)'] *= (1 + r_v4f)
            benchmark_value *= (1 + bench_ret)
            
            # Log
            print(f"   📈 Monthly: V1={r_v1:+.1%} | V3={r_v3:+.1%} | V4={r_v4b:+.1%} | V4+={r_v4f:+.1%} | Nifty={bench_ret:+.1%}")
            
            if r_v4f > bench_ret:
                print("   ✅ BEAT MARKET (V4+)")
            else:
                print("   ❌ UNDERPERFORMED (V4+)")
            
            # Store
            analysis_results.append({
                'date': current_date.date(),
                'v1_return': r_v1,
                'v3_return': r_v3,
                'v4b_return': r_v4b,
                'v4f_return': r_v4f,
                'benchmark_return': bench_ret,
                'v1_val': p_values['Legacy (V1)'],
                'v3_val': p_values['Improved (V3)'],
                'v4b_val': p_values['Hybrid (V4)'],
                'v4f_val': p_values['Final (V4+ML)'],
                'bench_val': benchmark_value
            })

            # Move to next month
            current_date += relativedelta(months=1)
            
    finally:
        # Restore original functions
        src.technical_analyzer.get_ohlcv = original_get_ohlcv
        if hasattr(analyze_top200_stocks_enhanced, 'get_comprehensive_stock_data'):
             analyze_top200_stocks_enhanced.get_comprehensive_stock_data = original_get_funds
        else:
             src.enhanced_fundamental_analyzer.get_comprehensive_stock_data = original_get_funds
    
    # Final Summary
    total_ret_bench = (benchmark_value - 100) / 100
    
    print("\n" + "="*60)
    print(f"📊 SCENARIO SUMMARY: {scenario_name}")
    print(f"   📅 Period: {start_date.date()} to {end_date.date()}")
    print("-" * 30)
    
    # Print sorted performance
    final_rets = {k: (v - 100)/100 for k, v in p_values.items()}
    sorted_systems = sorted(final_rets.items(), key=lambda x: x[1], reverse=True)
    
    for sys_name, ret in sorted_systems:
        print(f"   💰 {sys_name:<15}:  {ret:+.1%}  (Alpha: {ret - total_ret_bench:+.1%})")
        
    print("-" * 30)
    print(f"   🏢 Benchmark      :  {total_ret_bench:+.1%}")
    print("="*60 + "\n")

if __name__ == "__main__":
    # MEGA 15-YEAR TEST
    print("🚀 LAUNCHING MEGA 15-YEAR STRESS TEST (2010-2024) 🚀")
    
    # Load full universe (Template or Merged)
    STOCKS = load_comprehensive_universe()
    print(f"Loaded {len(STOCKS)} stocks for analysis.")
    
    scenario = "MEGA_LONG_TERM_TEST"
    fetch_data_for_scenario(scenario)
    run_simulation(scenario, top_n=20)
