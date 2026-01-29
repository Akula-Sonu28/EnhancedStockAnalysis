"""
Visual Excel Navigation Guide - Find BUY/EXIT opportunities quickly
"""
import pandas as pd
import os

reports = [f for f in os.listdir('reports') if f.startswith('Enhanced_Stock_Report') and f.endswith('.xlsx')]
latest = max([os.path.join('reports', f) for f in reports], key=os.path.getmtime)
df = pd.read_excel(latest, sheet_name='Portfolio Allocation')

print("📊 EXCEL QUICK REFERENCE GUIDE")
print("="*80)
print(f"FILE: {os.path.basename(latest)}")
print(f"SHEET: Portfolio Allocation")
print(f"TOTAL ROWS: {len(df)} stocks\n")

# Show sample row with pre-breakout data
print("📋 COLUMN LAYOUT (Key columns you need):")
print("-"*80)
# Find a row with pre-breakout setup
sample_with_setup = df[df['PRE_BREAKOUT?'] == True].iloc[0] if len(df[df['PRE_BREAKOUT?'] == True]) > 0 else df.iloc[0]
print(f"Example stock: {sample_with_setup['symbol']}")
print(f"...")
print(f"PRE_BREAKOUT? column = {sample_with_setup['PRE_BREAKOUT?']}")
print(f"BREAKOUT_%           = {sample_with_setup['BREAKOUT_%']:.0f}%")
if isinstance(sample_with_setup['SETUP_SIGNALS'], str):
    print(f"SETUP_SIGNALS        = {sample_with_setup['SETUP_SIGNALS'][:60]}...")
else:
    print(f"SETUP_SIGNALS        = (no setup detected)")
print(f"EXHAUSTION?          = {sample_with_setup['EXHAUSTION?']}")
print(f"EXIT_SCORE           = {sample_with_setup['EXIT_SCORE']:.0f}")
if isinstance(sample_with_setup['EXIT_SIGNALS'], str):
    print(f"EXIT_SIGNALS         = {sample_with_setup['EXIT_SIGNALS'][:60]}...")
else:
    print(f"EXIT_SIGNALS         = (no exhaustion)")
print(f"\n💡 These 6 columns are at the RIGHT END of the Portfolio Allocation sheet")

# Show all opportunities in table format
print("\n\n🎯 YOUR OPPORTUNITIES (Pre-filtered for you):")
print("="*80)

# BUY NOW
buy_now = df[(df['PRE_BREAKOUT?'] == True) & (df['BREAKOUT_%'] >= 70) & (df['EXHAUSTION?'] == False)]
print(f"\n🟢 BUY NOW ({len(buy_now)} stocks) - High probability, no exhaustion:")
print("-"*80)
if len(buy_now) > 0:
    print(f"{'SYMBOL':<12} {'PROB':<8} {'KEY SIGNAL'}")
    print("-"*80)
    for _, row in buy_now.sort_values('BREAKOUT_%', ascending=False).iterrows():
        prob = f"{row['BREAKOUT_%']:.0f}%"
        signal = row['SETUP_SIGNALS'].split('|')[0].strip()  # First signal
        print(f"{row['symbol']:<12} {prob:<8} {signal[:50]}")
else:
    print("   No clear BUY opportunities at this time")

# EXIT NOW
exit_now = df[(df['EXHAUSTION?'] == True) & (df['EXIT_SCORE'] >= 70)]
print(f"\n🔴 EXIT NOW ({len(exit_now)} stocks) - Critical exhaustion:")
print("-"*80)
if len(exit_now) > 0:
    print(f"{'SYMBOL':<12} {'EXIT':<8} {'KEY SIGNAL'}")
    print("-"*80)
    for _, row in exit_now.sort_values('EXIT_SCORE', ascending=False).iterrows():
        exit_sc = f"{row['EXIT_SCORE']:.0f}"
        signal = row['EXIT_SIGNALS'].split('|')[0].strip()
        print(f"{row['symbol']:<12} {exit_sc:<8} {signal[:50]}")
else:
    print("   No critical exits needed")

# CONFLICTS
conflicts = df[(df['PRE_BREAKOUT?'] == True) & (df['EXHAUSTION?'] == True)]
print(f"\n⚠️ MANUAL REVIEW ({len(conflicts)} stocks) - Conflicting signals:")
print("-"*80)
if len(conflicts) > 0:
    print(f"{'SYMBOL':<12} {'PROB':<6} {'EXIT':<6} {'DECISION':<20} {'ACTION'}")
    print("-"*80)
    for _, row in conflicts.iterrows():
        prob = f"{row['BREAKOUT_%']:.0f}%"
        exit_sc = f"{row['EXIT_SCORE']:.0f}"
        
        # Decision logic
        if row['EXIT_SCORE'] >= 60:
            decision = "SKIP"
            action = "Too exhausted"
        elif row['EXIT_SCORE'] >= 45 and row['BREAKOUT_%'] >= 85:
            decision = "SMALL (20-30%)"
            action = "Tight stop -3%"
        elif row['EXIT_SCORE'] < 45 and row['BREAKOUT_%'] >= 70:
            decision = "ENTER (50-70%)"
            action = "Monitor RSI"
        else:
            decision = "SKIP"
            action = "Wait for clarity"
        
        print(f"{row['symbol']:<12} {prob:<6} {exit_sc:<6} {decision:<20} {action}")

# WATCH LIST
watch = df[(df['PRE_BREAKOUT?'] == True) & (df['BREAKOUT_%'] >= 60) & (df['BREAKOUT_%'] < 70) & (df['EXHAUSTION?'] == False)]
print(f"\n🟡 WATCH LIST ({len(watch)} stocks) - Medium probability:")
print("-"*80)
if len(watch) > 0:
    print(f"{'SYMBOL':<12} {'PROB':<8} {'STATUS'}")
    print("-"*80)
    for _, row in watch.iterrows():
        prob = f"{row['BREAKOUT_%']:.0f}%"
        status = "Wait for >70% or more signals"
        print(f"{row['symbol']:<12} {prob:<8} {status}")
else:
    print("   No stocks in watch list")

print("\n\n" + "="*80)
print("💡 EXCEL SHORTCUTS:")
print("="*80)
print("1. Ctrl+Shift+L = Enable AutoFilter (on any column header)")
print("2. Click dropdown arrow on PRE_BREAKOUT? column")
print("3. Select only 'TRUE' checkbox")
print("4. Click dropdown on EXHAUSTION? column")
print("5. Select only 'FALSE' checkbox")
print("6. Click dropdown on BREAKOUT_% column")
print("7. Sort 'Largest to Smallest'")
print("→ Now you see BUY opportunities sorted by probability!")
print("="*80)
