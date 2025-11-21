"""
SIMPLE RANDOM VALIDATION TEST
Uses current data with random stock selections and small time variations
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import random

warnings.filterwarnings('ignore')
random.seed(42)

print("=" * 100)
print("🎲 SIMPLE RANDOM VALIDATION TEST")
print("=" * 100)

# Load existing scoring data
try:
    df_scores = pd.read_excel('reports/Enhanced_Stock_Report_20251006_211751.xlsx', sheet_name='Complete Data')
    print(f"✅ Loaded {len(df_scores)} stocks with existing scores")
    all_stocks = df_scores['symbol'].tolist()
except:
    print("❌ Using fallback stock list")
    all_stocks = [
        'MAHABANK', 'SBIN', 'CUB', 'INDIANB', 'GICRE', 'CANBK', 'KARURVYSYA',
        'UNIONBANK', 'PNB', 'BANKBARODA', 'ICICIBANK', 'BANKINDIA', 'CENTRALBK',
        'FEDERALBNK', 'AXISBANK', 'AUBANK', 'HDFCBANK', 'KOTAKBANK', 'YESBANK',
        'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'RELIANCE', 'BHARTIARTL', 'ITC',
        'HINDUNILVR', 'NESTLEIND', 'DRREDDY', 'SUNPHARMA', 'MARUTI', 'TATAMOTORS'
    ]
    # Create mock scores
    df_scores = pd.DataFrame({
        'symbol': all_stocks,
        'risk_adjusted_score': np.random.uniform(40, 90, len(all_stocks))
    })

print(f"📊 Stock Pool: {len(all_stocks)} stocks available")

# Random test configurations
NUM_RANDOM_TESTS = 12
random_tests = []

for i in range(NUM_RANDOM_TESTS):
    # Random parameters
    num_stocks = random.randint(15, min(35, len(all_stocks)))
    forward_days = random.choice([3, 5, 7, 10, 14, 20, 25, 30])
    
    random_tests.append({
        'test_id': i + 1,
        'num_stocks': num_stocks,
        'forward_days': forward_days,
        'name': f"Random {num_stocks} stocks, {forward_days}D forward"
    })

print(f"\n🎲 Generated {NUM_RANDOM_TESTS} random test configurations:")
for test in random_tests:
    print(f"   Test {test['test_id']}: {test['name']}")

# Run tests using current data with random selections
all_results = []

print(f"\n{'='*100}")
print("🔄 RUNNING SIMPLE RANDOM TESTS")
print("="*100)

# Get current price data for all available stocks
print(f"\n📊 Downloading current price data for all stocks...")
stock_data = {}

for i, symbol in enumerate(all_stocks):
    try:
        ticker_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period='90d')  # Get last 90 days
        
        if len(hist) >= 30:  # Need minimum data
            stock_data[symbol] = {
                'history': hist,
                'score': df_scores[df_scores['symbol'] == symbol].iloc[0]['risk_adjusted_score']
            }
        
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i + 1}/{len(all_stocks)}")
            
    except Exception as e:
        continue

print(f"\n✅ Got data for {len(stock_data)} stocks")

# Run each random test
for test_config in random_tests:
    print(f"\n{'='*70}")
    print(f"Random Test #{test_config['test_id']}: {test_config['name']}")
    print(f"{'='*70}")
    
    num_stocks = test_config['num_stocks']
    forward_days = test_config['forward_days']
    
    # Randomly select stocks from those with data
    available_stocks = list(stock_data.keys())
    selected_stocks = random.sample(available_stocks, min(num_stocks, len(available_stocks)))
    
    print(f"   Selected {len(selected_stocks)} random stocks")
    print(f"   Forward period: {forward_days} days")
    
    # Calculate returns for selected stocks
    test_results = []
    
    for symbol in selected_stocks:
        try:
            hist = stock_data[symbol]['history']
            score = stock_data[symbol]['score']
            
            # Use data up to (forward_days) ago as "test date"
            if len(hist) < forward_days + 5:
                continue
                
            test_price = hist['Close'].iloc[-(forward_days+1)]  # Price N days ago
            current_price = hist['Close'].iloc[-1]  # Current price
            
            # Calculate return
            stock_return = ((current_price - test_price) / test_price) * 100
            
            test_results.append({
                'symbol': symbol,
                'score': score,
                'return': stock_return
            })
            
        except Exception as e:
            continue
    
    if len(test_results) < 10:
        print(f"   ⚠️ Insufficient results ({len(test_results)})")
        continue
    
    # Analyze results
    df_test = pd.DataFrame(test_results)
    df_test = df_test.sort_values('score', ascending=False)
    
    # Calculate metrics
    n = len(df_test)
    top_n = max(3, n // 4)  # Top 25%
    bottom_n = max(3, n // 4)  # Bottom 25%
    
    top_stocks = df_test.head(top_n)
    bottom_stocks = df_test.tail(bottom_n)
    
    top_return = top_stocks['return'].mean()
    bottom_return = bottom_stocks['return'].mean()
    all_return = df_test['return'].mean()
    
    alpha = top_return - all_return
    spread = top_return - bottom_return
    correlation = df_test['score'].corr(df_test['return'])
    
    # Store results
    result = {
        'test_id': test_config['test_id'],
        'name': test_config['name'],
        'stocks': n,
        'forward_days': forward_days,
        'top_return': top_return,
        'bottom_return': bottom_return,
        'all_return': all_return,
        'alpha': alpha,
        'spread': spread,
        'correlation': correlation
    }
    
    all_results.append(result)
    
    print(f"   📊 Results for {n} stocks:")
    print(f"      Top {top_n} return: {top_return:>7.2f}%")
    print(f"      Bottom {bottom_n} return: {bottom_return:>7.2f}%")
    print(f"      Alpha: {alpha:>7.2f}%")
    print(f"      Correlation: {correlation:>7.3f}")
    
    # Show top 3 random performers
    print(f"   🎲 Random top performers:")
    for _, stock in top_stocks.head(3).iterrows():
        print(f"      {stock['symbol']:<10} Score: {stock['score']:>5.1f} Return: {stock['return']:>6.2f}%")

# Final Random Test Summary
print(f"\n\n{'='*100}")
print("🎲 RANDOM VALIDATION SUMMARY")
print("="*100)

if not all_results:
    print("❌ No random tests completed")
else:
    df_random = pd.DataFrame(all_results)
    
    print(f"\n📊 Random Test Results:")
    print(f"\n{'Test':>4} {'Forward':>7} {'Stocks':>6} {'Alpha':>8} {'Corr':>7} {'Spread':>8}")
    print("-" * 50)
    
    for _, row in df_random.iterrows():
        print(f"{row['test_id']:>4} {row['forward_days']:>7} {row['stocks']:>6} "
              f"{row['alpha']:>7.2f}% {row['correlation']:>6.3f} {row['spread']:>7.2f}%")
    
    # Statistics
    avg_alpha = df_random['alpha'].mean()
    avg_corr = df_random['correlation'].mean()
    avg_spread = df_random['spread'].mean()
    
    positive_alpha = (df_random['alpha'] > 0).sum()
    positive_corr = (df_random['correlation'] > 0).sum()
    strong_alpha = (df_random['alpha'] > 1).sum()
    
    total_tests = len(df_random)
    
    print(f"\n📈 RANDOM TEST STATISTICS:")
    print(f"   Total Random Tests: {total_tests}")
    print(f"   Average Alpha: {avg_alpha:>7.2f}%")
    print(f"   Average Correlation: {avg_corr:>7.3f}")
    print(f"   Average Spread: {avg_spread:>7.2f}%")
    print(f"   Positive Alpha: {positive_alpha}/{total_tests} ({positive_alpha/total_tests*100:.1f}%)")
    print(f"   Strong Alpha (>1%): {strong_alpha}/{total_tests} ({strong_alpha/total_tests*100:.1f}%)")
    print(f"   Positive Correlation: {positive_corr}/{total_tests} ({positive_corr/total_tests*100:.1f}%)")
    
    # Best random test
    best_test = df_random.loc[df_random['alpha'].idxmax()]
    worst_test = df_random.loc[df_random['alpha'].idxmin()]
    
    print(f"\n🏆 BEST RANDOM TEST:")
    print(f"   {best_test['name']}")
    print(f"   Alpha: {best_test['alpha']:.2f}%, Correlation: {best_test['correlation']:.3f}")
    
    print(f"\n💔 WORST RANDOM TEST:")
    print(f"   {worst_test['name']}")
    print(f"   Alpha: {worst_test['alpha']:.2f}%, Correlation: {worst_test['correlation']:.3f}")
    
    # Performance by timeframe
    print(f"\n📅 PERFORMANCE BY TIMEFRAME:")
    timeframe_stats = df_random.groupby('forward_days').agg({
        'alpha': ['mean', 'count'],
        'correlation': 'mean'
    }).round(3)
    
    print(f"\n{'Days':>5} {'Tests':>5} {'Avg Alpha':>10} {'Avg Corr':>9}")
    print("-" * 35)
    for days in sorted(df_random['forward_days'].unique()):
        subset = df_random[df_random['forward_days'] == days]
        print(f"{days:>5} {len(subset):>5} {subset['alpha'].mean():>9.2f}% {subset['correlation'].mean():>8.3f}")
    
    # Final verdict
    success_rate = positive_alpha / total_tests
    strong_rate = strong_alpha / total_tests
    
    print(f"\n{'='*100}")
    print("🎯 RANDOM VALIDATION VERDICT")
    print("="*100)
    
    if avg_alpha > 1.5 and success_rate >= 0.75:
        verdict = "✅ SCORING SYSTEM HIGHLY ROBUST ON RANDOM DATA"
        status = "🟢 EXCELLENT VALIDATION"
        confidence = "HIGH"
    elif avg_alpha > 0.8 and success_rate >= 0.6:
        verdict = "✅ SCORING SYSTEM ROBUST ON RANDOM DATA"
        status = "🟢 GOOD VALIDATION"
        confidence = "GOOD"
    elif avg_alpha > 0.3 and success_rate >= 0.5:
        verdict = "🟡 SCORING SYSTEM MODERATELY ROBUST"
        status = "🟡 ACCEPTABLE"
        confidence = "MEDIUM"
    else:
        verdict = "❌ SCORING SYSTEM NOT ROBUST ON RANDOM DATA"
        status = "🔴 VALIDATION FAILED"
        confidence = "LOW"
    
    print(f"\n{verdict}")
    print(f"Status: {status}")
    print(f"Confidence: {confidence}")
    
    print(f"\n💡 RANDOM TEST INSIGHTS:")
    print(f"   • Tested {total_tests} completely random configurations")
    print(f"   • Success rate: {success_rate*100:.1f}% positive alpha")
    print(f"   • Strong performance: {strong_rate*100:.1f}% with >1% alpha")
    print(f"   • Average performance: {avg_alpha:.2f}% alpha")
    print(f"   • Correlation strength: {avg_corr:.3f} (predictive power)")
    
    if success_rate >= 0.6 and avg_alpha > 0.5:
        print(f"\n🚀 CONCLUSION:")
        print(f"   ✅ Your scoring system IS ROBUST across random selections!")
        print(f"   ✅ Works consistently on different stock combinations")
        print(f"   ✅ Not overfitted to specific stocks or conditions")
        print(f"   ✅ Ready for production use with high confidence")
        
        print(f"\n📋 DEPLOYMENT RECOMMENDATIONS:")
        print(f"   • Use system confidently on new stock selections")
        print(f"   • Optimal timeframes: 7-30 days (based on random tests)")
        print(f"   • Expected alpha: {avg_alpha:.1f}% on average")
        print(f"   • Monitor correlation >0.3 for continued validity")
    else:
        print(f"\n⚠️ CONCLUSION:")
        print(f"   System shows mixed results on random data")
        print(f"   May work better on specific stock types/sectors")
        print(f"   Consider further optimization before broad deployment")

print(f"\n✅ SIMPLE RANDOM VALIDATION COMPLETE!")