"""
Find and verify ACTION column in latest report
"""
import pandas as pd
import os

# Get latest report
reports = [f for f in os.listdir('reports') if f.startswith('Enhanced_Stock_Report') and f.endswith('.xlsx')]
latest = max([os.path.join('reports', f) for f in reports], key=os.path.getmtime)

print("📊 FINDING ACTION COLUMN")
print("="*80)
print(f"File: {os.path.basename(latest)}\n")

# Read data
df = pd.read_excel(latest, sheet_name='Portfolio Allocation')

# Find action-related columns
action_cols = [c for c in df.columns if 'action' in c.lower() or 'recommend' in c.lower() or 'priority' in c.lower()]

print(f"Action/Recommendation related columns found: {len(action_cols)}")
for col in action_cols:
    print(f"   - {col}")

# Check conflict stocks
conflicts = df[(df['PRE_BREAKOUT?'] == True) & (df['EXHAUSTION?'] == True)]

if len(conflicts) > 0:
    print(f"\n🔍 CONFLICT STOCK EXAMPLE: {conflicts.iloc[0]['symbol']}")
    print("-"*80)
    for col in action_cols:
        value = conflicts.iloc[0][col]
        print(f"   {col:<30} = {value}")
    
    print(f"\n\n📋 ALL {len(conflicts)} CONFLICT STOCKS:")
    print("="*80)
    
    for _, row in conflicts.iterrows():
        symbol = row['symbol']
        bp = row['BREAKOUT_%']
        es = row['EXIT_SCORE']
        
        print(f"\n{symbol}: Breakout {bp:.0f}% | Exit {es:.0f}")
        
        for col in action_cols:
            val = row[col]
            if pd.notna(val) and str(val) != 'nan' and val != '':
                print(f"   {col}: {val}")
        
        # Check expected
        if es >= 60:
            expected = f"SKIP - EXHAUSTED"
        elif es >= 45 and bp >= 85:
            expected = "SMALL ENTRY (20-30%)"
        elif es < 45 and bp >= 70:
            expected = "ENTER (50-70%)"
        else:
            expected = "SKIP - WAIT"
        
        # Check if any column has the expected text
        found = False
        for col in action_cols:
            val = str(row[col])
            if any(keyword in val for keyword in ["SKIP", "SMALL", "ENTER", "EXHAUSTED", "20-30", "50-70"]):
                found = True
                print(f"   ✅ CONFLICT RESOLUTION DETECTED in {col}")
                break
        
        if not found:
            print(f"   ❌ Expected: {expected} - NOT FOUND")
        
        print("-"*80)

print("\n\n💡 DIAGNOSIS:")
print("="*80)
if len(action_cols) == 0:
    print("❌ No action columns found! Check column names in Excel.")
else:
    print(f"✅ Found {len(action_cols)} action-related columns")
    print(f"   Check if values are populated above")
