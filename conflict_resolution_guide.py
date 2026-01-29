"""
Conflict Resolution Guide - How to handle stocks with BOTH pre-breakout AND exhaustion signals
"""
import pandas as pd
import os

# Get latest report
reports = [f for f in os.listdir('reports') if f.startswith('Enhanced_Stock_Report') and f.endswith('.xlsx')]
latest = max([os.path.join('reports', f) for f in reports], key=os.path.getmtime)
df = pd.read_excel(latest, sheet_name='Portfolio Allocation')

print("🔍 CONFLICT RESOLUTION GUIDE")
print("="*80)
print("\nDECISION MATRIX:")
print("   Exit Score ≥60: SKIP (exhaustion takes priority)")
print("   Exit Score 45-59 + Breakout ≥85%: SMALL POSITION (20-30% size)")
print("   Exit Score <45 + Breakout ≥70%: CAN ENTER (50-70% size)")
print("="*80)

conflicts = df[(df['PRE_BREAKOUT?'] == True) & (df['EXHAUSTION?'] == True)]

for _, row in conflicts.iterrows():
    symbol = row['symbol']
    bp = row['BREAKOUT_%']
    es = row['EXIT_SCORE']
    
    print(f"\n📊 {symbol}:")
    print(f"   Breakout Probability: {bp:.0f}%")
    print(f"   Exit Score: {es:.0f}")
    print(f"   Setup Signals: {row['SETUP_SIGNALS'][:60]}...")
    print(f"   Exit Signals: {row['EXIT_SIGNALS'][:60]}...")
    
    # Decision logic
    if es >= 60:
        decision = "🔴 SKIP"
        reason = f"Exit score too high ({es:.0f}) - Momentum exhausted, reversal risk high"
        strategy = "Do NOT enter. Wait for exhaustion to clear."
    elif es >= 45 and bp >= 85:
        decision = "🟡 CAUTIOUS ENTRY"
        reason = f"Strong setup ({bp:.0f}%) but moderate exhaustion ({es:.0f})"
        strategy = "Enter 20-30% position size. Tight stop loss (-3%). Exit if RSI >75."
    elif es < 45 and bp >= 70:
        decision = "🟢 CAN ENTER"
        reason = f"Setup strong ({bp:.0f}%), exhaustion manageable ({es:.0f})"
        strategy = "Enter 50-70% position. Normal stop loss at support. Monitor RSI."
    else:
        decision = "⚪ SKIP"
        reason = "Risk/reward unfavorable"
        strategy = "Wait for better setup."
    
    print(f"\n   DECISION: {decision}")
    print(f"   Reason: {reason}")
    print(f"   Strategy: {strategy}")
    print("-"*80)

# Show Excel location
print("\n📋 WHERE TO FIND THIS IN EXCEL:")
print("="*80)
print(f"File: {os.path.basename(latest)}")
print("Sheet: Portfolio Allocation")
print("\nRelevant Columns (left to right):")
print("   Column | Field Name         | What It Shows")
print("   -------+-------------------+----------------------------------------")
print("   1      | symbol             | Stock ticker (e.g., BANKINDIA)")
print("   2      | company_name       | Full company name")
print("   ...    | ...                | (other columns)")
print("   36     | PRE_BREAKOUT?      | TRUE/FALSE - Is setup detected?")
print("   37     | BREAKOUT_%         | 0-100 - Probability of breakout")
print("   38     | SETUP_SIGNALS      | Text - Why it's a setup")
print("   39     | EXHAUSTION?        | TRUE/FALSE - Is exhausted?")
print("   40     | EXIT_SCORE         | 0-100 - How exhausted?")
print("   41     | EXIT_SIGNALS       | Text - Why to exit")

print("\n💡 QUICK FILTER IN EXCEL:")
print("   1. Open Portfolio Allocation sheet")
print("   2. Click on column headers to enable AutoFilter")
print("   3. Filter PRE_BREAKOUT? = TRUE")
print("   4. Filter EXHAUSTION? = FALSE")
print("   5. Sort by BREAKOUT_% (highest first)")
print("   → This shows your BUY NOW opportunities!")

print("\n🔴 TO FIND EXIT OPPORTUNITIES:")
print("   1. Filter EXHAUSTION? = TRUE")
print("   2. Filter EXIT_SCORE >= 70")
print("   3. Sort by EXIT_SCORE (highest first)")
print("   → These need IMMEDIATE exit!")

print("\n⚠️ TO FIND CONFLICTS:")
print("   1. Filter PRE_BREAKOUT? = TRUE")
print("   2. Filter EXHAUSTION? = TRUE")
print("   → These need manual review (use decision matrix above)")
print("="*80)
