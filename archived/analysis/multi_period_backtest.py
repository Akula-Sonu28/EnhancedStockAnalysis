"""
MULTI-PERIOD SCORING SYSTEM BACKTEST
Tests the scoring system across different time periods and holding durations
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from corrected_scoring_engine import CorrectedScoringEngine
import warnings
warnings.filterwarnings('ignore')

print("=" * 100)
print("📊 MULTI-PERIOD SCORING SYSTEM BACKTEST")
print("=" * 100)

# Initialize scoring engine
scoring_engine = CorrectedScoringEngine()

# Multiple test configurations
TEST_CONFIGS = [
    {"months_back": 1, "forward_days": 7, "name": "1M Back, 7D Forward"},
    {"months_back": 1, "forward_days": 14, "name": "1M Back, 14D Forward"},
    {"months_back": 1, "forward_days": 30, "name": "1M Back, 30D Forward"},
    {"months_back": 3, "forward_days": 7, "name": "3M Back, 7D Forward"},
    {"months_back": 3, "forward_days": 14, "name": "3M Back, 14D Forward"},
    {"months_back": 3, "forward_days": 30, "name": "3M Back, 30D Forward"},
    {"months_back": 6, "forward_days": 7, "name": "6M Back, 7D Forward"},
    {"months_back": 6, "forward_days": 14, "name": "6M Back, 14D Forward"},
    {"months_back": 6, "forward_days": 30, "name": "6M Back, 30D Forward"},
    {"months_back": 12, "forward_days": 30, "name": "12M Back, 30D Forward"},
]

TOP_N = 10
BOTTOM_N = 10

# EXTENDED DIVERSIFIED STOCK UNIVERSE (150+ stocks across sectors)
test_symbols = [
    # BANKING & FINANCIAL SERVICES (Current Holdings + Major Banks)
    'MAHABANK.NS', 'SBIN.NS', 'CUB.NS', 'INDIANB.NS', 'GICRE.NS', 
    'CANBK.NS', 'KARURVYSYA.NS', 'UNIONBANK.NS', 'PNB.NS',
    'BANKBARODA.NS', 'ICICIBANK.NS', 'BANKINDIA.NS', 'CENTRALBK.NS',
    'FEDERALBNK.NS', 'IDBI.NS', 'UCOBANK.NS', 'IOB.NS', 'J&KBANK.NS',
    'RECLTD.NS', 'KOTAKBANK.NS', 'AXISBANK.NS', 'AUBANK.NS', 'HDFCBANK.NS', 
    'UJJIVANSFB.NS', 'BANDHANBNK.NS', 'YESBANK.NS', 'PFC.NS', 'IDFCFIRSTB.NS',
    
    # NBFC & FINANCIAL SERVICES
    'BAJAJFINSV.NS', 'BAJFINANCE.NS', 'SHRIRAMFIN.NS', 'MUTHOOTFIN.NS', 
    'LICHSGFIN.NS', 'CHOLAFIN.NS', 'M&MFIN.NS', 'MANAPPURAM.NS', 'MOTILALOFS.NS',
    'IIFL.NS', 'SRTRANSFIN.NS', 'INDIAINFOLINE.NS',
    
    # IT & TECHNOLOGY
    'TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'LTI.NS',
    'MINDTREE.NS', 'COFORGE.NS', 'PERSISTENT.NS', 'MPHASIS.NS', 'OFSS.NS',
    'LTTS.NS', 'ZENSAR.NS', 'NIITTECH.NS', 'RAMSARUP.NS',
    
    # TELECOM & INFRASTRUCTURE  
    'BHARTIARTL.NS', 'INDUSTOWER.NS', 'RAILTEL.NS', 'GTLINFRA.NS',
    
    # CONSUMER GOODS & FMCG
    'NESTLEIND.NS', 'HINDUNILVR.NS', 'ITC.NS', 'BRITANNIA.NS', 'DABUR.NS',
    'MARICO.NS', 'GODREJCP.NS', 'COLPAL.NS', 'EMAMILTD.NS', 'TATACONSUM.NS',
    'UBL.NS', 'RADICO.NS', 'VBL.NS', 'BATAINDIA.NS', 'RELAXO.NS',
    
    # AUTOMOBILES & AUTO ANCILLARIES
    'TATAMOTORS.NS', 'MARUTI.NS', 'M&M.NS', 'BAJAJ-AUTO.NS', 'HEROMOTOCO.NS',
    'TVSMOTORS.NS', 'EICHERMOT.NS', 'ASHOKLEY.NS', 'APOLLOTYRE.NS', 'MRF.NS',
    'BOSCHLTD.NS', 'MOTHERSON.NS', 'BALKRISIND.NS', 'EXIDEIND.NS',
    
    # PHARMACEUTICALS & HEALTHCARE
    'DRREDDY.NS', 'SUNPHARMA.NS', 'CIPLA.NS', 'LUPIN.NS', 'DIVISLAB.NS',
    'BIOCON.NS', 'CADILAHC.NS', 'ALKEM.NS', 'TORNTPHARM.NS', 'AUROPHARMA.NS',
    'GLENMARK.NS', 'ABBOTINDIA.NS', 'PFIZER.NS', 'GLAXO.NS',
    
    # ENERGY & POWER
    'RELIANCE.NS', 'ONGC.NS', 'IOC.NS', 'BPCL.NS', 'HPCL.NS', 'GAIL.NS',
    'NTPC.NS', 'POWERGRID.NS', 'COALINDIA.NS', 'ADANIGREEN.NS', 'TATAPOWER.NS',
    'ADANIPOWER.NS', 'NHPC.NS', 'SJVN.NS', 'PFC.NS', 'RECLTD.NS',
    
    # METALS & MINING
    'VEDL.NS', 'HINDALCO.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'SAILSTEEL.NS',
    'NMDC.NS', 'HINDZINC.NS', 'NATIONALUM.NS', 'MOIL.NS', 'WELCORP.NS',
    'JINDALSTEL.NS', 'RATNAMANI.NS', 'ORIENTREF.NS',
    
    # CEMENT & CONSTRUCTION
    'ULTRACEMCO.NS', 'ACC.NS', 'AMBUJACEMENT.NS', 'SHREECEM.NS', 'RAMCOCEM.NS',
    'HEIDELBERG.NS', 'JKCEMENT.NS', 'PRISMCEM.NS',
    
    # INFRASTRUCTURE & CAPITAL GOODS
    'LARSENTOUBRO.NS', 'SIEMENS.NS', 'ABB.NS', 'BHEL.NS', 'BEL.NS',
    'HAL.NS', 'BEML.NS', 'CONCOR.NS', 'IRCON.NS', 'RVNL.NS',
    'KEC.NS', 'THERMAX.NS', 'VOLTAS.NS', 'CUMMINSIND.NS',
    
    # RETAIL & E-COMMERCE
    'DMART.NS', 'TRENT.NS', 'SHOPERSTOP.NS', 'V-MART.NS', 'ADITYA.NS',
    'FRETAIL.NS', 'SPENCERS.NS', 'LANDMARK.NS',
    
    # CHEMICALS & FERTILIZERS
    'UPL.NS', 'PIDILITIND.NS', 'AAVAS.NS', 'DEEPAKNTR.NS', 'GNFC.NS',
    'CHAMBLFERT.NS', 'COROMANDEL.NS', 'GSFC.NS', 'NFL.NS', 'RCF.NS',
    
    # TEXTILES & APPAREL
    'WELSPUNIND.NS', 'TRIDENT.NS', 'ARVIND.NS', 'RTNPOWER.NS', 'RAYMOND.NS',
    'VARDHMAN.NS', 'ALOKTEXT.NS', 'PAGEIND.NS',
    
    # REAL ESTATE
    'DLF.NS', 'GODREJPROP.NS', 'BRIGADE.NS', 'OBEROIRLTY.NS', 'PRESTIGE.NS',
    'SOBHA.NS', 'MAHLIFE.NS', 'SUNTECK.NS',
    
    # MEDIA & ENTERTAINMENT  
    'ZEEL.NS', 'SUNTV.NS', 'NETWORK18.NS', 'TVTODAY.NS', 'JAGRAN.NS',
    'DISHTV.NS', 'SAREGAMA.NS', 'BALAJITELE.NS',
    
    # AIRLINES & HOSPITALITY
    'INDIGO.NS', 'SPICEJET.NS', 'JETAIRWAYS.NS', 'INDHOTEL.NS', 'LEMONTREE.NS',
    'CHALET.NS', 'MAHINDRA.NS',
    
    # DIVERSIFIED CONGLOMERATES
    'ITC.NS', 'GODREJIND.NS', 'MAHINDRA.NS', 'BAJAJHLDNG.NS', 'SIEMENS.NS'
]

print(f"\n📋 Testing {len(TEST_CONFIGS)} different time periods")
print(f"   Stock universe: {len(test_symbols)} stocks")

# Helper function for RSI
def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    if len(prices) < period + 1:
        return 50
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50

# Storage for all results
all_results = []

print("\n" + "=" * 100)
print("🔄 RUNNING MULTI-PERIOD BACKTESTS")
print("=" * 100)

for config_idx, config in enumerate(TEST_CONFIGS):
    print(f"\n{'='*80}")
    print(f"Test #{config_idx + 1}: {config['name']}")
    print(f"{'='*80}")
    
    months_back = config['months_back']
    forward_days = config['forward_days']
    
    # Generate test dates for this configuration
    end_date = datetime.now()
    num_tests = min(months_back, 6)  # Max 6 test points per config
    test_dates = []
    
    for i in range(num_tests):
        # Space tests evenly across the lookback period
        days_back = int((months_back * 30) * (i + 1) / (num_tests + 1))
        test_date = end_date - timedelta(days=days_back + forward_days)
        test_dates.append(test_date)
    
    test_dates.reverse()  # Chronological order
    
    config_results = []
    
    print(f"   Test dates: {[d.strftime('%Y-%m-%d') for d in test_dates]}")
    print(f"   Forward window: {forward_days} days")
    
    for test_idx, test_date in enumerate(test_dates):
        print(f"\n  📅 Test Point {test_idx + 1}: {test_date.strftime('%Y-%m-%d')}")
        
        # Calculate forward date for returns measurement
        forward_date = test_date + timedelta(days=forward_days)
        
        if forward_date > datetime.now():
            print(f"    ⚠️ Forward date is in future, skipping...")
            continue
        
        period_scores = []
        
        # Get data and calculate scores for each stock
        valid_stocks = 0
        
        for symbol in test_symbols:
            try:
                # Download historical data
                ticker = yf.Ticker(symbol)
                
                # Get data from 90 days before test_date to forward_date
                start_data = test_date - timedelta(days=90)
                hist_data = ticker.history(start=start_data, end=forward_date + timedelta(days=5))
                
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
                price_change_5d = 0
                if len(test_date_data) > 5:
                    price_change_5d = ((test_price - test_date_data['Close'].iloc[-6]) / test_date_data['Close'].iloc[-6] * 100)
                
                volume_ratio = 1
                if len(recent_data) > 20:
                    volume_ratio = recent_data['Volume'].iloc[-5:].mean() / recent_data['Volume'].iloc[-20:].mean()
                
                # Get fundamental data (use cached values to avoid API limits)
                pe_ratio = 20
                pb_ratio = 2
                roe = 10
                debt_to_equity = 1
                
                try:
                    info = ticker.info
                    pe_ratio = info.get('trailingPE', 20) or 20
                    pb_ratio = info.get('priceToBook', 2) or 2
                    roe = (info.get('returnOnEquity', 0.1) or 0.1) * 100
                    debt_to_equity = (info.get('debtToEquity', 100) or 100) / 100
                except:
                    pass  # Use defaults
                
                # Get 52-week high/low
                year_high = test_date_data['High'].rolling(min(252, len(test_date_data))).max().iloc[-1]
                year_low = test_date_data['Low'].rolling(min(252, len(test_date_data))).min().iloc[-1]
                
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
                    'config': config['name']
                })
                
                valid_stocks += 1
                
            except Exception as e:
                # Silently skip stocks with errors
                continue
        
        if len(period_scores) < 10:
            print(f"    ⚠️ Only {len(period_scores)} valid stocks, need at least 10")
            continue
        
        # Convert to dataframe and analyze
        df_period = pd.DataFrame(period_scores)
        df_period = df_period.sort_values('score', ascending=False)
        
        # Get top and bottom stocks
        top_stocks = df_period.head(TOP_N)
        bottom_stocks = df_period.tail(BOTTOM_N)
        
        # Calculate returns
        top_return = top_stocks['actual_return'].mean()
        bottom_return = bottom_stocks['actual_return'].mean()
        all_return = df_period['actual_return'].mean()
        
        period_result = {
            'config_name': config['name'],
            'test_date': test_date,
            'stocks_analyzed': len(df_period),
            'top_return': top_return,
            'bottom_return': bottom_return,
            'all_return': all_return,
            'alpha': top_return - all_return,
            'spread': top_return - bottom_return,
            'months_back': months_back,
            'forward_days': forward_days
        }
        
        config_results.append(period_result)
        
        print(f"    📊 Results: {len(df_period)} stocks")
        print(f"       Top {TOP_N}: {top_return:>6.2f}%")
        print(f"       Bottom {BOTTOM_N}: {bottom_return:>6.2f}%")
        print(f"       Alpha: {top_return - all_return:>6.2f}%")
    
    # Summarize this configuration
    if config_results:
        avg_alpha = np.mean([r['alpha'] for r in config_results])
        avg_spread = np.mean([r['spread'] for r in config_results])
        win_rate = sum(1 for r in config_results if r['top_return'] > r['bottom_return']) / len(config_results) * 100
        
        print(f"\n  📈 {config['name']} Summary:")
        print(f"     Tests: {len(config_results)}")
        print(f"     Avg Alpha: {avg_alpha:6.2f}%")
        print(f"     Avg Spread: {avg_spread:6.2f}%")
        print(f"     Win Rate: {win_rate:6.1f}%")
        
        all_results.extend(config_results)

# Overall analysis
print("\n\n" + "=" * 100)
print("📊 MULTI-PERIOD BACKTEST SUMMARY")
print("=" * 100)

if not all_results:
    print("\n❌ No valid results across all periods")
else:
    # Convert to DataFrame for analysis
    df_all = pd.DataFrame(all_results)
    
    # Group by configuration
    print(f"\n📈 Results by Time Period ({len(all_results)} total tests):")
    print(f"\n{'Configuration':<25} {'Tests':>5} {'Avg Alpha':>10} {'Avg Spread':>11} {'Win Rate':>9}")
    print("-" * 70)
    
    config_summary = []
    
    for config_name in df_all['config_name'].unique():
        config_data = df_all[df_all['config_name'] == config_name]
        
        avg_alpha = config_data['alpha'].mean()
        avg_spread = config_data['spread'].mean()
        win_rate = (config_data['alpha'] > 0).sum() / len(config_data) * 100
        
        print(f"{config_name:<25} {len(config_data):>5} {avg_alpha:>9.2f}% {avg_spread:>10.2f}% {win_rate:>8.1f}%")
        
        config_summary.append({
            'config': config_name,
            'tests': len(config_data),
            'alpha': avg_alpha,
            'spread': avg_spread,
            'win_rate': win_rate
        })
    
    # Best performing configurations
    config_df = pd.DataFrame(config_summary)
    config_df = config_df.sort_values('alpha', ascending=False)
    
    print(f"\n🏆 BEST PERFORMING CONFIGURATIONS:")
    print(f"\n{'Rank':<4} {'Configuration':<25} {'Alpha':>8} {'Win Rate':>9}")
    print("-" * 50)
    
    for i, (_, row) in enumerate(config_df.head(5).iterrows()):
        print(f"{i+1:<4} {row['config']:<25} {row['alpha']:>7.2f}% {row['win_rate']:>8.1f}%")
    
    # Overall statistics
    overall_alpha = df_all['alpha'].mean()
    overall_spread = df_all['spread'].mean()
    overall_win_rate = (df_all['alpha'] > 0).sum() / len(df_all) * 100
    
    print(f"\n📊 OVERALL PERFORMANCE:")
    print(f"   Total Tests: {len(df_all)}")
    print(f"   Average Alpha: {overall_alpha:6.2f}%")
    print(f"   Average Spread: {overall_spread:6.2f}%")
    print(f"   Win Rate: {overall_win_rate:6.1f}%")
    
    # Verdict
    print(f"\n🎯 MULTI-PERIOD VERDICT:")
    
    if overall_alpha > 2 and overall_win_rate > 60:
        verdict = "✅ SCORING SYSTEM CONSISTENTLY WORKS"
        status = "PRODUCTION READY"
        detail = f"System delivers {overall_alpha:.2f}% alpha with {overall_win_rate:.1f}% win rate across all periods"
    elif overall_alpha > 0 and overall_win_rate > 50:
        verdict = "🟡 SCORING SYSTEM PARTIALLY WORKS"
        status = "NEEDS OPTIMIZATION"
        detail = f"Modest {overall_alpha:.2f}% alpha with {overall_win_rate:.1f}% win rate - consider tuning"
    else:
        verdict = "❌ SCORING SYSTEM INCONSISTENT"
        status = "NEEDS MAJOR REVISION"
        detail = f"Poor {overall_alpha:.2f}% alpha with {overall_win_rate:.1f}% win rate - fundamental issues"
    
    print(f"\n{verdict}")
    print(f"Status: {status}")
    print(f"Detail: {detail}")
    
    # Time horizon analysis
    print(f"\n📅 ANALYSIS BY TIME HORIZON:")
    print("\nForward Period Performance:")
    
    for forward_days in [7, 14, 30]:
        forward_data = df_all[df_all['forward_days'] == forward_days]
        if not forward_data.empty:
            avg_alpha = forward_data['alpha'].mean()
            win_rate = (forward_data['alpha'] > 0).sum() / len(forward_data) * 100
            print(f"   {forward_days:2d}-day forward: {avg_alpha:6.2f}% alpha, {win_rate:5.1f}% win rate ({len(forward_data)} tests)")
    
    print(f"\nLookback Period Performance:")
    
    for months_back in [1, 3, 6, 12]:
        lookback_data = df_all[df_all['months_back'] == months_back]
        if not lookback_data.empty:
            avg_alpha = lookback_data['alpha'].mean()
            win_rate = (lookback_data['alpha'] > 0).sum() / len(lookback_data) * 100
            print(f"   {months_back:2d}-month lookback: {avg_alpha:6.2f}% alpha, {win_rate:5.1f}% win rate ({len(lookback_data)} tests)")

print("\n" + "=" * 100)
print("📝 RECOMMENDATIONS")
print("=" * 100)

if all_results:
    best_config = config_df.iloc[0]
    
    print(f"""
🎯 OPTIMAL CONFIGURATION IDENTIFIED:
   Best Setup: {best_config['config']}
   Alpha: {best_config['alpha']:.2f}%
   Win Rate: {best_config['win_rate']:.1f}%

📈 TRADING RECOMMENDATIONS:
   1. Use scoring system with {best_config['config'].split(',')[1].strip()} holding period
   2. Rebalance every {best_config['config'].split(',')[0].split()[0]} 
   3. Focus on scores >75 for buy signals
   4. Avoid scores <50 for risk management
   
🔄 SYSTEM MAINTENANCE:
   1. Validate system quarterly using multi-period backtest
   2. Monitor win rate - if drops below 60%, retune parameters
   3. Track alpha - target >2% for production use
   4. Consider position sizing based on score confidence
""")
else:
    print(f"""
⚠️ INSUFFICIENT DATA FOR VALIDATION
   
Next Steps:
   1. Extend data sources (more stock universe)
   2. Use longer historical periods (if available)
   3. Consider paper trading to validate in real-time
   4. Focus on liquid stocks with complete data history
""")

print("\n✅ MULTI-PERIOD BACKTEST COMPLETE!")