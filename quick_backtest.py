"""
QUICK SCORING BACKTEST
Uses existing Excel report data to validate scoring quickly
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

print("=" * 100)
print("⚡ QUICK SCORING SYSTEM BACKTEST")
print("=" * 100)

# Load the latest Excel report
excel_file = 'reports/Enhanced_Stock_Report_20251006_211751.xlsx'

try:
    df_complete = pd.read_excel(excel_file, sheet_name='Complete Data')
    print(f"\n✅ Loaded {excel_file}")
    print(f"   Complete Data: {len(df_complete)} stocks")
    print(f"   Score range: {df_complete['risk_adjusted_score'].min():.1f} - {df_complete['risk_adjusted_score'].max():.1f}")
except:
    print(f"\n❌ Could not load {excel_file}")
    print("   Using current holdings only for backtest")
    excel_file = None
    df_complete = None

# Test configuration
FORWARD_DAYS_LIST = [7, 14, 30]  # Test multiple time horizons
TOP_N = 15
BOTTOM_N = 15

print(f"\n📋 Backtest Configuration:")
print(f"   Forward test windows: {FORWARD_DAYS_LIST} days")
print(f"   Comparing: Top {TOP_N} vs Bottom {BOTTOM_N} scored stocks")

if excel_file and df_complete is not None and not df_complete.empty:
    # Use complete data for backtest
    stocks_to_test = df_complete['symbol'].tolist()[:50]  # Limit to 50 for speed
else:
    # Fallback to holdings
    stocks_to_test = ['MAHABANK', 'SBIN', 'CUB', 'INDIANB', 'GICRE', 
                      'CANBK', 'KARURVYSYA', 'UNIONBANK', 'J&KBANK', 'PNB',
                      'KOTAKBANK', 'AXISBANK', 'HDFCBANK', 'ICICIBANK']

print(f"   Stocks to test: {len(stocks_to_test)}")

print("\n" + "=" * 100)
print("📊 DOWNLOADING CURRENT & HISTORICAL PRICES")
print("=" * 100)

# Get report date (use today as proxy)
report_date = datetime.now()

# Download price data
price_data = {}
scores_data = {}

print(f"\nDownloading price data...")

for i, symbol in enumerate(stocks_to_test):
    try:
        # Add .NS suffix for Yahoo Finance
        ticker_symbol = symbol if '.NS' in symbol else f"{symbol}.NS"
        ticker = yf.Ticker(ticker_symbol)
        
        # Get 60 days of history (30 days back + 30 days forward)
        hist = ticker.history(period='60d')
        
        if len(hist) >= 10:  # Need minimum data
            price_data[symbol] = hist
            
            # Get score from Excel if available
            if excel_file and df_complete is not None:
                score_row = df_complete[df_complete['symbol'] == symbol]
                if not score_row.empty:
                    scores_data[symbol] = score_row.iloc[0]['risk_adjusted_score']
                else:
                    scores_data[symbol] = 50  # Default neutral score
            else:
                scores_data[symbol] = 50
        
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i + 1}/{len(stocks_to_test)} stocks")
            
    except Exception as e:
        continue

print(f"\n✅ Downloaded price data for {len(price_data)} stocks")

if len(price_data) < 10:
    print("\n❌ Insufficient data for backtest. Need at least 10 stocks.")
    exit()

print("\n" + "=" * 100)
print("📈 CALCULATING FORWARD RETURNS")
print("=" * 100)

results_by_period = {}

for forward_days in FORWARD_DAYS_LIST:
    print(f"\n{'='*80}")
    print(f"Testing {forward_days}-Day Forward Returns")
    print(f"{'='*80}")
    
    backtest_data = []
    
    for symbol, hist in price_data.items():
        try:
            # Get price from 'forward_days' ago
            if len(hist) < forward_days + 5:
                continue
            
            start_price = hist['Close'].iloc[-(forward_days + 1)]
            current_price = hist['Close'].iloc[-1]
            
            # Calculate return
            forward_return = ((current_price - start_price) / start_price) * 100
            
            backtest_data.append({
                'symbol': symbol,
                'score': scores_data.get(symbol, 50),
                'start_price': start_price,
                'current_price': current_price,
                'forward_return': forward_return
            })
            
        except Exception as e:
            continue
    
    if len(backtest_data) < 10:
        print(f"   ⚠️ Insufficient data ({len(backtest_data)} stocks)")
        continue
    
    # Convert to DataFrame
    df_backtest = pd.DataFrame(backtest_data)
    
    # Sort by score
    df_backtest = df_backtest.sort_values('score', ascending=False)
    
    # Get top and bottom
    top_stocks = df_backtest.head(TOP_N)
    bottom_stocks = df_backtest.tail(BOTTOM_N)
    
    # Calculate metrics
    top_return = top_stocks['forward_return'].mean()
    bottom_return = bottom_stocks['forward_return'].mean()
    all_return = df_backtest['forward_return'].mean()
    median_return = df_backtest['forward_return'].median()
    
    # Alpha and spread
    alpha = top_return - all_return
    spread = top_return - bottom_return
    
    # Win rate
    top_wins = (top_stocks['forward_return'] > median_return).sum()
    top_total = len(top_stocks)
    win_rate = (top_wins / top_total) * 100
    
    # Store results
    results_by_period[forward_days] = {
        'stocks_analyzed': len(df_backtest),
        'top_return': top_return,
        'bottom_return': bottom_return,
        'all_return': all_return,
        'median_return': median_return,
        'alpha': alpha,
        'spread': spread,
        'win_rate': win_rate,
        'top_stocks': top_stocks,
        'bottom_stocks': bottom_stocks
    }
    
    # Print results
    print(f"\n   Stocks analyzed: {len(df_backtest)}")
    print(f"   Top-{TOP_N} average return: {top_return:>7.2f}%")
    print(f"   Bottom-{BOTTOM_N} average return: {bottom_return:>7.2f}%")
    print(f"   All stocks average return: {all_return:>7.2f}%")
    print(f"   Median return: {median_return:>7.2f}%")
    print(f"   Alpha (Top vs All): {alpha:>7.2f}%")
    print(f"   Spread (Top vs Bottom): {spread:>7.2f}%")
    print(f"   Win Rate (Top beats median): {win_rate:.1f}%")

print("\n\n" + "=" * 100)
print("📊 OVERALL BACKTEST SUMMARY")
print("=" * 100)

# Average across all periods
avg_alpha = np.mean([r['alpha'] for r in results_by_period.values()])
avg_spread = np.mean([r['spread'] for r in results_by_period.values()])
avg_win_rate = np.mean([r['win_rate'] for r in results_by_period.values()])

print(f"\n📈 Averaged across {len(results_by_period)} time periods:")
print(f"   Average Alpha: {avg_alpha:>7.2f}%")
print(f"   Average Spread: {avg_spread:>7.2f}%")
print(f"   Average Win Rate: {avg_win_rate:.1f}%")

print(f"\n" + "=" * 100)
print("🎯 VERDICT")
print("=" * 100)

if avg_alpha > 2 and avg_win_rate > 60:
    verdict = "✅ SCORING SYSTEM WORKS!"
    detail = f"High-score stocks outperform by {avg_alpha:.2f}% with {avg_win_rate:.1f}% win rate"
    status = "🟢 PRODUCTION READY"
    recommendation = "Use scores confidently. High scores (>75) = Strong buy candidates"
elif avg_alpha > 1 and avg_win_rate > 55:
    verdict = "🟡 SCORING SYSTEM PARTIALLY WORKS"
    detail = f"Modest outperformance: {avg_alpha:.2f}% alpha, {avg_win_rate:.1f}% win rate"
    status = "🟡 NEEDS OPTIMIZATION"
    recommendation = "System shows promise but needs tuning. Combine with other factors."
elif avg_alpha < 0:
    verdict = "❌ SCORING SYSTEM INVERTED!"
    detail = f"High scores UNDERPERFORM by {avg_alpha:.2f}%. System logic is backwards!"
    status = "🔴 CRITICAL BUG"
    recommendation = "URGENT: Test inverse scoring (low score = buy). May be contrarian logic error."
else:
    verdict = "🤷 SCORING SYSTEM NEUTRAL"
    detail = f"No significant edge: {avg_alpha:.2f}% alpha, {avg_win_rate:.1f}% win rate"
    status = "🟡 NO PREDICTIVE POWER"
    recommendation = "System doesn't beat random selection. Consider redesign or different approach."

print(f"\n{verdict}")
print(f"Detail: {detail}")
print(f"Status: {status}")
print(f"\nRecommendation:")
print(f"   {recommendation}")

# Show best and worst performers
if 30 in results_by_period:
    print(f"\n" + "=" * 100)
    print("🏆 TOP-SCORING STOCKS (30-day forward returns)")
    print("=" * 100)
    
    result_30d = results_by_period[30]
    print(f"\n{'Symbol':<12} {'Score':>7} {'30d Return':>12} {'Performance'}")
    print("-" * 60)
    
    for _, stock in result_30d['top_stocks'].head(10).iterrows():
        perf = "✅ Beat" if stock['forward_return'] > result_30d['median_return'] else "❌ Lost"
        print(f"{stock['symbol']:<12} {stock['score']:>6.1f} {stock['forward_return']:>11.2f}% {perf}")
    
    print(f"\n" + "=" * 100)
    print("💔 BOTTOM-SCORING STOCKS (30-day forward returns)")
    print("=" * 100)
    
    print(f"\n{'Symbol':<12} {'Score':>7} {'30d Return':>12} {'Performance'}")
    print("-" * 60)
    
    for _, stock in result_30d['bottom_stocks'].head(10).iterrows():
        perf = "✅ Beat" if stock['forward_return'] > result_30d['median_return'] else "❌ Lost"
        print(f"{stock['symbol']:<12} {stock['score']:>6.1f} {stock['forward_return']:>11.2f}% {perf}")

print(f"\n" + "=" * 100)
print("💡 NEXT STEPS")
print("=" * 100)

if "WORKS" in verdict:
    print("""
✅ System validated! Next steps:
1. Continue using current scoring system
2. Set buy threshold at score >75
3. Avoid stocks with score <50
4. Retest quarterly to maintain validity
5. Consider position sizing based on score (higher score = larger position)
""")
elif "PARTIALLY" in verdict:
    print("""
🟡 System needs improvement:
1. Optimize component weights (try different combinations)
2. Add momentum or volume filters
3. Test different time horizons (weekly vs monthly)
4. Consider market regime detection (bull/bear/sideways)
5. Combine scoring with other signals
""")
elif "INVERTED" in verdict:
    print("""
🔴 CRITICAL: System logic is backwards!
1. TEST IMMEDIATELY: Invert scores (100 - score) and re-run
2. Check if contrarian logic should be opposite
3. Review CorrectedScoringEngine formula
4. May need to flip technical/momentum interpretation
5. Consider that "value" approach may not work in current market
""")
else:
    print("""
🤷 System has no predictive power:
1. Consider complete redesign
2. Test simpler strategies (PE ratio only, RSI only)
3. Add machine learning features
4. Focus on sector-specific models
5. May need fundamental different approach (momentum vs value)
""")

print("\n" + "=" * 100)
