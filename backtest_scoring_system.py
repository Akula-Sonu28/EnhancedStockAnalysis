"""
SCORING SYSTEM BACKTEST
Tests the CorrectedScoringEngine on historical data
Compares high-score vs low-score stocks to validate the system
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from corrected_scoring_engine import CorrectedScoringEngine
import warnings
warnings.filterwarnings('ignore')

print("=" * 100)
print("📊 SCORING SYSTEM BACKTEST - Historical Validation")
print("=" * 100)

# Initialize scoring engine
scoring_engine = CorrectedScoringEngine()

# Test parameters
BACKTEST_MONTHS = 3  # Test last 3 months
FORWARD_DAYS = 30    # Measure returns over 30 days
TOP_N = 10           # Top 10 highest scores
BOTTOM_N = 10        # Bottom 10 lowest scores

# Stock universe - your current holdings + top 200
test_symbols = [
    # Current holdings (from previous analysis)
    'MAHABANK.NS', 'SBIN.NS', 'CUB.NS', 'INDIANB.NS', 'GICRE.NS', 
    'CANBK.NS', 'KARURVYSYA.NS', 'UNIONBANK.NS', 'J&KBANK.NS', 'PNB.NS',
    'IOB.NS', 'BANKBARODA.NS', 'ICICIBANK.NS', 'BANKINDIA.NS', 'CENTRALBK.NS',
    'YESBANK.NS', 'NMDC.NS', 'FEDERALBNK.NS', 'IDBI.NS', 'UCOBANK.NS',
    'RECLTD.NS', 'BAJAJHLDNG.NS', 'KOTAKBANK.NS', 'AXISBANK.NS', 'WIPRO.NS',
    'AUBANK.NS', 'HDFCBANK.NS', 'PFC.NS', 'UJJIVANSFB.NS', 'MUTHOOTFIN.NS',
    'LICHSGFIN.NS', 'MOTILALOFS.NS', 'DRREDDY.NS', 'NESTLEIND.NS', 'HINDUNILVR.NS'
]

print(f"\n📋 Backtest Configuration:")
print(f"   Period: Last {BACKTEST_MONTHS} months")
print(f"   Forward window: {FORWARD_DAYS} days")
print(f"   Stock universe: {len(test_symbols)} stocks")
print(f"   Test dates: Monthly snapshots")

# Generate test dates (monthly for last 3 months)
end_date = datetime.now()
test_dates = []
for i in range(BACKTEST_MONTHS):
    test_date = end_date - timedelta(days=30 * (i + 1))
    test_dates.append(test_date)

test_dates.reverse()  # Chronological order

print(f"   Test dates: {[d.strftime('%Y-%m-%d') for d in test_dates]}")

# Helper function for RSI
def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50

# Storage for results
backtest_results = []

print("\n" + "=" * 100)
print("📈 RUNNING BACKTEST")
print("=" * 100)

for test_idx, test_date in enumerate(test_dates):
    print(f"\n{'='*80}")
    print(f"Test Period #{test_idx + 1}: {test_date.strftime('%Y-%m-%d')}")
    print(f"{'='*80}")
    
    # Calculate forward date for returns measurement
    forward_date = test_date + timedelta(days=FORWARD_DAYS)
    
    if forward_date > datetime.now():
        print(f"⚠️ Forward date {forward_date.strftime('%Y-%m-%d')} is in future, skipping...")
        continue
    
    period_scores = []
    
    # Get data and calculate scores for each stock
    print(f"\n📊 Analyzing {len(test_symbols)} stocks...")
    
    for symbol in test_symbols:
        try:
            # Download historical data
            ticker = yf.Ticker(symbol)
            
            # Get data from 90 days before test_date to forward_date
            start_data = test_date - timedelta(days=90)
            hist_data = ticker.history(start=start_data, end=forward_date)
            
            if len(hist_data) < 30:  # Need minimum data
                continue
            
            # Get price at test_date and forward_date
            test_date_data = hist_data[hist_data.index <= test_date]
            forward_date_data = hist_data[hist_data.index <= forward_date]
            
            if test_date_data.empty or forward_date_data.empty:
                continue
            
            test_price = test_date_data['Close'].iloc[-1]
            forward_price = forward_date_data['Close'].iloc[-1]
            
            # Calculate actual return
            actual_return = ((forward_price - test_price) / test_price) * 100
            
            # Get stock data at test_date for scoring
            recent_data = test_date_data.tail(30)
            
            # Calculate indicators needed for scoring
            rsi = calculate_rsi(recent_data['Close'])
            price_change_5d = ((test_price - test_date_data['Close'].iloc[-6]) / test_date_data['Close'].iloc[-6] * 100) if len(test_date_data) > 5 else 0
            volume_ratio = recent_data['Volume'].iloc[-5:].mean() / recent_data['Volume'].iloc[-20:].mean() if len(recent_data) > 20 else 1
            
            # Get fundamental data
            info = ticker.info
            pe_ratio = info.get('trailingPE', 20)
            pb_ratio = info.get('priceToBook', 2)
            roe = info.get('returnOnEquity', 0.1) * 100 if info.get('returnOnEquity') else 10
            debt_to_equity = info.get('debtToEquity', 100) / 100 if info.get('debtToEquity') else 1
            
            # Get 52-week high/low
            year_high = test_date_data['High'].rolling(252).max().iloc[-1]
            year_low = test_date_data['Low'].rolling(252).min().iloc[-1]
            
            # Create stock_data dict for scoring
            stock_data = {
                'real_rsi': rsi,
                'enhanced_price_change_5d': price_change_5d,
                'enhanced_volume_ratio': volume_ratio,
                'momentum_flags': 0,
                'breakout_patterns': 0,
                'pe_ratio': pe_ratio,
                'pb_ratio': pb_ratio,
                'debt_to_equity': debt_to_equity,
                'roe': roe,
                'current_price': test_price,
                'year_high': year_high,
                'year_low': year_low
            }
            
            # Calculate score using CorrectedScoringEngine
            score_result = scoring_engine.calculate_corrected_overall_score(
                symbol.replace('.NS', ''), 
                stock_data
            )
            
            score = score_result['corrected_overall_score']
            
            period_scores.append({
                'symbol': symbol.replace('.NS', ''),
                'test_date': test_date,
                'test_price': test_price,
                'forward_price': forward_price,
                'actual_return': actual_return,
                'score': score,
                'rsi': rsi,
                'pe_ratio': pe_ratio,
                'pb_ratio': pb_ratio,
                'sector': score_result['sector']
            })
            
        except Exception as e:
            # Silently skip stocks with errors
            continue
    
    if len(period_scores) == 0:
        print("⚠️ No valid data for this period")
        continue
    
    # Convert to dataframe
    df_period = pd.DataFrame(period_scores)
    
    # Sort by score
    df_period = df_period.sort_values('score', ascending=False)
    
    # Get top and bottom stocks
    top_stocks = df_period.head(TOP_N)
    bottom_stocks = df_period.tail(BOTTOM_N)
    
    # Calculate returns
    top_return = top_stocks['actual_return'].mean()
    bottom_return = bottom_stocks['actual_return'].mean()
    all_return = df_period['actual_return'].mean()
    
    print(f"\n📊 Results for {test_date.strftime('%Y-%m-%d')}:")
    print(f"   Total stocks analyzed: {len(df_period)}")
    print(f"   Top {TOP_N} avg return: {top_return:>7.2f}%")
    print(f"   Bottom {TOP_N} avg return: {bottom_return:>7.2f}%")
    print(f"   All stocks avg return: {all_return:>7.2f}%")
    print(f"   Alpha (Top vs All): {top_return - all_return:>7.2f}%")
    print(f"   Spread (Top vs Bottom): {top_return - bottom_return:>7.2f}%")
    
    # Store results
    backtest_results.append({
        'test_date': test_date,
        'stocks_analyzed': len(df_period),
        'top_return': top_return,
        'bottom_return': bottom_return,
        'all_return': all_return,
        'alpha': top_return - all_return,
        'spread': top_return - bottom_return,
        'top_stocks': top_stocks,
        'bottom_stocks': bottom_stocks,
        'all_scores': df_period
    })

print("\n\n" + "=" * 100)
print("📊 BACKTEST SUMMARY")
print("=" * 100)

if len(backtest_results) == 0:
    print("\n❌ No valid backtest results. Need more historical data.")
else:
    # Aggregate results
    avg_top_return = np.mean([r['top_return'] for r in backtest_results])
    avg_bottom_return = np.mean([r['bottom_return'] for r in backtest_results])
    avg_all_return = np.mean([r['all_return'] for r in backtest_results])
    avg_alpha = np.mean([r['alpha'] for r in backtest_results])
    avg_spread = np.mean([r['spread'] for r in backtest_results])
    
    # Win rate (how often top > bottom)
    wins = sum(1 for r in backtest_results if r['top_return'] > r['bottom_return'])
    total_tests = len(backtest_results)
    win_rate = (wins / total_tests) * 100
    
    print(f"\n📈 Overall Performance ({total_tests} test periods):")
    print(f"   Average Top-{TOP_N} Return: {avg_top_return:>7.2f}%")
    print(f"   Average Bottom-{BOTTOM_N} Return: {avg_bottom_return:>7.2f}%")
    print(f"   Average All Stocks Return: {avg_all_return:>7.2f}%")
    print(f"   Average Alpha (Top vs All): {avg_alpha:>7.2f}%")
    print(f"   Average Spread (Top vs Bottom): {avg_spread:>7.2f}%")
    print(f"   Win Rate (Top beats Bottom): {win_rate:.1f}% ({wins}/{total_tests})")
    
    # Verdict
    print(f"\n" + "=" * 100)
    print("🎯 VERDICT")
    print("=" * 100)
    
    if avg_alpha > 2 and win_rate > 60:
        verdict = "✅ SCORING SYSTEM WORKS!"
        detail = "High-score stocks consistently outperform. System is validated."
        status = "PRODUCTION READY"
    elif avg_alpha > 0 and win_rate > 50:
        verdict = "🟡 SCORING SYSTEM PARTIALLY WORKS"
        detail = "High-score stocks perform slightly better. Needs optimization."
        status = "NEEDS TUNING"
    elif avg_alpha < 0 or win_rate < 50:
        verdict = "❌ SCORING SYSTEM DOESN'T WORK"
        detail = "High-score stocks underperform or no better than random. Major issues."
        status = "NEEDS REDESIGN"
    else:
        verdict = "🤷 INCONCLUSIVE"
        detail = "Results are mixed. Need more data or longer test period."
        status = "NEED MORE DATA"
    
    print(f"\n{verdict}")
    print(f"Detail: {detail}")
    print(f"Status: {status}")
    
    # Detailed breakdown by period
    print(f"\n" + "=" * 100)
    print("📅 PERIOD-BY-PERIOD BREAKDOWN")
    print("=" * 100)
    
    print(f"\n{'Date':<12} {'Stocks':>7} {'Top Return':>12} {'Bottom Return':>15} {'Alpha':>10} {'Spread':>10}")
    print("-" * 80)
    
    for result in backtest_results:
        print(f"{result['test_date'].strftime('%Y-%m-%d'):<12} "
              f"{result['stocks_analyzed']:>7} "
              f"{result['top_return']:>11.2f}% "
              f"{result['bottom_return']:>14.2f}% "
              f"{result['alpha']:>9.2f}% "
              f"{result['spread']:>9.2f}%")
    
    # Best and worst performing stocks
    if backtest_results:
        print(f"\n" + "=" * 100)
        print("🏆 BEST SCORING STOCKS (from latest period)")
        print("=" * 100)
        
        latest = backtest_results[-1]
        print(f"\nTop {TOP_N} stocks on {latest['test_date'].strftime('%Y-%m-%d')}:")
        print(f"\n{'Symbol':<12} {'Score':>7} {'Return':>10} {'RSI':>7} {'P/E':>7} {'Sector':<12}")
        print("-" * 70)
        
        for _, stock in latest['top_stocks'].head(10).iterrows():
            print(f"{stock['symbol']:<12} {stock['score']:>6.1f} "
                  f"{stock['actual_return']:>9.2f}% "
                  f"{stock['rsi']:>6.1f} "
                  f"{stock['pe_ratio']:>6.1f} "
                  f"{stock['sector']:<12}")
        
        print(f"\n" + "=" * 100)
        print("💔 WORST SCORING STOCKS (from latest period)")
        print("=" * 100)
        
        print(f"\nBottom {BOTTOM_N} stocks on {latest['test_date'].strftime('%Y-%m-%d')}:")
        print(f"\n{'Symbol':<12} {'Score':>7} {'Return':>10} {'RSI':>7} {'P/E':>7} {'Sector':<12}")
        print("-" * 70)
        
        for _, stock in latest['bottom_stocks'].head(10).iterrows():
            print(f"{stock['symbol']:<12} {stock['score']:>6.1f} "
                  f"{stock['actual_return']:>9.2f}% "
                  f"{stock['rsi']:>6.1f} "
                  f"{stock['pe_ratio']:>6.1f} "
                  f"{stock['sector']:<12}")

print("\n" + "=" * 100)
print("📝 RECOMMENDATIONS")
print("=" * 100)

if len(backtest_results) == 0:
    print("""
