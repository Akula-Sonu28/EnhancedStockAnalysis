"""
TEST IMPROVED SCORING VS OLD SCORING
Quick comparison to see if changes actually help
"""

import pandas as pd
import yfinance as yf
from improved_scoring_engine import ImprovedScoringEngine
import warnings
warnings.filterwarnings('ignore')

print("=" * 100)
print("🆚 OLD vs NEW SCORING COMPARISON")
print("=" * 100)

# Load existing data
excel_file = 'reports/Enhanced_Stock_Report_20251006_211751.xlsx'
df = pd.read_excel(excel_file, sheet_name='Complete Data')

print(f"\n✅ Loaded {len(df)} stocks from {excel_file}")

# Get forward returns (already downloaded in previous test)
print("\n📊 Downloading 30-day forward returns...")
forward_returns = {}

for i, symbol in enumerate(df['symbol'].tolist()[:40]):
    try:
        ticker_symbol = symbol if '.NS' in symbol else f"{symbol}.NS"
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period='60d')
        
        if len(hist) >= 35:
            start_price = hist['Close'].iloc[-31]
            current_price = hist['Close'].iloc[-1]
            ret_30d = ((current_price - start_price) / start_price) * 100
            forward_returns[symbol] = ret_30d
        
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i + 1}/{len(df)}")
            
    except:
        continue

df['forward_return_30d'] = df['symbol'].map(forward_returns)
df_test = df[df['forward_return_30d'].notna()].copy()

print(f"\n✅ Got returns for {len(df_test)} stocks")

# Calculate improved scores
print("\n🔧 Calculating improved scores...")
scorer = ImprovedScoringEngine()
improved_scores = []

for idx, row in df_test.iterrows():
    stock_data = row.to_dict()
    result = scorer.calculate_improved_overall_score(row['symbol'], stock_data)
    improved_scores.append(result['improved_overall_score'])

df_test['improved_score'] = improved_scores

print("\n" + "=" * 100)
print("📈 PERFORMANCE COMPARISON")
print("=" * 100)

# Compare OLD vs NEW scoring
old_corr = df_test['risk_adjusted_score'].corr(df_test['forward_return_30d'])
new_corr = df_test['improved_score'].corr(df_test['forward_return_30d'])

print(f"\n📊 CORRELATION WITH 30-DAY RETURNS:")
print(f"   OLD scoring: {old_corr:+.3f}")
print(f"   NEW scoring: {new_corr:+.3f}")
print(f"   Improvement: {(new_corr - old_corr):+.3f} ({((new_corr - old_corr) / abs(old_corr) * 100):+.1f}%)")

# Top 10 vs Bottom 10 comparison
print("\n" + "=" * 100)
print("🏆 TOP 10 vs BOTTOM 10 COMPARISON")
print("=" * 100)

# OLD SCORING
df_old = df_test.sort_values('risk_adjusted_score', ascending=False)
old_top_df = df_old.head(10)
old_top = old_top_df['forward_return_30d'].mean()
old_bot_df = df_old.tail(10)
old_bot = old_bot_df['forward_return_30d'].mean()
old_spread = old_top - old_bot

# NEW SCORING
df_new = df_test.sort_values('improved_score', ascending=False)
new_top_df = df_new.head(10)
new_top = new_top_df['forward_return_30d'].mean()
new_bot_df = df_new.tail(10)
new_bot = new_bot_df['forward_return_30d'].mean()
new_spread = new_top - new_bot

print(f"\nOLD SCORING:")
print(f"   Top-10 return:  {old_top:+.2f}%")
print(f"   Bot-10 return:  {old_bot:+.2f}%")
print(f"   Spread:         {old_spread:+.2f}%")

print(f"\nNEW SCORING:")
print(f"   Top-10 return:  {new_top:+.2f}%")
print(f"   Bot-10 return:  {new_bot:+.2f}%")
print(f"   Spread:         {new_spread:+.2f}%")

print(f"\n📊 IMPROVEMENT:")
print(f"   Spread improved: {(new_spread - old_spread):+.2f}% points")
improvement_pct = ((new_spread - old_spread) / abs(old_spread) * 100) if old_spread != 0 else 0
print(f"   Percentage gain: {improvement_pct:+.1f}%")

# Show top stocks from each system
print("\n" + "=" * 100)
print("🎯 TOP 10 STOCKS COMPARISON")
print("=" * 100)

print("\nOLD SCORING TOP 10:")
print("-" * 60)
for idx, row in old_top_df.iterrows():
    symbol = row['symbol']
    old_score = row['risk_adjusted_score']
    ret = row['forward_return_30d']
    perf = "✅" if ret > df_test['forward_return_30d'].median() else "❌"
    print(f"   {symbol:12s} | Score: {old_score:5.1f} | Return: {ret:+6.2f}% {perf}")

print("\nNEW SCORING TOP 10:")
print("-" * 60)
for idx, row in new_top_df.iterrows():
    symbol = row['symbol']
    new_score = row['improved_score']
    ret = row['forward_return_30d']
    perf = "✅" if ret > df_test['forward_return_30d'].median() else "❌"
    print(f"   {symbol:12s} | Score: {new_score:5.1f} | Return: {ret:+6.2f}% {perf}")

print("\n" + "=" * 100)
print("💡 VERDICT")
print("=" * 100)

if new_spread > old_spread + 2:
    print("\n✅ SIGNIFICANT IMPROVEMENT")
    print(f"   New system has {(new_spread - old_spread):+.2f}% better spread")
    print("\n   RECOMMENDATION: Replace old scoring with new system")
    print("   ACTION: Integrate improved_scoring_engine.py into main analysis")
    
elif new_spread > old_spread:
    print("\n🟡 MODERATE IMPROVEMENT")
    print(f"   New system has {(new_spread - old_spread):+.2f}% better spread")
    print("\n   RECOMMENDATION: Consider using new system")
    
else:
    print("\n🔴 NO IMPROVEMENT")
    print(f"   New system is {(new_spread - old_spread):+.2f}% worse")
    print("\n   RECOMMENDATION: Keep investigating or try different approach")

# Win rate comparison
old_win_rate = (old_top_df['forward_return_30d'] > df_test['forward_return_30d'].median()).sum() / len(old_top_df) * 100
new_win_rate = (new_top_df['forward_return_30d'] > df_test['forward_return_30d'].median()).sum() / len(new_top_df) * 100

print(f"\n📊 WIN RATE (Top-10 beats median):")
print(f"   OLD: {old_win_rate:.0f}%")
print(f"   NEW: {new_win_rate:.0f}%")

print("\n" + "=" * 100)
