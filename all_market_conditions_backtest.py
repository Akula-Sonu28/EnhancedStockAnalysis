#!/usr/bin/env python3
"""
ALL MARKET CONDITIONS BACKTESTING SYSTEM
========================================

This system tests your scoring approach across:
1. BULL MARKETS (strong uptrends) 
2. BEAR MARKETS (strong downtrends)
3. SIDEWAYS MARKETS (range-bound/choppy)
4. VOLATILE MARKETS (high volatility periods)
5. CALM MARKETS (low volatility periods)

The goal is to validate system robustness across all market regimes
and identify which conditions favor your scoring approach.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

warnings.filterwarnings('ignore')

# Import our scoring systems
try:
    from hybrid_optimized_scoring import HybridOptimizedScoringEngine
    print("✅ Loaded HybridOptimizedScoringEngine")
except ImportError as e:
    print(f"❌ Failed to load HybridOptimizedScoringEngine: {e}")
    HybridOptimizedScoringEngine = None

try:
    from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer
    print("✅ Loaded EnhancedTop200StockAnalyzer")
except ImportError as e:
    print(f"❌ Failed to load EnhancedTop200StockAnalyzer: {e}")
    EnhancedTop200StockAnalyzer = None

class AllMarketConditionsBacktester:
    def __init__(self):
        self.nifty_symbol = "^NSEI"
        self.test_symbols = [
            # Banking (historically strong in your system)
            'SBIN.NS', 'ICICIBANK.NS', 'HDFCBANK.NS', 'AXISBANK.NS', 'KOTAKBANK.NS',
            'INDIANB.NS', 'PNB.NS', 'CANBK.NS', 'BANKBARODA.NS', 'FEDERALBNK.NS',
            'CUB.NS', 'KARURVYSYA.NS', 'UNIONBANK.NS', 'BANKINDIA.NS', 'CENTRALBK.NS',
            
            # Large Cap (stable performers)  
            'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS',
            'ITC.NS', 'HINDUNILVR.NS', 'NESTLEIND.NS', 'BAJAJFINSERV.NS',
            
            # Mid Cap (growth potential)
            'NMDC.NS', 'HINDALCO.NS', 'TATAMOTORS.NS', 'DRREDDY.NS', 'CIPLA.NS',
            'BPCL.NS', 'IOC.NS', 'GAIL.NS', 'OIL.NS', 'NTPC.NS'
        ]
        
        self.market_conditions = {}
        self.backtest_results = {}
        
        # Initialize scoring systems
        self.scoring_systems = {}
        if HybridOptimizedScoringEngine:
            self.scoring_systems['Hybrid'] = HybridOptimizedScoringEngine()
        if EnhancedTop200StockAnalyzer:
            self.scoring_systems['Enhanced'] = EnhancedTop200StockAnalyzer()
    
    def detect_market_conditions(self, lookback_years=3):
        """
        Detect different market conditions over the past few years
        """
        print("🔍 DETECTING MARKET CONDITIONS")
        print("-" * 50)
        
        try:
            # Get Nifty 50 historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_years*365)
            
            nifty = yf.Ticker(self.nifty_symbol)
            hist = nifty.history(start=start_date, end=end_date)
            
            if hist.empty:
                print("❌ Failed to get Nifty data")
                return
            
            # Calculate various market metrics
            hist['Returns'] = hist['Close'].pct_change()
            hist['SMA_50'] = hist['Close'].rolling(50).mean()
            hist['SMA_200'] = hist['Close'].rolling(200).mean()
            hist['Volatility'] = hist['Returns'].rolling(20).std() * np.sqrt(252)
            
            # Detect market conditions day by day
            conditions = []
            
            for i in range(200, len(hist)):  # Start after moving averages are available
                date = hist.index[i]
                price = hist['Close'].iloc[i]
                sma_50 = hist['SMA_50'].iloc[i]
                sma_200 = hist['SMA_200'].iloc[i]
                volatility = hist['Volatility'].iloc[i]
                
                # 30-day return for trend strength
                return_30d = (price - hist['Close'].iloc[i-30]) / hist['Close'].iloc[i-30]
                
                # Classify market condition
                if return_30d > 0.10 and price > sma_50 > sma_200:
                    condition = 'BULL_STRONG'
                elif return_30d > 0.05 and price > sma_50:
                    condition = 'BULL_MODERATE'
                elif return_30d < -0.10 and price < sma_50 < sma_200:
                    condition = 'BEAR_STRONG'
                elif return_30d < -0.05 and price < sma_50:
                    condition = 'BEAR_MODERATE'
                elif volatility > 0.30:
                    condition = 'VOLATILE'
                elif volatility < 0.15:
                    condition = 'CALM'
                else:
                    condition = 'SIDEWAYS'
                
                conditions.append({
                    'date': date,
                    'condition': condition,
                    'nifty_price': price,
                    'return_30d': return_30d * 100,
                    'volatility': volatility,
                    'trend_strength': price / sma_200 if sma_200 > 0 else 1
                })
            
            # Group by condition
            df_conditions = pd.DataFrame(conditions)
            
            for condition in df_conditions['condition'].unique():
                condition_data = df_conditions[df_conditions['condition'] == condition]
                self.market_conditions[condition] = {
                    'periods': len(condition_data),
                    'dates': condition_data['date'].tolist(),
                    'avg_return': condition_data['return_30d'].mean(),
                    'avg_volatility': condition_data['volatility'].mean(),
                    'sample_dates': condition_data['date'].sample(min(10, len(condition_data))).tolist()
                }
            
            # Print summary
            print(f"📊 Market Condition Analysis (Last {lookback_years} years):")
            print(f"{'Condition':<15} {'Periods':<10} {'Avg Return':<12} {'Volatility':<12}")
            print("-" * 55)
            
            for condition, data in self.market_conditions.items():
                print(f"{condition:<15} {data['periods']:<10} {data['avg_return']:+.2f}%     {data['avg_volatility']:.1%}")
            
            return df_conditions
            
        except Exception as e:
            print(f"❌ Error detecting market conditions: {e}")
            return None
    
    def fetch_stock_data_for_date(self, symbol, analysis_date, days_before=100, days_after=60):
        """
        Fetch stock data around a specific analysis date
        """
        try:
            start_date = analysis_date - timedelta(days=days_before)
            end_date = analysis_date + timedelta(days=days_after)
            
            yahoo_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
            stock = yf.Ticker(yahoo_symbol)
            
            hist = stock.history(start=start_date, end=end_date)
            if hist.empty or len(hist) < 50:
                return None
            
            # Find analysis date in data
            analysis_idx = None
            for i, date in enumerate(hist.index):
                if date.date() >= analysis_date.date():
                    analysis_idx = i
                    break
            
            if analysis_idx is None or analysis_idx < 50:
                return None
            
            # Get data up to analysis date for scoring
            analysis_hist = hist.iloc[:analysis_idx+1]
            
            # Get forward data for returns calculation
            forward_hist = hist.iloc[analysis_idx:analysis_idx+min(60, len(hist)-analysis_idx)]
            
            if len(forward_hist) < 30:  # Need at least 30 days forward
                return None
            
            # Calculate stock metrics for analysis date
            stock_data = self._calculate_stock_metrics(analysis_hist, symbol)
            
            # Calculate forward returns
            entry_price = analysis_hist['Close'].iloc[-1]
            returns_data = {}
            
            for days in [7, 15, 30, 45, 60]:
                if len(forward_hist) > days:
                    exit_price = forward_hist['Close'].iloc[min(days, len(forward_hist)-1)]
                    returns_data[f'return_{days}d'] = ((exit_price - entry_price) / entry_price) * 100
            
            return {
                'stock_data': stock_data,
                'returns': returns_data,
                'analysis_date': analysis_date,
                'entry_price': entry_price
            }
            
        except Exception as e:
            return None
    
    def _calculate_stock_metrics(self, hist, symbol):
        """Calculate comprehensive stock metrics for scoring"""
        try:
            closes = hist['Close']
            volumes = hist['Volume']
            
            # Get basic info
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
            except:
                info = {}
            
            # Technical indicators
            rsi = self._calculate_rsi(closes)
            sma_20 = closes.rolling(20).mean().iloc[-1]
            sma_50 = closes.rolling(50).mean().iloc[-1]
            
            # Price changes
            current_price = closes.iloc[-1]
            price_change_1w = ((current_price - closes.iloc[-5]) / closes.iloc[-5]) * 100 if len(closes) > 5 else 0
            price_change_1m = ((current_price - closes.iloc[-20]) / closes.iloc[-20]) * 100 if len(closes) > 20 else 0
            
            # Volume metrics
            volume_sma_20 = volumes.rolling(20).mean().iloc[-1]
            volume_ratio = volumes.iloc[-1] / volume_sma_20 if volume_sma_20 > 0 else 1
            
            # Volatility
            volatility = closes.pct_change().rolling(20).std().iloc[-1] * 100
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'volume': volumes.iloc[-1],
                'market_cap': info.get('marketCap', 1000000000),
                'pe_ratio': info.get('trailingPE', 15),
                'pb_ratio': info.get('priceToBook', 1.5),
                'debt_to_equity': info.get('debtToEquity', 50),
                'roe': info.get('returnOnEquity', 0.10),
                'rsi': rsi,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'price_change_1w': price_change_1w,
                'price_change_1m': price_change_1m,
                'volume_sma_20': volume_sma_20,
                'volume_ratio': volume_ratio,
                'volatility': volatility
            }
            
        except Exception as e:
            return {'symbol': symbol, 'current_price': 100}  # Minimal fallback
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not rsi.empty else 50
        except:
            return 50
    
    def backtest_market_condition(self, condition, sample_size=50):
        """
        Backtest scoring system performance in specific market condition
        """
        print(f"\n🧪 BACKTESTING {condition}")
        print("-" * 40)
        
        if condition not in self.market_conditions:
            print(f"❌ No data for condition: {condition}")
            return None
        
        # Get sample dates for this condition
        available_dates = self.market_conditions[condition]['sample_dates'][:sample_size]
        
        print(f"📅 Testing {len(available_dates)} periods")
        print(f"📊 Sample dates: {[d.strftime('%Y-%m-%d') for d in available_dates[:3]]}...")
        
        results = []
        
        for date_idx, test_date in enumerate(available_dates):
            if date_idx % 10 == 0:
                print(f"   Progress: {date_idx+1}/{len(available_dates)}")
            
            date_results = []
            
            # Test a subset of stocks for each date (for speed)
            test_stocks = self.test_symbols[:20]  # First 20 for faster testing
            
            for symbol in test_stocks:
                stock_result = self.fetch_stock_data_for_date(symbol, test_date)
                
                if stock_result is None:
                    continue
                
                # Score with available systems
                scores = {}
                if 'Hybrid' in self.scoring_systems:
                    try:
                        hybrid_score = self.scoring_systems['Hybrid'].calculate_hybrid_score(
                            symbol, stock_result['stock_data']
                        )
                        scores['Hybrid'] = hybrid_score['hybrid_score']
                    except Exception as e:
                        scores['Hybrid'] = 50
                
                # Record result
                for days in [15, 30, 45]:
                    if f'return_{days}d' in stock_result['returns']:
                        date_results.append({
                            'date': test_date,
                            'symbol': symbol,
                            'condition': condition,
                            'hybrid_score': scores.get('Hybrid', 50),
                            'forward_return': stock_result['returns'][f'return_{days}d'],
                            'holding_days': days,
                            'entry_price': stock_result['entry_price']
                        })
            
            results.extend(date_results)
        
        if not results:
            print(f"❌ No valid results for {condition}")
            return None
        
        # Analyze results
        df = pd.DataFrame(results)
        
        analysis = {
            'condition': condition,
            'total_tests': len(results),
            'avg_return': df['forward_return'].mean(),
            'median_return': df['forward_return'].median(),
            'success_rate': (df['forward_return'] > 0).mean() * 100,
            'volatility': df['forward_return'].std(),
            'best_return': df['forward_return'].max(),
            'worst_return': df['forward_return'].min(),
            'raw_results': results
        }
        
        # Score correlation analysis
        if 'hybrid_score' in df.columns:
            analysis['score_correlation'] = df['hybrid_score'].corr(df['forward_return'])
            
            # Quintile analysis
            df['score_quintile'] = pd.qcut(df['hybrid_score'], 5, labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
            quintile_performance = df.groupby('score_quintile')['forward_return'].agg(['mean', 'count'])
            analysis['quintile_performance'] = quintile_performance.to_dict()
        
        print(f"✅ {condition} Analysis Complete:")
        print(f"   Tests: {analysis['total_tests']}")
        print(f"   Avg Return: {analysis['avg_return']:+.2f}%")
        print(f"   Success Rate: {analysis['success_rate']:.1f}%")
        if 'score_correlation' in analysis:
            print(f"   Score Correlation: {analysis['score_correlation']:+.3f}")
        
        return analysis
    
    def run_comprehensive_market_backtest(self):
        """
        Run backtests across all market conditions
        """
        print("=" * 80)
        print("📊 ALL MARKET CONDITIONS COMPREHENSIVE BACKTEST")
        print("=" * 80)
        
        # Step 1: Detect market conditions
        conditions_df = self.detect_market_conditions(lookback_years=2)
        if conditions_df is None:
            print("❌ Failed to detect market conditions")
            return
        
        # Step 2: Backtest each condition
        print(f"\n🚀 RUNNING BACKTESTS ACROSS ALL CONDITIONS")
        print("=" * 60)
        
        for condition in self.market_conditions.keys():
            result = self.backtest_market_condition(condition, sample_size=30)
            if result:
                self.backtest_results[condition] = result
        
        # Step 3: Generate comprehensive report
        self._generate_market_conditions_report()
        
        print(f"\n✅ ALL MARKET CONDITIONS BACKTEST COMPLETE!")
        return self.backtest_results
    
    def _generate_market_conditions_report(self):
        """Generate comprehensive market conditions analysis report"""
        print(f"\n" + "=" * 80)
        print("📈 MARKET CONDITIONS PERFORMANCE ANALYSIS")
        print("=" * 80)
        
        if not self.backtest_results:
            print("❌ No backtest results available")
            return
        
        # Performance summary table
        print(f"\n📊 PERFORMANCE BY MARKET CONDITION:")
        print("-" * 70)
        print(f"{'Condition':<15} {'Tests':<8} {'Avg Return':<12} {'Success %':<10} {'Correlation':<12}")
        print("-" * 70)
        
        summary_data = []
        
        for condition, results in self.backtest_results.items():
            correlation = results.get('score_correlation', 0)
            
            print(f"{condition:<15} {results['total_tests']:<8} {results['avg_return']:+8.2f}%    {results['success_rate']:7.1f}%   {correlation:+9.3f}")
            
            summary_data.append({
                'Condition': condition,
                'Tests': results['total_tests'],
                'Avg_Return': results['avg_return'],
                'Success_Rate': results['success_rate'],
                'Correlation': correlation,
                'Volatility': results['volatility']
            })
        
        # Find best and worst conditions
        if summary_data:
            best_condition = max(summary_data, key=lambda x: x['Avg_Return'])
            worst_condition = min(summary_data, key=lambda x: x['Avg_Return'])
            best_correlation = max(summary_data, key=lambda x: x['Correlation'])
            
            print(f"\n🏆 BEST PERFORMING CONDITION:")
            print(f"   {best_condition['Condition']}: {best_condition['Avg_Return']:+.2f}% avg return")
            
            print(f"\n📉 MOST CHALLENGING CONDITION:")
            print(f"   {worst_condition['Condition']}: {worst_condition['Avg_Return']:+.2f}% avg return")
            
            print(f"\n🎯 HIGHEST CORRELATION:")
            print(f"   {best_correlation['Condition']}: {best_correlation['Correlation']:+.3f} correlation")
        
        # Detailed condition analysis
        print(f"\n📋 DETAILED CONDITION ANALYSIS:")
        print("=" * 60)
        
        for condition, results in self.backtest_results.items():
            print(f"\n{condition}:")
            print(f"  Total Tests: {results['total_tests']}")
            print(f"  Average Return: {results['avg_return']:+.2f}%")
            print(f"  Success Rate: {results['success_rate']:.1f}%")
            print(f"  Best Return: {results['best_return']:+.2f}%")
            print(f"  Worst Return: {results['worst_return']:+.2f}%")
            print(f"  Volatility: {results['volatility']:.2f}%")
            
            if 'score_correlation' in results:
                print(f"  Score Correlation: {results['score_correlation']:+.3f}")
            
            # Quintile analysis if available
            if 'quintile_performance' in results:
                print(f"  Quintile Performance:")
                for quintile in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']:
                    if quintile in results['quintile_performance']['mean']:
                        avg_ret = results['quintile_performance']['mean'][quintile]
                        count = results['quintile_performance']['count'][quintile]
                        print(f"    {quintile}: {avg_ret:+.2f}% ({count} tests)")
        
        # Generate recommendations
        print(f"\n💡 MARKET-ADAPTIVE RECOMMENDATIONS:")
        print("=" * 60)
        
        recommendations = self._generate_adaptive_recommendations()
        for rec in recommendations:
            print(f"• {rec}")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save as JSON
        json_filename = f'market_conditions_backtest_{timestamp}.json'
        with open(json_filename, 'w') as f:
            # Convert datetime objects for JSON serialization
            json_results = {}
            for condition, results in self.backtest_results.items():
                json_results[condition] = results.copy()
                # Convert dates in raw_results
                for item in json_results[condition]['raw_results']:
                    item['date'] = item['date'].isoformat()
            json.dump(json_results, f, indent=2, default=str)
        
        # Save summary as CSV
        csv_filename = f'market_conditions_summary_{timestamp}.csv'
        pd.DataFrame(summary_data).to_csv(csv_filename, index=False)
        
        print(f"\n💾 Results saved:")
        print(f"   📊 {json_filename}")
        print(f"   📋 {csv_filename}")
    
    def _generate_adaptive_recommendations(self):
        """Generate market-adaptive trading recommendations"""
        recommendations = []
        
        if not self.backtest_results:
            return ["No backtest data available for recommendations"]
        
        # Find best and worst performing conditions
        performance_data = []
        for condition, results in self.backtest_results.items():
            performance_data.append({
                'condition': condition,
                'avg_return': results['avg_return'],
                'success_rate': results['success_rate'],
                'correlation': results.get('score_correlation', 0)
            })
        
        # Sort by average return
        performance_data.sort(key=lambda x: x['avg_return'], reverse=True)
        
        if len(performance_data) >= 2:
            best = performance_data[0]
            worst = performance_data[-1]
            
            recommendations.append(f"BEST Market Condition: {best['condition']} ({best['avg_return']:+.2f}% avg return)")
            recommendations.append(f"AVOID Market Condition: {worst['condition']} ({worst['avg_return']:+.2f}% avg return)")
        
        # Correlation-based recommendations
        high_corr = [p for p in performance_data if p['correlation'] > 0.3]
        if high_corr:
            best_corr = max(high_corr, key=lambda x: x['correlation'])
            recommendations.append(f"STRONGEST Predictive Power: {best_corr['condition']} ({best_corr['correlation']:+.3f} correlation)")
        
        # Success rate recommendations
        high_success = [p for p in performance_data if p['success_rate'] > 60]
        if high_success:
            best_success = max(high_success, key=lambda x: x['success_rate'])
            recommendations.append(f"HIGHEST Win Rate: {best_success['condition']} ({best_success['success_rate']:.1f}% success)")
        
        # General recommendations
        recommendations.extend([
            "Use higher position sizes during favorable market conditions",
            "Reduce exposure or go defensive during challenging conditions", 
            "Monitor market regime changes for strategy adjustments",
            "Consider market condition as additional scoring factor"
        ])
        
        return recommendations

if __name__ == "__main__":
    backtester = AllMarketConditionsBacktester()
    results = backtester.run_comprehensive_market_backtest()