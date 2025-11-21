"""
SCORING SYSTEM OPTIMIZATION
Tests different weight combinations to maximize 30-day forward returns
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from itertools import product
import warnings
warnings.filterwarnings('ignore')

print("=" * 100)
print("🔧 SCORING SYSTEM OPTIMIZATION")
print("=" * 100)

# Load the Excel with current scores and components
excel_file = 'reports/Enhanced_Stock_Report_20251006_211751.xlsx'

try:
    df = pd.read_excel(excel_file, sheet_name='Complete Data')
    print(f"\n✅ Loaded {excel_file}")
    print(f"   Stocks: {len(df)}")
    print(f"   Current score range: {df['risk_adjusted_score'].min():.1f} - {df['risk_adjusted_score'].max():.1f}")
except Exception as e:
    print(f"\n❌ Could not load {excel_file}: {e}")
    exit()

# Extract component scores
components = {
    'contrarian_technical': 'contrarian_technical_score',
    'contrarian_momentum': 'contrarian_momentum_score',
    'fundamental_quality': 'fundamental_quality_score',
    'value_opportunity': 'value_opportunity_score'
}

# Check which components are available
available_components = {}
for comp_name, col_name in components.items():
    if col_name in df.columns:
        available_components[comp_name] = col_name
        print(f"   ✓ Found {comp_name}")
    else:
        print(f"   ✗ Missing {col_name}")

if len(available_components) < 4:
    print("\n⚠️  Not all component scores available in Excel")
    print("   Will test with available data only")

print("\n" + "=" * 100)
print("📊 DOWNLOADING FORWARD RETURN DATA (30 DAYS)")
print("=" * 100)

# Download 30-day forward returns
forward_returns = {}
stocks_to_test = df['symbol'].tolist()[:40]  # Limit for speed

print(f"\nDownloading price data for {len(stocks_to_test)} stocks...")

for i, symbol in enumerate(stocks_to_test):
    try:
        ticker_symbol = symbol if '.NS' in symbol else f"{symbol}.NS"
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period='60d')
        
        if len(hist) >= 35:
            # Calculate 30-day return
            start_price = hist['Close'].iloc[-31]
            current_price = hist['Close'].iloc[-1]
            ret_30d = ((current_price - start_price) / start_price) * 100
            forward_returns[symbol] = ret_30d
        
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i + 1}/{len(stocks_to_test)}")
            
    except Exception as e:
        continue

print(f"\n✅ Got forward returns for {len(forward_returns)} stocks")

# Add returns to dataframe
df['forward_return_30d'] = df['symbol'].map(forward_returns)
df_test = df[df['forward_return_30d'].notna()].copy()

print(f"\n📊 Test dataset: {len(df_test)} stocks with complete data")

if len(df_test) < 20:
    print("❌ Insufficient data for optimization")
    exit()

print("\n" + "=" * 100)
print("🔬 ANALYZING COMPONENT CORRELATIONS")
print("=" * 100)

# Analyze individual component correlations with forward returns
print("\nComponent correlation with 30-day returns:")
print("-" * 60)

for comp_name, col_name in available_components.items():
    if col_name in df_test.columns:
        corr = df_test[col_name].corr(df_test['forward_return_30d'])
        print(f"   {comp_name:25s}: {corr:+.3f} {'✅ POSITIVE' if corr > 0.1 else '❌ NEGATIVE' if corr < -0.1 else '🟡 WEAK'}")

# Current scoring system correlation
current_corr = df_test['risk_adjusted_score'].corr(df_test['forward_return_30d'])
print(f"\n   {'CURRENT SYSTEM':25s}: {current_corr:+.3f} (baseline to beat)")

print("\n" + "=" * 100)
print("🎯 TESTING WEIGHT COMBINATIONS")
print("=" * 100)

# Define weight ranges to test
weight_options = [0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4]

best_correlation = current_corr
best_weights = {'contrarian_technical': 0.25, 'contrarian_momentum': 0.20, 
                'fundamental_quality': 0.20, 'value_opportunity': 0.15}
best_score = None

print(f"\nTesting combinations (this may take a minute)...")
print(f"Weight options: {weight_options}")

# Test a subset of combinations (full grid would be 8^4 = 4096 combinations)
# Test every combination that sums close to 1.0
tested = 0
improved = 0

for w1 in weight_options:
    for w2 in weight_options:
        for w3 in weight_options:
            for w4 in weight_options:
                # Weights should sum to approximately 0.8-1.0 (leaving room for sector/timing)
                weight_sum = w1 + w2 + w3 + w4
                if weight_sum < 0.75 or weight_sum > 1.05:
                    continue
                
                tested += 1
                
                # Calculate score with these weights
                test_score = (
                    df_test[available_components['contrarian_technical']] * w1 +
                    df_test[available_components['contrarian_momentum']] * w2 +
                    df_test[available_components['fundamental_quality']] * w3 +
                    df_test[available_components['value_opportunity']] * w4
                )
                
                # Calculate correlation with forward returns
                corr = test_score.corr(df_test['forward_return_30d'])
                
                if corr > best_correlation + 0.01:  # At least 0.01 improvement
                    best_correlation = corr
                    best_weights = {
                        'contrarian_technical': w1,
                        'contrarian_momentum': w2,
                        'fundamental_quality': w3,
                        'value_opportunity': w4
                    }
                    best_score = test_score
                    improved += 1
                    print(f"   🎉 New best! Correlation: {corr:.3f} | Weights: {w1:.2f}, {w2:.2f}, {w3:.2f}, {w4:.2f}")

print(f"\n✅ Tested {tested} weight combinations")
print(f"   Found {improved} improvements over baseline")

print("\n" + "=" * 100)
print("📈 OPTIMIZATION RESULTS")
print("=" * 100)

print(f"\n🎯 BEST WEIGHTS FOUND:")
print(f"   Correlation with 30d returns: {best_correlation:+.3f}")
print(f"   Improvement vs current: {(best_correlation - current_corr):+.3f}")
print()
print(f"   Component Weights:")
for comp, weight in best_weights.items():
    print(f"      {comp:25s}: {weight:.2f} ({weight*100:.0f}%)")

# Calculate statistics with best weights
if best_score is not None:
    df_test['optimized_score'] = best_score
    
    # Top vs bottom comparison
    df_test_sorted = df_test.sort_values('optimized_score', ascending=False)
    top_10 = df_test_sorted.head(10)
    bottom_10 = df_test_sorted.tail(10)
    
    top_return = top_10['forward_return_30d'].mean()
    bottom_return = bottom_10['forward_return_30d'].mean()
    all_return = df_test['forward_return_30d'].mean()
    
    print(f"\n📊 PERFORMANCE WITH OPTIMIZED WEIGHTS:")
    print(f"   Top-10 avg return:     {top_return:+.2f}%")
    print(f"   Bottom-10 avg return:  {bottom_return:+.2f}%")
    print(f"   All stocks avg:        {all_return:+.2f}%")
    print(f"   Alpha (Top vs All):    {(top_return - all_return):+.2f}%")
    print(f"   Spread (Top vs Bottom):{(top_return - bottom_return):+.2f}%")

print("\n" + "=" * 100)
print("💡 RECOMMENDATIONS")
print("=" * 100)

improvement_pct = ((best_correlation - current_corr) / abs(current_corr) * 100) if current_corr != 0 else 0

if improvement_pct > 20:
    print("\n✅ SIGNIFICANT IMPROVEMENT FOUND")
    print(f"   Correlation improved by {improvement_pct:.1f}%")
    print("\n   ACTION: Update corrected_scoring_engine.py with new weights:")
    print(f"      self.component_weights = {{")
    for comp, weight in best_weights.items():
        print(f"          '{comp}': {weight:.2f},")
    print(f"      }}")
    
elif improvement_pct > 5:
    print("\n🟡 MODERATE IMPROVEMENT FOUND")
    print(f"   Correlation improved by {improvement_pct:.1f}%")
    print("\n   ACTION: Consider updating weights if gain justifies change")
    
else:
    print("\n🔴 MINIMAL IMPROVEMENT")
    print(f"   Correlation improved by only {improvement_pct:.1f}%")
    print("\n   ACTION: Weight tuning won't help much. Need bigger changes:")
    print("      1. Add new components (momentum, volume, sentiment)")
    print("      2. Use different technical indicators")
    print("      3. Add market regime detection")
    print("      4. Consider machine learning approach")

print("\n" + "=" * 100)
print("🔍 COMPONENT ANALYSIS")
print("=" * 100)

print("\nWhich components are actually useful?")
print("-" * 60)

# Individual component predictive power
for comp_name, col_name in available_components.items():
    if col_name in df_test.columns:
        # Sort by component, compare top vs bottom
        df_sorted = df_test.sort_values(col_name, ascending=False)
        top_ret = df_sorted.head(10)['forward_return_30d'].mean()
        bot_ret = df_sorted.tail(10)['forward_return_30d'].mean()
        spread = top_ret - bot_ret
        
        corr = df_test[col_name].corr(df_test['forward_return_30d'])
        
        verdict = "✅ KEEP" if spread > 2 else "⚠️  WEAK" if spread > 0 else "❌ REMOVE"
        
        print(f"\n{comp_name.upper()}")
        print(f"   Correlation: {corr:+.3f}")
        print(f"   Top-10 return: {top_ret:+.2f}%")
        print(f"   Bot-10 return: {bot_ret:+.2f}%")
        print(f"   Spread: {spread:+.2f}%")
        print(f"   Verdict: {verdict}")

print("\n" + "=" * 100)
print("🎓 NEXT STEPS")
print("=" * 100)

print("\n1. If improvement is good (>20%):")
print("   → Update weights in corrected_scoring_engine.py")
print("   → Rerun analysis to generate new Excel report")
print("   → Backtest again to verify improvement")

print("\n2. If improvement is minimal (<5%):")
print("   → Consider removing weak components")
print("   → Add new components (volume, market regime)")
print("   → Try different scoring approaches")

print("\n3. To apply optimized weights:")
print("   → Edit corrected_scoring_engine.py line 13-18")
print("   → Change component_weights dictionary")
print("   → Run: python analyze_top200_stocks_enhanced.py")

print("\n" + "=" * 100)