⚠️ Backtest incomplete - need more historical data or different test period.

Next steps:
1. Try longer backtest period (6-12 months)
2. Use different stock universe
3. Check data availability
""")
elif 'verdict' in locals():
    if "WORKS" in verdict and avg_alpha > 2:
        print(f"""
✅ Your scoring system is validated!
   - Top-scoring stocks beat the market by {avg_alpha:.2f}%
   - Win rate: {win_rate:.1f}%
   
Recommendations:
1. Use scores >75 for buy candidates
2. Avoid scores <40
3. Retest quarterly to ensure continued validity
4. Consider increasing position sizes for highest scorers
""")
    elif "PARTIALLY" in verdict:
        print(f"""
🟡 Scoring system needs optimization
   - Small alpha: {avg_alpha:.2f}%
   - Moderate win rate: {win_rate:.1f}%

Recommendations:
1. Tune component weights (currently 25%, 20%, 20%, 15%)
2. Test different RSI thresholds
3. Add momentum/volume filters
4. Consider market regime detection
5. Optimize sector multipliers
""")
    else:
        print(f"""
❌ Scoring system has fundamental issues
   - Negative or minimal alpha: {avg_alpha:.2f}%
   - Low win rate: {win_rate:.1f}%

Recommendations:
1. REDESIGN scoring logic
2. Test if INVERSE logic works (high score = bad?)
3. Check for bugs in scoring calculations
4. Consider momentum vs value approach
5. Benchmark against simple strategies (PE ratio, RSI only)
""")
