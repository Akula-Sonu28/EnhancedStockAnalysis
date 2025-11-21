#!/usr/bin/env python3
"""
COMPREHENSIVE SCORING SYSTEMS COMPARISON & BACKTEST
====================================================

This script compares ALL available scoring systems:
1. CorrectedScoringEngine (Contrarian Value)
2. ImprovedScoringEngine (Momentum-based)  
3. OptimizedScoringFormula (Correlation-based)
4. Original System (from analyze_top200_stocks_enhanced.py)

For each system, we'll:
- Score the same stock universe
- Run identical backtests
- Compare performance metrics
- Identify the best approach
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

warnings.filterwarnings('ignore')

# Import all scoring systems
try:
    from corrected_scoring_engine import CorrectedScoringEngine
    print("✅ Loaded CorrectedScoringEngine")
except ImportError as e:
    print(f"❌ Failed to load CorrectedScoringEngine: {e}")
    CorrectedScoringEngine = None

try:
    from improved_scoring_engine import ImprovedScoringEngine
    print("✅ Loaded ImprovedScoringEngine")
except ImportError as e:
    print(f"❌ Failed to load ImprovedScoringEngine: {e}")
    ImprovedScoringEngine = None

try:
    from optimized_scoring_formula import calculate_optimized_score
    print("✅ Loaded OptimizedScoringFormula")
except ImportError as e:
    print(f"❌ Failed to load OptimizedScoringFormula: {e}")
    calculate_optimized_score = None

try:
    from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer
    print("✅ Loaded Original Enhanced System")
except ImportError as e:
    print(f"❌ Failed to load Enhanced System: {e}")
    EnhancedTop200StockAnalyzer = None

class ComprehensiveScoringComparison:
    def __init__(self):
        self.test_symbols = [
            # Banking sector (historically your focus)
            'MAHABANK.NS', 'SBIN.NS', 'CUB.NS', 'INDIANB.NS', 'GICRE.NS',
            'CANBK.NS', 'KARURVYSYA.NS', 'UNIONBANK.NS', 'J&KBANK.NS', 'PNB.NS',
            'IOB.NS', 'BANKBARODA.NS', 'ICICIBANK.NS', 'BANKINDIA.NS', 'CENTRALBK.NS',
            'YESBANK.NS', 'FEDERALBNK.NS', 'IDBI.NS', 'UCOBANK.NS', 'AXISBANK.NS',
            'AUBANK.NS', 'HDFCBANK.NS', 'KOTAKBANK.NS', 'UJJIVANSFB.NS',
            
            # Non-banking (for diversification)
            'NMDC.NS', 'RECLTD.NS', 'PFC.NS', 'WIPRO.NS', 'DRREDDY.NS', 
            'NESTLEIND.NS', 'HINDUNILVR.NS', 'BAJAJHLDNG.NS', 'MUTHOOTFIN.NS',
            'LICHSGFIN.NS', 'MOTILALOFS.NS'
        ]
        
        self.results = {}
        self.backtest_results = {}
        
        # Initialize available scoring systems
        self.scoring_systems = {}
        if CorrectedScoringEngine:
            self.scoring_systems['Corrected'] = CorrectedScoringEngine()
        if ImprovedScoringEngine:
            self.scoring_systems['Improved'] = ImprovedScoringEngine()
        if EnhancedTop200StockAnalyzer:
            self.scoring_systems['Original'] = EnhancedTop200StockAnalyzer()
        # Optimized formula doesn't have a class, we'll handle it separately
    
    def fetch_stock_data(self, symbol, days=200):
        """Fetch comprehensive stock data for analysis"""
        try:
            yahoo_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
            stock = yf.Ticker(yahoo_symbol)
            
            # Get historical data
            hist = stock.history(period=f"{days}d")
            if hist.empty or len(hist) < 50:
                return None
            
            # Get basic info
            info = stock.info
            
            # Calculate technical indicators
            stock_data = {
                'symbol': symbol,
                'current_price': hist['Close'].iloc[-1],
                'volume': hist['Volume'].iloc[-1],
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'pb_ratio': info.get('priceToBook', 0),
                'debt_to_equity': info.get('debtToEquity', 0),
                'roe': info.get('returnOnEquity', 0),
                'price_history': hist['Close'].tolist(),
                'volume_history': hist['Volume'].tolist(),
            }
            
            # Calculate technical indicators
            self._add_technical_indicators(stock_data, hist)
            
            return stock_data
            
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {e}")
            return None
    
    def _add_technical_indicators(self, stock_data, hist):
        """Add technical indicators to stock data"""
        closes = hist['Close']
        volumes = hist['Volume']
        
        # RSI
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        stock_data['rsi'] = rsi.iloc[-1] if not rsi.empty else 50
        
        # Moving averages
        stock_data['sma_20'] = closes.rolling(20).mean().iloc[-1]
        stock_data['sma_50'] = closes.rolling(50).mean().iloc[-1]
        stock_data['ema_12'] = closes.ewm(span=12).mean().iloc[-1]
        stock_data['ema_26'] = closes.ewm(span=26).mean().iloc[-1]
        
        # Price changes
        stock_data['price_change_1d'] = ((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2]) * 100
        stock_data['price_change_1w'] = ((closes.iloc[-1] - closes.iloc[-5]) / closes.iloc[-5]) * 100
        stock_data['price_change_1m'] = ((closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20]) * 100
        
        # Volume indicators
        stock_data['volume_sma_20'] = volumes.rolling(20).mean().iloc[-1]
        stock_data['volume_ratio'] = stock_data['volume'] / stock_data['volume_sma_20']
        
        # Volatility
        stock_data['volatility'] = closes.pct_change().rolling(20).std().iloc[-1] * 100
    
    def score_with_all_systems(self, stock_data):
        """Score a stock using all available systems"""
        scores = {}
        
        # Corrected Scoring Engine
        if 'Corrected' in self.scoring_systems:
            try:
                scores['Corrected'] = self.scoring_systems['Corrected'].calculate_total_score(stock_data)
            except Exception as e:
                print(f"❌ Corrected scoring failed for {stock_data['symbol']}: {e}")
                scores['Corrected'] = 0
        
        # Improved Scoring Engine
        if 'Improved' in self.scoring_systems:
            try:
                scores['Improved'] = self.scoring_systems['Improved'].calculate_total_score(stock_data)
            except Exception as e:
                print(f"❌ Improved scoring failed for {stock_data['symbol']}: {e}")
                scores['Improved'] = 0
        
        # Optimized Formula
        if calculate_optimized_score:
            try:
                scores['Optimized'] = calculate_optimized_score(stock_data)
            except Exception as e:
                print(f"❌ Optimized scoring failed for {stock_data['symbol']}: {e}")
                scores['Optimized'] = 0
        
        # Original Enhanced System (more complex - needs full analysis)
        if 'Original' in self.scoring_systems:
            try:
                # This would need the full analysis pipeline - simplified for now
                scores['Original'] = self._calculate_original_score(stock_data)
            except Exception as e:
                print(f"❌ Original scoring failed for {stock_data['symbol']}: {e}")
                scores['Original'] = 0
        
        return scores
    
    def _calculate_original_score(self, stock_data):
        """Simplified version of original scoring for comparison"""
        # Basic technical score
        rsi = stock_data.get('rsi', 50)
        price_change_1m = stock_data.get('price_change_1m', 0)
        
        # Basic fundamental score
        pe = stock_data.get('pe_ratio', 15)
        pb = stock_data.get('pb_ratio', 1.5)
        roe = stock_data.get('roe', 0.1)
        
        # Simple scoring logic (approximation)
        technical_score = max(0, 100 - rsi) + max(0, -price_change_1m)
        fundamental_score = (50 if pe > 0 and pe < 20 else 0) + (50 if pb > 0 and pb < 3 else 0)
        
        return (technical_score * 0.4 + fundamental_score * 0.6)
    
    def calculate_forward_returns(self, symbol, start_date, holding_days=60):
        """Calculate forward returns for backtesting"""
        try:
            yahoo_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
            stock = yf.Ticker(yahoo_symbol)
            
            end_date = start_date + timedelta(days=holding_days + 10)  # Buffer for weekends
            hist = stock.history(start=start_date, end=end_date)
            
            if len(hist) < holding_days:
                return None
            
            entry_price = hist['Close'].iloc[0]
            exit_price = hist['Close'].iloc[min(holding_days-1, len(hist)-1)]
            
            return ((exit_price - entry_price) / entry_price) * 100
            
        except Exception as e:
            return None
    
    def run_comprehensive_comparison(self):
        """Run the complete scoring comparison and backtest"""
        print("=" * 100)
        print("🔍 COMPREHENSIVE SCORING SYSTEMS COMPARISON")
        print("=" * 100)
        print(f"📊 Testing {len(self.test_symbols)} stocks")
        print(f"⚙️  Available systems: {list(self.scoring_systems.keys())}")
        
        # Step 1: Score all stocks with all systems
        print("\n📈 SCORING PHASE")
        print("-" * 50)
        
        all_stocks_data = []
        for i, symbol in enumerate(self.test_symbols):
            print(f"📊 Analyzing {symbol} ({i+1}/{len(self.test_symbols)})")
            
            stock_data = self.fetch_stock_data(symbol)
            if stock_data is None:
                continue
            
            scores = self.score_with_all_systems(stock_data)
            stock_data['scores'] = scores
            all_stocks_data.append(stock_data)
        
        # Step 2: Backtest each system
        print(f"\n🔬 BACKTESTING PHASE")
        print("-" * 50)
        
        # Test dates (monthly over last 6 months)
        end_date = datetime.now()
        test_dates = []
        for i in range(6):
            test_date = end_date - timedelta(days=30 * (i + 1))
            test_dates.append(test_date)
        
        print(f"📅 Test dates: {[d.strftime('%Y-%m-%d') for d in test_dates]}")
        
        # Run backtest for each system
        for system_name in self.scoring_systems.keys():
            print(f"\n🧪 Backtesting {system_name} System")
            self.backtest_results[system_name] = self._backtest_system(
                system_name, all_stocks_data, test_dates
            )
        
        # Step 3: Generate comparison report
        self._generate_comparison_report(all_stocks_data)
        
        print("\n✅ COMPREHENSIVE COMPARISON COMPLETE!")
        return all_stocks_data, self.backtest_results
    
    def _backtest_system(self, system_name, stocks_data, test_dates):
        """Backtest a specific scoring system"""
        results = []
        
        for test_date in test_dates:
            print(f"   📊 Testing {test_date.strftime('%Y-%m-%d')}")
            
            # Get scores and returns for this date
            date_results = []
            for stock_data in stocks_data:
                symbol = stock_data['symbol']
                score = stock_data['scores'].get(system_name, 0)
                
                # Calculate forward returns from this test date
                forward_return = self.calculate_forward_returns(symbol, test_date, 60)
                
                if forward_return is not None:
                    date_results.append({
                        'symbol': symbol,
                        'score': score,
                        'return': forward_return,
                        'test_date': test_date
                    })
            
            results.extend(date_results)
        
        # Calculate system performance metrics
        if results:
            df = pd.DataFrame(results)
            
            # Overall performance
            avg_return = df['return'].mean()
            median_return = df['return'].median()
            success_rate = (df['return'] > 0).mean() * 100
            
            # Quartile analysis
            df['score_quartile'] = pd.qcut(df['score'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
            quartile_performance = df.groupby('score_quartile')['return'].agg(['mean', 'median', 'count'])
            
            # Correlation
            correlation = df['score'].corr(df['return'])
            
            return {
                'system_name': system_name,
                'total_tests': len(results),
                'avg_return': avg_return,
                'median_return': median_return,
                'success_rate': success_rate,
                'score_return_correlation': correlation,
                'quartile_performance': quartile_performance.to_dict(),
                'raw_results': results
            }
        
        return None
    
    def _generate_comparison_report(self, stocks_data):
        """Generate comprehensive comparison report"""
        print("\n" + "=" * 100)
        print("📊 SCORING SYSTEMS COMPARISON REPORT")
        print("=" * 100)
        
        # Current scores comparison
        print("\n📈 CURRENT SCORES COMPARISON")
        print("-" * 80)
        
        comparison_df = []
        for stock_data in stocks_data:
            row = {'Symbol': stock_data['symbol']}
            for system, score in stock_data['scores'].items():
                row[f'{system}_Score'] = round(score, 1)
            comparison_df.append(row)
        
        df = pd.DataFrame(comparison_df)
        print(df.to_string(index=False))
        
        # Save detailed results
        df.to_csv('scoring_systems_comparison.csv', index=False)
        
        # Backtest performance comparison
        print(f"\n🏆 BACKTEST PERFORMANCE COMPARISON")
        print("-" * 80)
        
        performance_summary = []
        for system_name, results in self.backtest_results.items():
            if results:
                performance_summary.append({
                    'System': system_name,
                    'Avg Return': f"{results['avg_return']:.2f}%",
                    'Success Rate': f"{results['success_rate']:.1f}%",
                    'Correlation': f"{results['score_return_correlation']:.3f}",
                    'Total Tests': results['total_tests'],
                    'Q4 vs Q1': f"{results['quartile_performance']['mean']['Q4'] - results['quartile_performance']['mean']['Q1']:.2f}%"
                })
        
        if performance_summary:
            perf_df = pd.DataFrame(performance_summary)
            print(perf_df.to_string(index=False))
            
            # Save performance comparison
            perf_df.to_csv('backtest_performance_comparison.csv', index=False)
        
        # Detailed backtest results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f'detailed_backtest_results_{timestamp}.json', 'w') as f:
            # Convert datetime objects to strings for JSON serialization
            json_results = {}
            for system, results in self.backtest_results.items():
                if results:
                    json_results[system] = results.copy()
                    # Convert datetime objects in raw_results
                    for item in json_results[system]['raw_results']:
                        item['test_date'] = item['test_date'].isoformat()
            json.dump(json_results, f, indent=2)
        
        print(f"\n💾 Detailed results saved:")
        print(f"   📊 scoring_systems_comparison.csv")
        print(f"   🏆 backtest_performance_comparison.csv")
        print(f"   📋 detailed_backtest_results_{timestamp}.json")

if __name__ == "__main__":
    comparator = ComprehensiveScoringComparison()
    stocks_data, backtest_results = comparator.run_comprehensive_comparison()