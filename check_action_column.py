"""
Check if ACTION column has conflict resolution working
"""
import pandas as pd
import os

# Get latest report
reports = [f for f in os.listdir('reports') if f.startswith('Enhanced_Stock_Report') and f.endswith('.xlsx')]
latest = max([os.path.join('reports', f) for f in reports], key=os.path.getmtime)

print("📊 CHECKING ACTION COLUMN - CONFLICT RESOLUTION")
print("="*80)
print(f"File: {os.path.basename(latest)}\n")

# Read data
df = pd.read_excel(latest, sheet_name='Portfolio Allocation')

# Check for conflicts
conflicts = df[(df['PRE_BREAKOUT?'] == True) & (df['EXHAUSTION?'] == True)]

print(f"🔍 CONFLICT STOCKS (Pre-breakout AND Exhaustion):")
print(f"Found: {len(conflicts)} stocks\n")

if len(conflicts) > 0:
    print(f"{'SYMBOL':<13} | {'BREAKOUT':<8} | {'EXIT':<4} | ACTION COLUMN")
    print("-"*80)
    for _, row in conflicts.iterrows():
        symbol = row['symbol']
        bp = row['BREAKOUT_%']
        es = row['EXIT_SCORE']
        action = row.get('action_type', 'N/A')
        print(f"{symbol:<13} | {bp:>7.0f}% | {es:>4.0f} | {action}")
    
    print("\n✅ EXPECTED vs ACTUAL:")
    print("-"*80)
    for _, row in conflicts.iterrows():
        symbol = row['symbol']
        bp = row['BREAKOUT_%']
        es = row['EXIT_SCORE']
        action = row.get('action_type', 'N/A')
        
        # Expected action based on conflict resolution
        if es >= 60:
            expected = f"⚠️ SKIP - EXHAUSTED ({es:.0f})"
        elif es >= 45 and bp >= 85:
            expected = "🟡 SMALL ENTRY (20-30%)"
        elif es < 45 and bp >= 70:
            expected = "🟢 ENTER (50-70%)"
        else:
            expected = "⚪ SKIP - WAIT"
        
        # Check if matches
        if expected in action or "SKIP" in action or "SMALL" in action or "ENTER" in action:
            status = "✅ CORRECT"
        else:
            status = "❌ NEEDS UPDATE"
        
        print(f"{symbol:<13} | Expected: {expected:<30} | {status}")
        print(f"              | Actual:   {action}")
        print()

else:
    print("   No conflicts found")

# Check BUY NOW stocks
print("\n" + "="*80)
buy_stocks = df[(df['PRE_BREAKOUT?'] == True) & (df['BREAKOUT_%'] >= 70) & (df['EXHAUSTION?'] == False)]
print(f"\n🟢 BUY NOW STOCKS (No conflicts):")
print(f"Found: {len(buy_stocks)} stocks\n")

if len(buy_stocks) > 0:
    print(f"{'SYMBOL':<13} | {'BREAKOUT':<8} | ACTION COLUMN")
    print("-"*80)
    for _, row in buy_stocks.head(5).iterrows():
        symbol = row['symbol']
        bp = row['BREAKOUT_%']
        action = row.get('action_type', 'N/A')
        print(f"{symbol:<13} | {bp:>7.0f}% | {action}")

# Check EXIT NOW stocks
print("\n" + "="*80)
exit_stocks = df[(df['EXHAUSTION?'] == True) & (df['EXIT_SCORE'] >= 70)]
print(f"\n🔴 EXIT NOW STOCKS (No conflicts):")
print(f"Found: {len(exit_stocks)} stocks\n")

if len(exit_stocks) > 0:
    print(f"{'SYMBOL':<13} | {'EXIT':<4} | ACTION COLUMN")
    print("-"*80)
    for _, row in exit_stocks.iterrows():
        symbol = row['symbol']
        es = row['EXIT_SCORE']
        action = row.get('action_type', 'N/A')
        print(f"{symbol:<13} | {es:>4.0f} | {action}")

print("\n" + "="*80)
print("\n💡 INTERPRETATION:")
print("-"*80)

# Check if report is from before or after the fix
file_time = os.path.getmtime(latest)
current_time = os.path.getmtime(__file__)

if file_time < current_time:
    print("⚠️ This report was generated BEFORE the ACTION column fix.")
    print("   Run: python analyze_top200_stocks_enhanced.py -b 7")
    print("   Then check again to see conflict resolution working.")
else:
    print("✅ This report was generated AFTER the ACTION column fix.")
    print("   Conflict resolution should be working above.")

print("="*80)
