"""
Test improved pre-breakout detector with stricter criteria
Expected: ~30-40% detection rate (not 96%)
"""
import pandas as pd
import os

# Quick check on latest report
reports = [f for f in os.listdir('reports') if f.startswith('Enhanced_Stock_Report') and f.endswith('.xlsx')]
if not reports:
    print("❌ No reports found")
    exit()

latest_report = max([os.path.join('reports', f) for f in reports], key=os.path.getmtime)
print(f"📊 Analyzing: {os.path.basename(latest_report)}\n")

# Read Portfolio Allocation sheet
df = pd.read_excel(latest_report, sheet_name='Portfolio Allocation')
print(f"Total stocks: {len(df)}")

# Check detection rates with IMPROVED version
pre_breakout_stocks = df[df['PRE_BREAKOUT?'] == True]
high_prob_stocks = df[df['BREAKOUT_%'] >= 70]
very_high_prob = df[df['BREAKOUT_%'] >= 80]

print(f"\n🔍 IMPROVED DETECTION RATES:")
print(f"   Pre-breakout detected: {len(pre_breakout_stocks)}/{len(df)} ({len(pre_breakout_stocks)/len(df)*100:.1f}%)")
print(f"   High probability (≥70%): {len(high_prob_stocks)}")
print(f"   Very high (≥80%): {len(very_high_prob)}")

# Should now be 30-40%, not 96%
if len(pre_breakout_stocks) / len(df) > 0.5:
    print(f"\n⚠️ WARNING: Still too many detections ({len(pre_breakout_stocks)/len(df)*100:.1f}%)")
    print("   Expected: 30-40% for quality setups")
elif len(pre_breakout_stocks) / len(df) < 0.2:
    print(f"\n⚠️ WARNING: Too few detections ({len(pre_breakout_stocks)/len(df)*100:.1f}%)")
    print("   Expected: 30-40% for quality setups")
else:
    print(f"\n✅ OPTIMAL: {len(pre_breakout_stocks)/len(df)*100:.1f}% detection rate (good selectivity)")

# Show top 5 setups with all factors
if len(high_prob_stocks) > 0:
    print(f"\n🎯 TOP SETUPS (High Confidence):")
    for idx, row in high_prob_stocks.sort_values('BREAKOUT_%', ascending=False).head(5).iterrows():
        symbol = row.get('symbol', row.get('SYMBOL', 'UNKNOWN'))
        print(f"\n   {symbol}: {row['BREAKOUT_%']:.0f}% probability")
        print(f"      Score: {row.get('risk_adjusted_score', row.get('RISK_ADJUSTED_SCORE', 'N/A'))}")
        print(f"      Signals: {row['SETUP_SIGNALS']}")
        if row.get('EXHAUSTION?'):
            print(f"      ⚠️ EXHAUSTED ({row['EXIT_SCORE']}) - SKIP THIS!")
else:
    print("\n⚪ No high-probability setups found (strict criteria)")

# Show what got filtered out
filtered_out = df[df['PRE_BREAKOUT?'] == False]
print(f"\n📊 FILTERED OUT: {len(filtered_out)} stocks didn't meet criteria")
print(f"   (Reasons: Low score, not near resistance, no volume, not consolidating, etc.)")
