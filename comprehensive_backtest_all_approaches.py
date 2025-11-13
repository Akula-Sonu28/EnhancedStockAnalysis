#!/usr/bin/env python3
"""
COMPREHENSIVE BACKTESTING OF ALL APPROACHES
Tests all scoring engines, strategies, and methodologies with unified framework
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

warnings.filterwarnings('ignore')

# Import all available scoring engines and approaches
try:
    from corrected_scoring_engine import CorrectedScoringEngine
    CORRECTED_AVAILABLE = True
except ImportError:
    print("⚠️ Corrected Scoring Engine not available")
    CORRECTED_AVAILABLE = False

try:
    from improved_scoring_engine import ImprovedScoringEngine
    IMPROVED_AVAILABLE = True
except ImportError:
    print("⚠️ Improved Scoring Engine not available")
    IMPROVED_AVAILABLE = False

try:
    from hybrid_optimized_scoring import HybridOptimizedScoringEngine
    HYBRID_AVAILABLE = True
except ImportError:
    print("⚠️ Hybrid Optimized Scoring Engine not available")
    HYBRID_AVAILABLE = False

class ComprehensiveBacktester:
    """
    Unified backtesting framework for all approaches
    """
    
    def __init__(self):
        self.version = "1.0"
        self.test_date = datetime.now()
        
        # Initialize scoring engines
        self.engines = {}
        if CORRECTED_AVAILABLE:
            self.engines['Corrected_V2'] = CorrectedScoringEngine()
        if IMPROVED_AVAILABLE:
            self.engines['Improved'] = ImprovedScoringEngine()
        if HYBRID_AVAILABLE:
            self.engines['Hybrid_V4'] = HybridOptimizedScoringEngine()
        
        # Test configuration
        self.test_periods = [7, 14, 21, 30]  # Different holding periods
        self.test_universes = ['current_portfolio', 'buy_candidates', 'random_selection']
        
        # Results storage
        self.results = {}
        
        print(f"🚀 Comprehensive Backtester Initialized")
        print(f"📊 Available Engines: {list(self.engines.keys())}")
    
    def get_stock_universe(self, universe_type='current_portfolio'):
        """Get different stock universes for testing"""
        
        try:
            if universe_type == 'current_portfolio':
                # Use current holdings
                df = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Current_Holdings')
                symbols = df['symbol'].tolist()
                print(f"📋 Current Portfolio: {len(symbols)} stocks")
                
            elif universe_type == 'buy_candidates':
                # Use buy candidates
                df = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Buy_Candidates')
                symbols = df['symbol'].tolist()
                print(f"🛒 Buy Candidates: {len(symbols)} stocks")
                
            elif universe_type == 'random_selection':
                # Use random selection from all scored stocks
                df = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='All_Stocks_Scored')
                # Select top 30 by score for testing
                symbols = df.nlargest(30, 'optimized_score')['symbol'].tolist()
                print(f"🎲 Random Selection: {len(symbols)} top-scored stocks")
                
            else:
                # Fallback to current holdings
                df = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Current_Holdings')
                symbols = df['symbol'].tolist()
            
            # Add .NS suffix for Indian stocks
            symbols_ns = [f"{symbol}.NS" for symbol in symbols]
            return symbols, symbols_ns
            
        except Exception as e:
            print(f"❌ Error getting universe {universe_type}: {e}")
            # Fallback to a small test set
            fallback = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
            return fallback, [f"{s}.NS" for s in fallback]
    
    def get_stock_data(self, symbol_ns, period_days=30):
        """Get historical stock data with error handling"""
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days + 10)  # Extra buffer
            
            # Fetch data
            ticker = yf.Ticker(symbol_ns)
            data = ticker.history(start=start_date, end=end_date)
            
            if len(data) < period_days:
                return None
                
            return data
            
        except Exception as e:
            print(f"⚠️ Error fetching {symbol_ns}: {e}")
            return None
    
    def calculate_simple_scoring(self, data, symbol):
        """Calculate simple scoring when advanced engines not available"""
        
        try:
            if len(data) < 20:
                return 50  # Neutral score
            
            # Simple technical scoring
            current_price = data['Close'].iloc[-1]
            sma_20 = data['Close'].rolling(20).mean().iloc[-1]
            volatility = data['Close'].pct_change().std() * 100
            
            # Simple momentum
            momentum_5d = (current_price / data['Close'].iloc[-6] - 1) * 100
            momentum_20d = (current_price / data['Close'].iloc[-21] - 1) * 100 if len(data) >= 21 else 0
            
            # Volume ratio
            avg_volume = data['Volume'].rolling(10).mean().iloc[-1]
            recent_volume = data['Volume'].iloc[-1]
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
            
            # Simple scoring formula
            score = 50  # Base score
            
            # Price momentum component (30%)
            if momentum_5d > 2:
                score += 15
            elif momentum_5d < -2:
                score -= 15
            
            if momentum_20d > 5:
                score += 15
            elif momentum_20d < -5:
                score -= 15
            
            # Trend component (30%)
            if current_price > sma_20:
                score += 15
            else:
                score -= 15
            
            # Volume component (20%)
            if volume_ratio > 1.2:
                score += 10
            elif volume_ratio < 0.8:
                score -= 10
            
            # Volatility component (20%) - prefer moderate volatility
            if 15 < volatility < 30:
                score += 10
            elif volatility > 40:
                score -= 15
            
            return max(0, min(100, score))
            
        except Exception as e:
            print(f"⚠️ Error in simple scoring for {symbol}: {e}")
            return 50
    
    def test_single_approach(self, engine_name, engine, symbols, symbols_ns, period_days, universe_type):
        """Test a single approach with given parameters"""
        
        print(f"\n🔍 Testing {engine_name} | Period: {period_days}d | Universe: {universe_type}")
        
        results = []
        successful_tests = 0
        
        for i, (symbol, symbol_ns) in enumerate(zip(symbols[:20], symbols_ns[:20])):  # Limit to 20 for speed
            try:
                # Get stock data
                data = self.get_stock_data(symbol_ns, period_days + 10)
                if data is None or len(data) < period_days + 5:
                    continue
                
                # Get initial price and score
                initial_price = data['Close'].iloc[-(period_days + 1)]
                final_price = data['Close'].iloc[-1]
                actual_return = (final_price / initial_price - 1) * 100
                
                # Calculate score using the engine or fallback
                if engine and hasattr(engine, 'calculate_corrected_overall_score'):
                    # For CorrectedScoringEngine
                    stock_data = self.prepare_stock_data_for_engine(data, symbol)
                    engine_result = engine.calculate_corrected_overall_score(symbol, stock_data)
                    predicted_score = engine_result.get('corrected_overall_score', 50)
                    
                elif engine and hasattr(engine, 'calculate_score'):
                    # For other engines
                    stock_data = self.prepare_stock_data_for_engine(data, symbol)
                    predicted_score = engine.calculate_score(stock_data)
                    
                else:
                    # Fallback to simple scoring
                    predicted_score = self.calculate_simple_scoring(data, symbol)
                
                results.append({
                    'symbol': symbol,
                    'predicted_score': predicted_score,
                    'actual_return': actual_return,
                    'period_days': period_days,
                    'engine': engine_name
                })
                
                successful_tests += 1
                
                if i % 5 == 0:
                    print(f"   📊 Processed {i+1}/{min(20, len(symbols))} stocks...")
                
            except Exception as e:
                print(f"   ⚠️ Error with {symbol}: {e}")
                continue
        
        # Calculate performance metrics
        if results:
            df_results = pd.DataFrame(results)
            
            # Correlation between predicted scores and actual returns
            correlation = df_results['predicted_score'].corr(df_results['actual_return'])
            
            # Average return
            avg_return = df_results['actual_return'].mean()
            
            # Success rate (positive returns)
            success_rate = (df_results['actual_return'] > 0).mean() * 100
            
            # Alpha (excess return)
            market_return = df_results['actual_return'].mean()  # Simple proxy
            alpha = avg_return - market_return * 0.8  # Assume beta of 0.8
            
            performance_metrics = {
                'engine': engine_name,
                'universe': universe_type,
                'period_days': period_days,
                'correlation': correlation,
                'average_return': avg_return,
                'success_rate': success_rate,
                'alpha': alpha,
                'total_tests': successful_tests,
                'test_date': self.test_date.isoformat()
            }
            
            print(f"   ✅ {engine_name}: Corr={correlation:.3f}, Return={avg_return:.2f}%, Success={success_rate:.1f}%")
            
            return performance_metrics
        else:
            print(f"   ❌ No successful tests for {engine_name}")
            return None
    
    def prepare_stock_data_for_engine(self, price_data, symbol):
        """Prepare stock data in format expected by scoring engines"""
        
        try:
            if len(price_data) < 20:
                return {}
            
            current_price = price_data['Close'].iloc[-1]
            
            # Calculate basic metrics
            rsi = self.calculate_rsi(price_data['Close'])
            sma_20 = price_data['Close'].rolling(20).mean().iloc[-1]
            volatility = price_data['Close'].pct_change().std() * 100
            
            # Price changes
            price_change_5d = (current_price / price_data['Close'].iloc[-6] - 1) * 100 if len(price_data) >= 6 else 0
            
            # Volume ratio
            avg_volume = price_data['Volume'].rolling(10).mean().iloc[-1]
            recent_volume = price_data['Volume'].iloc[-1]
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
            
            # 52-week high/low simulation
            year_high = price_data['Close'].max()
            year_low = price_data['Close'].min()
            
            stock_data = {
                'current_price': current_price,
                'real_rsi': rsi,
                'enhanced_price_change_5d': price_change_5d,
                'enhanced_volume_ratio': volume_ratio,
                'year_high': year_high,
                'year_low': year_low,
                'pe_ratio': 15.0,  # Default values
                'pb_ratio': 2.0,
                'debt_to_equity': 0.5,
                'roe': 12.0,
                'momentum_flags': 2,
                'breakout_patterns': 1
            }
            
            return stock_data
            
        except Exception as e:
            print(f"⚠️ Error preparing data for {symbol}: {e}")
            return {}
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        except:
            return 50
    
    def run_comprehensive_backtest(self):
        """Run comprehensive backtest across all approaches"""
        
        print("=" * 80)
        print("🚀 COMPREHENSIVE BACKTESTING OF ALL APPROACHES")
        print("=" * 80)
        print()
        
        all_results = []
        
        # Test each engine across different configurations
        for universe_type in self.test_universes:
            print(f"\n📊 Testing Universe: {universe_type.upper()}")
            
            symbols, symbols_ns = self.get_stock_universe(universe_type)
            if not symbols:
                continue
            
            for period_days in self.test_periods:
                print(f"\n⏱️ Testing {period_days}-day period...")
                
                # Test each available engine
                for engine_name, engine in self.engines.items():
                    result = self.test_single_approach(
                        engine_name, engine, symbols, symbols_ns, period_days, universe_type
                    )
                    if result:
                        all_results.append(result)
                
                # Test simple baseline approach (no engine)
                result = self.test_single_approach(
                    'Simple_Baseline', None, symbols, symbols_ns, period_days, universe_type
                )
                if result:
                    all_results.append(result)
        
        # Store results
        self.results = all_results
        
        return all_results
    
    def generate_performance_summary(self):
        """Generate comprehensive performance summary"""
        
        if not self.results:
            print("❌ No results to summarize")
            return
        
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE BACKTEST RESULTS SUMMARY")
        print("=" * 80)
        
        df_results = pd.DataFrame(self.results)
        
        # Overall performance by engine
        print("\n🏆 OVERALL PERFORMANCE BY ENGINE:")
        print("-" * 50)
        
        engine_summary = df_results.groupby('engine').agg({
            'correlation': 'mean',
            'average_return': 'mean', 
            'success_rate': 'mean',
            'alpha': 'mean',
            'total_tests': 'sum'
        }).round(3)
        
        # Add composite score
        engine_summary['composite_score'] = (
            engine_summary['correlation'] * 0.3 +
            engine_summary['average_return'] * 0.025 +  # Scale down return
            engine_summary['success_rate'] * 0.01 +     # Scale down success rate
            engine_summary['alpha'] * 0.025             # Scale down alpha
        ).round(3)
        
        # Sort by composite score
        engine_summary = engine_summary.sort_values('composite_score', ascending=False)
        
        print(engine_summary.to_string())
        
        # Performance by period
        print(f"\n📅 PERFORMANCE BY HOLDING PERIOD:")
        print("-" * 45)
        
        period_summary = df_results.groupby('period_days').agg({
            'correlation': 'mean',
            'average_return': 'mean',
            'success_rate': 'mean',
            'alpha': 'mean'
        }).round(3)
        
        print(period_summary.to_string())
        
        # Performance by universe
        print(f"\n🌍 PERFORMANCE BY STOCK UNIVERSE:")
        print("-" * 40)
        
        universe_summary = df_results.groupby('universe').agg({
            'correlation': 'mean',
            'average_return': 'mean',
            'success_rate': 'mean',
            'alpha': 'mean'
        }).round(3)
        
        print(universe_summary.to_string())
        
        # Best performing combinations
        print(f"\n🥇 TOP 10 BEST PERFORMING COMBINATIONS:")
        print("-" * 50)
        
        # Calculate composite score for each test
        df_results['composite_score'] = (
            df_results['correlation'] * 0.3 +
            df_results['average_return'] * 0.025 +
            df_results['success_rate'] * 0.01 +
            df_results['alpha'] * 0.025
        ).round(3)
        
        top_combinations = df_results.nlargest(10, 'composite_score')[
            ['engine', 'universe', 'period_days', 'correlation', 'average_return', 
             'success_rate', 'alpha', 'composite_score']
        ]
        
        print(top_combinations.to_string(index=False))
        
        # Generate recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print("-" * 25)
        
        best_engine = engine_summary.index[0]
        best_correlation = engine_summary.loc[best_engine, 'correlation']
        best_return = engine_summary.loc[best_engine, 'average_return']
        
        print(f"🏆 BEST OVERALL ENGINE: {best_engine}")
        print(f"   • Correlation: {best_correlation:.3f}")
        print(f"   • Average Return: {best_return:.2f}%")
        print(f"   • Composite Score: {engine_summary.loc[best_engine, 'composite_score']:.3f}")
        print()
        
        # Best period
        best_period_idx = period_summary['composite_score'].idxmax() if 'composite_score' in period_summary.columns else period_summary['correlation'].idxmax()
        print(f"📅 OPTIMAL HOLDING PERIOD: {best_period_idx} days")
        print()
        
        # Best universe
        best_universe_idx = universe_summary['composite_score'].idxmax() if 'composite_score' in universe_summary.columns else universe_summary['correlation'].idxmax()
        print(f"🌍 BEST STOCK UNIVERSE: {best_universe_idx}")
        print()
        
        return df_results, engine_summary
    
    def save_results(self, filename=None):
        """Save results to files"""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comprehensive_backtest_results_{timestamp}"
        
        # Save to JSON
        json_file = f"{filename}.json"
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Save to Excel
        if self.results:
            excel_file = f"{filename}.xlsx"
            df_results = pd.DataFrame(self.results)
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                df_results.to_sheet(writer, sheet_name='All_Results', index=False)
                
                # Summary by engine
                engine_summary = df_results.groupby('engine').agg({
                    'correlation': 'mean',
                    'average_return': 'mean',
                    'success_rate': 'mean', 
                    'alpha': 'mean',
                    'total_tests': 'sum'
                }).round(3)
                engine_summary.to_excel(writer, sheet_name='Engine_Summary')
                
                # Summary by period
                period_summary = df_results.groupby('period_days').agg({
                    'correlation': 'mean',
                    'average_return': 'mean',
                    'success_rate': 'mean',
                    'alpha': 'mean'
                }).round(3)
                period_summary.to_excel(writer, sheet_name='Period_Summary')
        
        print(f"\n💾 Results saved:")
        print(f"   📄 JSON: {json_file}")
        if self.results:
            print(f"   📊 Excel: {excel_file}")

def main():
    """Main execution function"""
    
    print("🚀 Starting Comprehensive Backtesting of All Approaches...")
    print()
    
    # Initialize backtester
    backtester = ComprehensiveBacktester()
    
    # Run comprehensive backtest
    results = backtester.run_comprehensive_backtest()
    
    if results:
        # Generate summary
        df_results, engine_summary = backtester.generate_performance_summary()
        
        # Save results
        backtester.save_results()
        
        print("\n✅ Comprehensive backtesting completed successfully!")
        print(f"📊 Total tests completed: {len(results)}")
        print(f"🏆 Best performing engine: {engine_summary.index[0] if len(engine_summary) > 0 else 'N/A'}")
        
    else:
        print("❌ No successful backtest results generated")

if __name__ == "__main__":
    main()