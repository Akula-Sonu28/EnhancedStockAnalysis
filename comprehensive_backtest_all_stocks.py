"""
COMPREHENSIVE BACKTEST - ALL STOCKS
Tests improved scoring on complete stock universe (200+ stocks)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from improved_scoring_engine import ImprovedScoringEngine
import warnings
warnings.filterwarnings('ignore')

print("=" * 100)
print("🌐 COMPREHENSIVE BACKTEST - ALL STOCKS")
print("=" * 100)

# Load stock list
print("\n📋 Loading stock universe...")

# Get all Nifty 500 or use predefined list
stock_list_file = 'stock_list_template500.csv'

try:
    df_stocks = pd.read_csv(stock_list_file)
    all_symbols = df_stocks['Symbol'].tolist()
    print(f"✅ Loaded {len(all_symbols)} stocks from {stock_list_file}")
except:
    print(f"⚠️  Could not load {stock_list_file}, using top 200 stocks")
    # Fallback: Top 200 liquid stocks
    all_symbols = [
        # Banking (30)
        'HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK',
        'FEDERALBNK', 'BANDHANBNK', 'IDFCFIRSTB', 'PNB', 'CANBK', 'BANKBARODA',
        'UNIONBANK', 'INDIANB', 'BANKINDIA', 'MAHABANK', 'CUB', 'KARURVYSYA',
        'J&KBANK', 'CENTRALBK', 'IDBI', 'YESBANK', 'UCOBANK', 'IOB', 'AUBANK',
        'RBLBANK', 'SOUTHBANK', 'PNBHOUSING', 'CSBBANK', 'DCBBANK',
        
        # Financial Services (20)
        'BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN', 'MUTHOOTFIN', 'UJJIVANSFB',
        'LICHSGFIN', 'RECLTD', 'PFC', 'ICICIGI', 'GICRE', 'BAJAJHLDNG',
        'SBILIFE', 'HDFCLIFE', 'ICICIPRULI', 'SBICARD', 'M&MFIN',
        'SHRIRAMFIN', 'L&TFH', 'CDSL', 'CAMS',
        
        # IT (15)
        'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTTS', 'LTIM',
        'COFORGE', 'PERSISTENT', 'MPHASIS', 'OFSS', 'MINDTREE', 'FSL',
        'TATAELXSI', 'SONATSOFTW',
        
        # Auto (15)
        'MARUTI', 'M&M', 'TATAMOTORS', 'BAJAJ-AUTO', 'EICHERMOT', 'HEROMOTOCO',
        'TVSMOTOR', 'ASHOKLEY', 'ESCORTS', 'APOLLOTYRE', 'MRF', 'BALKRISIND',
        'EXIDEIND', 'AMARA RAJA', 'BOSCHLTD',
        
        # Pharma (15)
        'SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LUPIN', 'AUROPHARMA',
        'BIOCON', 'TORNTPHARM', 'ALKEM', 'ABBOTINDIA', 'GLENMARK', 'IPCALAB',
        'LAURUSLABS', 'NATCOPHARM', 'GRANULES',
        
        # FMCG (15)
        'HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'DABUR', 'GODREJCP',
        'MARICO', 'COLPAL', 'TATACONSUM', 'UBL', 'PGHH', 'MCDOWELL-N',
        'EMAMILTD', 'VBL', 'RADICO',
        
        # Energy & Power (15)
        'RELIANCE', 'ONGC', 'NTPC', 'POWERGRID', 'COALINDIA', 'BPCL', 'IOC',
        'ADANIGREEN', 'ADANIPOWER', 'TATAPOWER', 'TORNTPOWER', 'NHPC', 'SJVN',
        'GAIL', 'PETRONET',
        
        # Metals (15)
        'TATASTEEL', 'HINDALCO', 'JSWSTEEL', 'VEDL', 'SAIL', 'NMDC', 'COALINDIA',
        'JINDALSTEL', 'HINDZINC', 'NATIONALUM', 'WELCORP', 'RATNAMANI',
        'WELSPUNIND', 'MOIL', 'GMRINFRA',
        
        # Capital Goods (20)
        'LARSENTOUBRO', 'ABB', 'SIEMENS', 'BHARTIARTL', 'BEL', 'BHEL', 'HAL',
        'CUMMINSIND', 'THERMAX', 'CROMPTON', 'VOLTAS', 'KPITTECH', 'GRINDWELL',
        'SCHAEFFLER', 'TIMKEN', 'SKF', 'CARERATING', 'POWERINDIA', 'ATUL', 'BALRAMCHIN',
        
        # Cement (10)
        'ULTRACEMCO', 'SHREECEM', 'GRASIM', 'AMBUJACEM', 'ACC', 'JKCEMENT',
        'RAMCOCEM', 'DALMIACEM', 'HEIDELBERG', 'JKLAKSHMI',
        
        # Consumer Durables (10)
        'TITAN', 'HAVELLS', 'VOLTAS', 'DIXON', 'CROMPTON', 'SYMPHONY',
        'WHIRLPOOL', 'BLUESTAR', 'RAJESHEXPO', 'KAJARIACER',
        
        # Telecom & Media (10)
        'BHARTIARTL', 'IDEA', 'ZEEL', 'SUNTV', 'PVR', 'NETWORK18', 'TVTODAY',
        'HFCL', 'TTML', 'GTPL',
        
        # Real Estate (10)
        'DLF', 'GODREJPROP', 'OBEROIRLTY', 'BRIGADE', 'PHOENIXLTD', 'PRESTIGE',
        'SOBHA', 'MAHLIFE', 'SUNTECK', 'IBREALEST'
    ]
    all_symbols = list(set(all_symbols))[:200]  # Remove duplicates, limit to 200

print(f"\n🎯 Testing on {len(all_symbols)} stocks")
print(f"   Time horizon: 30 days")
print(f"   This may take 5-10 minutes...\n")

print("=" * 100)
print("📊 PHASE 1: DOWNLOADING HISTORICAL DATA")
print("=" * 100)

# Download price data for all stocks
stock_data_list = []
successful_downloads = 0
failed_symbols = []

for i, symbol in enumerate(all_symbols):
    try:
        ticker_symbol = symbol if '.NS' in symbol else f"{symbol}.NS"
        ticker = yf.Ticker(ticker_symbol)
        
        # Get 90 days of data
        hist = ticker.history(period='3mo')
        info = ticker.info
        
        if len(hist) < 35:
            failed_symbols.append((symbol, "Insufficient data"))
            continue
        
        # Calculate 30-day forward return
        start_price = hist['Close'].iloc[-31]
        current_price = hist['Close'].iloc[-1]
        forward_return = ((current_price - start_price) / start_price) * 100
        
        # Extract key metrics for scoring
        stock_info = {
            'symbol': symbol,
            'current_price': current_price,
            'forward_return_30d': forward_return,
            
            # Technical indicators
            'enhanced_rsi_14': None,  # Will calculate
            'enhanced_price_change_20d': ((hist['Close'].iloc[-1] - hist['Close'].iloc[-20]) / hist['Close'].iloc[-20] * 100) if len(hist) >= 20 else 0,
            'enhanced_macd_histogram': None,
            'enhanced_volume_ratio': hist['Volume'].iloc[-5:].mean() / hist['Volume'].mean() if len(hist) > 5 else 1.0,
            'volatility': hist['Close'].pct_change().std() * 100 if len(hist) > 5 else 2.0,
            
            # Fundamentals
            'pe_ratio': info.get('trailingPE', 20),
            'pb_ratio': info.get('priceToBook', 3),
            'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 10,
            'debt_to_equity': info.get('debtToEquity', 50) / 100 if info.get('debtToEquity') else 0.5,
            'net_margin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 10,
            'revenue_growth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 10,
        }
        
        # Calculate RSI
        if len(hist) >= 14:
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            stock_info['enhanced_rsi_14'] = rsi.iloc[-1]
            stock_info['real_rsi'] = rsi.iloc[-1]
        
        # Calculate MACD
        if len(hist) >= 26:
            exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
            exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            stock_info['enhanced_macd_histogram'] = histogram.iloc[-1]
        
        stock_data_list.append(stock_info)
        successful_downloads += 1
        
        if (i + 1) % 20 == 0:
            print(f"   Progress: {i + 1}/{len(all_symbols)} stocks | Success: {successful_downloads}")
            
    except Exception as e:
        failed_symbols.append((symbol, str(e)[:50]))
        continue

print(f"\n✅ Successfully downloaded data for {successful_downloads} stocks")
print(f"❌ Failed: {len(failed_symbols)} stocks")

if successful_downloads < 50:
    print("\n⚠️  Insufficient data for comprehensive backtest")
    print(f"   Need at least 50 stocks, got {successful_downloads}")
    exit()

# Convert to DataFrame
df_all = pd.DataFrame(stock_data_list)

print("\n" + "=" * 100)
print("📊 PHASE 2: CALCULATING SCORES")
print("=" * 100)

print("\nCalculating scores for all stocks...")

# Calculate OLD scores (using risk_adjusted_score logic - simplified)
df_all['old_score'] = 50  # Placeholder

# Calculate NEW scores (improved system)
scorer = ImprovedScoringEngine()
improved_scores = []

for idx, row in df_all.iterrows():
    stock_data = row.to_dict()
    result = scorer.calculate_improved_overall_score(row['symbol'], stock_data)
    improved_scores.append(result['improved_overall_score'])
    
    if (idx + 1) % 50 == 0:
        print(f"   Scored: {idx + 1}/{len(df_all)} stocks")

df_all['improved_score'] = improved_scores

print(f"\n✅ Scored {len(df_all)} stocks")
print(f"   Score range: {df_all['improved_score'].min():.1f} - {df_all['improved_score'].max():.1f}")

print("\n" + "=" * 100)
print("📈 PHASE 3: BACKTESTING RESULTS")
print("=" * 100)

# Overall statistics
avg_return = df_all['forward_return_30d'].mean()
median_return = df_all['forward_return_30d'].median()
std_return = df_all['forward_return_30d'].std()

print(f"\n📊 MARKET STATISTICS (30-day returns):")
print(f"   Average return:  {avg_return:+.2f}%")
print(f"   Median return:   {median_return:+.2f}%")
print(f"   Std deviation:   {std_return:.2f}%")
print(f"   Best performer:  {df_all['forward_return_30d'].max():+.2f}%")
print(f"   Worst performer: {df_all['forward_return_30d'].min():+.2f}%")

# Score correlation
correlation = df_all['improved_score'].corr(df_all['forward_return_30d'])
print(f"\n📊 SCORING SYSTEM CORRELATION:")
print(f"   Correlation: {correlation:+.3f}")

if correlation > 0.3:
    print(f"   ✅ STRONG predictive power")
elif correlation > 0.15:
    print(f"   🟡 MODERATE predictive power")
elif correlation > 0:
    print(f"   ⚠️  WEAK predictive power")
else:
    print(f"   ❌ NEGATIVE correlation (inverted!)")

print("\n" + "=" * 100)
print("🏆 QUINTILE ANALYSIS")
print("=" * 100)

# Divide into quintiles (5 groups)
df_all['quintile'] = pd.qcut(df_all['improved_score'], q=5, labels=['Q1 (Worst)', 'Q2', 'Q3', 'Q4', 'Q5 (Best)'])

print("\nPerformance by Score Quintile:")
print("-" * 80)
print(f"{'Quintile':<15} {'Stocks':>8} {'Avg Score':>10} {'Avg Return':>12} {'Win Rate':>10}")
print("-" * 80)

quintile_results = []
for quintile in ['Q1 (Worst)', 'Q2', 'Q3', 'Q4', 'Q5 (Best)']:
    q_data = df_all[df_all['quintile'] == quintile]
    count = len(q_data)
    avg_score = q_data['improved_score'].mean()
    avg_ret = q_data['forward_return_30d'].mean()
    win_rate = (q_data['forward_return_30d'] > median_return).sum() / count * 100
    
    quintile_results.append({
        'quintile': quintile,
        'count': count,
        'avg_score': avg_score,
        'avg_return': avg_ret,
        'win_rate': win_rate
    })
    
    print(f"{quintile:<15} {count:>8} {avg_score:>10.1f} {avg_ret:>+11.2f}% {win_rate:>9.0f}%")

print("-" * 80)

# Calculate spread (Q5 - Q1)
q5_return = quintile_results[4]['avg_return']
q1_return = quintile_results[0]['avg_return']
spread = q5_return - q1_return

print(f"\n📊 KEY METRICS:")
print(f"   Best quintile (Q5) return:  {q5_return:+.2f}%")
print(f"   Worst quintile (Q1) return: {q1_return:+.2f}%")
print(f"   Spread (Q5 - Q1):           {spread:+.2f}%")
print(f"   Alpha (Q5 vs market avg):   {(q5_return - avg_return):+.2f}%")

print("\n" + "=" * 100)
print("🎯 TOP 20 STOCKS BY SCORE")
print("=" * 100)

top_20 = df_all.nlargest(20, 'improved_score')[['symbol', 'improved_score', 'forward_return_30d']].copy()
top_20_avg = top_20['forward_return_30d'].mean()
top_20_wins = (top_20['forward_return_30d'] > median_return).sum()

print("\nTop 20 scored stocks:")
print("-" * 60)
print(f"{'Rank':<6} {'Symbol':<12} {'Score':>8} {'30d Return':>12} {'vs Median':>10}")
print("-" * 60)

for rank, (idx, row) in enumerate(top_20.iterrows(), 1):
    vs_median = "✅ Beat" if row['forward_return_30d'] > median_return else "❌ Lost"
    print(f"{rank:<6} {row['symbol']:<12} {row['improved_score']:>8.1f} {row['forward_return_30d']:>+11.2f}% {vs_median:>10}")

print("-" * 60)
print(f"{'AVERAGE':<6} {'':<12} {top_20['improved_score'].mean():>8.1f} {top_20_avg:>+11.2f}% {top_20_wins}/20 wins")

print("\n" + "=" * 100)
print("💔 BOTTOM 20 STOCKS BY SCORE")
print("=" * 100)

bottom_20 = df_all.nsmallest(20, 'improved_score')[['symbol', 'improved_score', 'forward_return_30d']].copy()
bottom_20_avg = bottom_20['forward_return_30d'].mean()

print("\nBottom 20 scored stocks (AVOID these):")
print("-" * 60)

for rank, (idx, row) in enumerate(bottom_20.iterrows(), 1):
    vs_median = "✅ Beat" if row['forward_return_30d'] > median_return else "❌ Lost"
    print(f"{rank:<6} {row['symbol']:<12} {row['improved_score']:>8.1f} {row['forward_return_30d']:>+11.2f}% {vs_median:>10}")

print("-" * 60)
print(f"{'AVERAGE':<6} {'':<12} {bottom_20['improved_score'].mean():>8.1f} {bottom_20_avg:>+11.2f}%")

print("\n" + "=" * 100)
print("📊 FINAL VERDICT")
print("=" * 100)

print(f"\n🎯 SCORING SYSTEM PERFORMANCE:")
print(f"   Stocks tested:        {len(df_all)}")
print(f"   Correlation:          {correlation:+.3f}")
print(f"   Top-20 avg return:    {top_20_avg:+.2f}%")
print(f"   Bottom-20 avg return: {bottom_20_avg:+.2f}%")
print(f"   Spread (Top - Bottom):{(top_20_avg - bottom_20_avg):+.2f}%")
print(f"   Alpha (Top vs Avg):   {(top_20_avg - avg_return):+.2f}%")
print(f"   Win rate (Top-20):    {(top_20_wins / 20 * 100):.0f}%")

if spread > 5 and correlation > 0.3:
    print(f"\n✅ EXCELLENT - System shows strong predictive power")
    print(f"   Recommendation: USE with confidence")
    print(f"   Strategy: Focus on stocks scoring >80")
    
elif spread > 3 and correlation > 0.2:
    print(f"\n🟡 GOOD - System has meaningful edge")
    print(f"   Recommendation: USE but validate picks")
    print(f"   Strategy: Focus on stocks scoring >75")
    
elif spread > 1.5:
    print(f"\n⚠️  FAIR - System has some value")
    print(f"   Recommendation: Use as ONE factor, not sole decision")
    print(f"   Strategy: Combine with other analysis")
    
else:
    print(f"\n❌ POOR - System lacks predictive power")
    print(f"   Recommendation: Further refinement needed")

# Save results
output_file = f"backtest_results_comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df_all.to_csv(f"reports/{output_file}", index=False)
print(f"\n💾 Detailed results saved to: reports/{output_file}")

print("\n" + "=" * 100)
