"""
PERIOD-BASED BACKTEST USING EXISTING DATA
Tests different time horizons using available stock data
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

print("=" * 100)
print("📊 PERIOD-BASED SCORING BACKTEST")
print("=" * 100)

# Load existing Excel report for scores
try:
    df_scores = pd.read_excel('reports/Enhanced_Stock_Report_20251006_211751.xlsx', sheet_name='Complete Data')
    print(f"✅ Loaded scoring data: {len(df_scores)} stocks")
except:
    print("❌ Could not load Excel report, creating extended sample data...")
    # Create extended sample data across sectors
    sample_stocks = [
        # Banking & Financial
        'MAHABANK', 'SBIN', 'CUB', 'INDIANB', 'GICRE', 'CANBK', 'KARURVYSYA', 
        'UNIONBANK', 'PNB', 'BANKBARODA', 'ICICIBANK', 'BANKINDIA', 'CENTRALBK',
        'FEDERALBNK', 'AXISBANK', 'AUBANK', 'HDFCBANK', 'KOTAKBANK', 'YESBANK', 'BAJFINANCE',
        
        # IT & Technology
        'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTI', 'MINDTREE', 'COFORGE',
        
        # Consumer Goods
        'NESTLEIND', 'HINDUNILVR', 'ITC', 'BRITANNIA', 'DABUR', 'MARICO', 'GODREJCP',
        
        # Auto
        'TATAMOTORS', 'MARUTI', 'M&M', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT',
        
        # Pharma
        'DRREDDY', 'SUNPHARMA', 'CIPLA', 'LUPIN', 'DIVISLAB', 'BIOCON',
        
        # Energy
        'RELIANCE', 'ONGC', 'IOC', 'BPCL', 'NTPC', 'POWERGRID', 'COALINDIA',
        
        # Metals
        'VEDL', 'HINDALCO', 'TATASTEEL', 'JSWSTEEL', 'NMDC', 'HINDZINC',
        
        # Cement
        'ULTRACEMCO', 'ACC', 'AMBUJACEMENT', 'SHREECEM',
        
        # Infrastructure
        'LARSENTOUBRO', 'SIEMENS', 'ABB', 'BHEL',
        
        # Telecom
        'BHARTIARTL', 'INDUSTOWER',
        
        # Others
        'DMART', 'UPL', 'PIDILITIND', 'DLF', 'INDIGO'
    ]
    
    df_scores = pd.DataFrame({
        'symbol': sample_stocks,
        'risk_adjusted_score': np.random.uniform(35, 95, len(sample_stocks))  # Wider range
    })

# Different test periods to evaluate
TEST_PERIODS = [
    {'days': 5, 'name': '5-Day Returns'},
    {'days': 10, 'name': '10-Day Returns'},
    {'days': 15, 'name': '15-Day Returns'}, 
    {'days': 20, 'name': '20-Day Returns'},
    {'days': 30, 'name': '30-Day Returns'},
    {'days': 45, 'name': '45-Day Returns'},
    {'days': 60, 'name': '60-Day Returns'}
]

print(f"\n📋 Testing {len(TEST_PERIODS)} different return periods")
print(f"   Stock universe: {len(df_scores)} stocks")

# Get current price data for all stocks
print(f"\n📊 Downloading current price data...")
price_data = {}
current_scores = {}

valid_stocks = 0
for i, row in df_scores.iterrows():
    symbol = row['symbol']
    score = row['risk_adjusted_score']
    
    try:
        # Add .NS suffix for Indian stocks
        ticker_symbol = symbol if '.NS' in symbol else f"{symbol}.NS"
        ticker = yf.Ticker(ticker_symbol)
        
        # Get last 90 days of data
        hist = ticker.history(period='90d')
        
        if len(hist) >= 30:  # Need minimum data
            price_data[symbol] = hist
            current_scores[symbol] = score
            valid_stocks += 1
            
        if (i + 1) % 5 == 0:
            print(f"   Progress: {i + 1}/{len(df_scores)}")
            
    except Exception as e:
        continue

print(f"\n✅ Got data for {valid_stocks} stocks")

if valid_stocks < 10:
    print("❌ Insufficient data for meaningful analysis")
    exit()

# Test each time period
period_results = []

print(f"\n" + "=" * 100)
print("📈 TESTING DIFFERENT TIME PERIODS")
print("=" * 100)

for period_config in TEST_PERIODS:
    days = period_config['days']
    name = period_config['name']
    
    print(f"\n{'='*60}")
    print(f"Testing {name} ({days} days)")
    print(f"{'='*60}")
    
    # Calculate returns for this period
    stock_returns = []
    
    for symbol, hist_data in price_data.items():
        if len(hist_data) < days + 5:  # Need enough data
            continue
            
        try:
            # Get price from 'days' ago and current price
            start_price = hist_data['Close'].iloc[-(days+1)]
            end_price = hist_data['Close'].iloc[-1]
            
            # Calculate return
            period_return = ((end_price - start_price) / start_price) * 100
            
            stock_returns.append({
                'symbol': symbol,
                'score': current_scores[symbol],
                'return': period_return,
                'start_price': start_price,
                'end_price': end_price
            })
            
        except Exception as e:
            continue
    
    if len(stock_returns) < 10:
        print(f"   ⚠️ Only {len(stock_returns)} stocks with data")
        continue
    
    # Convert to DataFrame and analyze
    df_returns = pd.DataFrame(stock_returns)
    df_returns = df_returns.sort_values('score', ascending=False)
    
    # Split into quintiles by score
    n_stocks = len(df_returns)
    quintile_size = n_stocks // 5
    
    quintiles = {
        'Q1 (Highest Score)': df_returns.head(quintile_size),
        'Q2': df_returns.iloc[quintile_size:2*quintile_size],
        'Q3': df_returns.iloc[2*quintile_size:3*quintile_size], 
        'Q4': df_returns.iloc[3*quintile_size:4*quintile_size],
        'Q5 (Lowest Score)': df_returns.tail(quintile_size)
    }
    
    # Calculate statistics
    print(f"\n   📊 Analysis of {n_stocks} stocks:")
    print(f"\n   {'Quintile':<20} {'Count':>5} {'Avg Return':>12} {'Median':>10} {'Top Stock'}")
    print(f"   {'-'*70}")
    
    quintile_stats = []
    
    for q_name, q_data in quintiles.items():
        if len(q_data) == 0:
            continue
            
        avg_return = q_data['return'].mean()
        median_return = q_data['return'].median()
        best_stock = q_data.loc[q_data['return'].idxmax(), 'symbol'] if len(q_data) > 0 else 'N/A'
        best_return = q_data['return'].max() if len(q_data) > 0 else 0
        
        print(f"   {q_name:<20} {len(q_data):>5} {avg_return:>11.2f}% {median_return:>9.2f}% {best_stock} ({best_return:.1f}%)")
        
        quintile_stats.append({
            'period': name,
            'days': days,
            'quintile': q_name,
            'count': len(q_data),
            'avg_return': avg_return,
            'median_return': median_return
        })
    
    # Calculate key metrics
    top_quintile_return = quintiles['Q1 (Highest Score)']['return'].mean()
    bottom_quintile_return = quintiles['Q5 (Lowest Score)']['return'].mean()
    all_stocks_return = df_returns['return'].mean()
    
    alpha = top_quintile_return - all_stocks_return
    spread = top_quintile_return - bottom_quintile_return
    
    # Correlation analysis
    correlation = df_returns['score'].corr(df_returns['return'])
    
    period_result = {
        'period': name,
        'days': days,
        'stocks': n_stocks,
        'top_quintile_return': top_quintile_return,
        'bottom_quintile_return': bottom_quintile_return,
        'all_stocks_return': all_stocks_return,
        'alpha': alpha,
        'spread': spread,
        'correlation': correlation
    }
    
    period_results.append(period_result)
    
    print(f"\n   📈 Key Metrics:")
    print(f"      Top Quintile Return: {top_quintile_return:>7.2f}%")
    print(f"      Bottom Quintile Return: {bottom_quintile_return:>7.2f}%")
    print(f"      Alpha (Top vs All): {alpha:>7.2f}%")
    print(f"      Spread (Top vs Bottom): {spread:>7.2f}%")
    print(f"      Score-Return Correlation: {correlation:>7.3f}")

# Summary analysis
print(f"\n\n" + "=" * 100)
print("📊 PERIOD-BASED BACKTEST SUMMARY")
print("=" * 100)

if not period_results:
    print("\n❌ No valid results across test periods")
else:
    df_summary = pd.DataFrame(period_results)
    
    print(f"\n📈 Performance by Time Period:")
    print(f"\n{'Period':<15} {'Days':>5} {'Stocks':>6} {'Alpha':>8} {'Spread':>8} {'Correlation':>11}")
    print("-" * 65)
    
    for _, row in df_summary.iterrows():
        print(f"{row['period']:<15} {row['days']:>5} {row['stocks']:>6} "
              f"{row['alpha']:>7.2f}% {row['spread']:>7.2f}% {row['correlation']:>10.3f}")
    
    # Best performing periods
    best_alpha = df_summary.loc[df_summary['alpha'].idxmax()]
    best_correlation = df_summary.loc[df_summary['correlation'].idxmax()] 
    best_spread = df_summary.loc[df_summary['spread'].idxmax()]
    
    print(f"\n🏆 BEST PERFORMING PERIODS:")
    print(f"   Highest Alpha: {best_alpha['period']} ({best_alpha['alpha']:.2f}%)")
    print(f"   Best Correlation: {best_correlation['period']} ({best_correlation['correlation']:.3f})")
    print(f"   Largest Spread: {best_spread['period']} ({best_spread['spread']:.2f}%)")
    
    # Overall statistics
    avg_alpha = df_summary['alpha'].mean()
    avg_correlation = df_summary['correlation'].mean()
    avg_spread = df_summary['spread'].mean()
    
    positive_alpha_periods = (df_summary['alpha'] > 0).sum()
    positive_corr_periods = (df_summary['correlation'] > 0).sum()
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   Average Alpha: {avg_alpha:7.2f}%")
    print(f"   Average Correlation: {avg_correlation:7.3f}")
    print(f"   Average Spread: {avg_spread:7.2f}%")
    print(f"   Periods with Positive Alpha: {positive_alpha_periods}/{len(df_summary)}")
    print(f"   Periods with Positive Correlation: {positive_corr_periods}/{len(df_summary)}")
    
    # Verdict
    print(f"\n" + "=" * 100)
    print("🎯 PERIOD-BASED VERDICT")
    print("=" * 100)
    
    if avg_alpha > 1 and avg_correlation > 0.1 and positive_alpha_periods >= len(df_summary) * 0.6:
        verdict = "✅ SCORING SYSTEM WORKS ACROSS TIME PERIODS"
        status = "🟢 VALIDATED"
        recommendation = "System shows consistent alpha generation across different time horizons"
    elif avg_alpha > 0 and positive_alpha_periods >= len(df_summary) * 0.5:
        verdict = "🟡 SCORING SYSTEM PARTIALLY EFFECTIVE"
        status = "🟡 NEEDS OPTIMIZATION"  
        recommendation = "System shows some predictive power but needs tuning for consistency"
    else:
        verdict = "❌ SCORING SYSTEM INCONSISTENT"
        status = "🔴 NEEDS MAJOR REVISION"
        recommendation = "System lacks consistent predictive power across time periods"
    
    print(f"\n{verdict}")
    print(f"Status: {status}")
    print(f"\n💡 Recommendation: {recommendation}")
    
    # Optimal holding period analysis
    print(f"\n📅 OPTIMAL HOLDING PERIOD ANALYSIS:")
    
    # Find the period with best risk-adjusted returns
    df_summary['risk_adjusted'] = df_summary['alpha'] / (df_summary['spread'].abs() + 1)  # Simple risk adjustment
    best_period = df_summary.loc[df_summary['risk_adjusted'].idxmax()]
    
    print(f"   Recommended Holding Period: {best_period['period']}")
    print(f"   Rationale: Best balance of alpha ({best_period['alpha']:.2f}%) and consistency")
    print(f"   Correlation Strength: {best_period['correlation']:.3f}")
    
    if best_period['days'] <= 15:
        strategy = "SHORT-TERM TRADING"
        approach = "Active rebalancing, frequent position updates"
    elif best_period['days'] <= 30:
        strategy = "MEDIUM-TERM SWING"  
        approach = "Monthly rebalancing, momentum capture"
    else:
        strategy = "LONG-TERM POSITION"
        approach = "Quarterly rebalancing, fundamental focus"
        
    print(f"   Suggested Strategy: {strategy}")
    print(f"   Trading Approach: {approach}")

print(f"\n✅ PERIOD-BASED BACKTEST COMPLETE!")