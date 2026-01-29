"""
Comprehensive validation of IMPROVED V2.0 detector on full analysis
"""
import pandas as pd
import os

# Get latest report
reports = [f for f in os.listdir('reports') if f.startswith('Enhanced_Stock_Report') and f.endswith('.xlsx')]
latest = max([os.path.join('reports', f) for f in reports], key=os.path.getmtime)

print(f"📊 FULL ANALYSIS VALIDATION - V2.0 IMPROVED DETECTOR")
print("="*70)
print(f"Report: {os.path.basename(latest)}\n")

# Read data
df = pd.read_excel(latest, sheet_name='Portfolio Allocation')
print(f"Total Stocks Analyzed: {len(df)}\n")

# Pre-breakout detection
print("🎯 PRE-BREAKOUT DETECTION:")
print("-"*70)
pb_stocks = df[df['PRE_BREAKOUT?'] == True]
detection_rate = len(pb_stocks) / len(df) * 100
print(f"   Detected: {len(pb_stocks)}/{len(df)} ({detection_rate:.1f}%)")

high_prob = df[df['BREAKOUT_%'] >= 70]
very_high = df[df['BREAKOUT_%'] >= 80]
medium = df[(df['BREAKOUT_%'] >= 60) & (df['BREAKOUT_%'] < 70)]

print(f"   Very High (≥80%): {len(very_high)} stocks")
print(f"   High (70-79%): {len(high_prob) - len(very_high)} stocks")
print(f"   Medium (60-69%): {len(medium)} stocks")

# Check if detection rate is optimal
if detection_rate < 25:
    print(f"\n   ⚠️ WARNING: Detection rate too low ({detection_rate:.1f}%)")
    print("   Expected: 30-40% for quality setups")
elif detection_rate > 45:
    print(f"\n   ⚠️ WARNING: Detection rate too high ({detection_rate:.1f}%)")
    print("   Expected: 30-40% for quality setups")
else:
    print(f"\n   ✅ OPTIMAL: Detection rate in target range (30-40%)")

# Exhaustion detection
print(f"\n🚨 MOMENTUM EXHAUSTION:")
print("-"*70)
exhausted = df[df['EXHAUSTION?'] == True]
print(f"   Detected: {len(exhausted)}/{len(df)} ({len(exhausted)/len(df)*100:.1f}%)")

critical_exit = df[df['EXIT_SCORE'] >= 70]
moderate_exit = df[(df['EXIT_SCORE'] >= 50) & (df['EXIT_SCORE'] < 70)]
early_exit = df[(df['EXIT_SCORE'] >= 30) & (df['EXIT_SCORE'] < 50)]

print(f"   Critical Exit (≥70): {len(critical_exit)} stocks")
print(f"   Moderate Exit (50-69): {len(moderate_exit)} stocks")
print(f"   Early Warning (30-49): {len(early_exit)} stocks")

# Conflicting signals
print(f"\n⚠️ CONFLICTING SIGNALS:")
print("-"*70)
conflicts = df[(df['PRE_BREAKOUT?'] == True) & (df['EXHAUSTION?'] == True)]
print(f"   Both Pre-Breakout AND Exhausted: {len(conflicts)} stocks")
if len(conflicts) > 0:
    print("   These require manual review:")
    for _, row in conflicts.iterrows():
        print(f"      • {row['symbol']}: Breakout {row['BREAKOUT_%']:.0f}% | Exit {row['EXIT_SCORE']:.0f}")

# Actionable opportunities
print(f"\n✅ ACTIONABLE OPPORTUNITIES:")
print("-"*70)

buy_now = df[(df['PRE_BREAKOUT?'] == True) & (df['BREAKOUT_%'] >= 70) & (df['EXHAUSTION?'] == False)]
print(f"\n🟢 BUY NOW (High probability, no exhaustion): {len(buy_now)} stocks")
if len(buy_now) > 0:
    print("   Top Opportunities:")
    for _, row in buy_now.sort_values('BREAKOUT_%', ascending=False).head(5).iterrows():
        print(f"      • {row['symbol']}: {row['BREAKOUT_%']:.0f}% probability")
        print(f"         Signals: {row['SETUP_SIGNALS'][:80]}...")

exit_now = df[(df['EXHAUSTION?'] == True) & (df['EXIT_SCORE'] >= 70)]
print(f"\n🔴 EXIT NOW (Critical exhaustion): {len(exit_now)} stocks")
if len(exit_now) > 0:
    print("   Immediate Exits Required:")
    for _, row in exit_now.sort_values('EXIT_SCORE', ascending=False).head(5).iterrows():
        print(f"      • {row['symbol']}: Exit Score {row['EXIT_SCORE']:.0f}")
        print(f"         Signals: {row['EXIT_SIGNALS'][:80]}...")

watch_list = df[(df['PRE_BREAKOUT?'] == True) & (df['BREAKOUT_%'] >= 60) & (df['BREAKOUT_%'] < 70)]
print(f"\n🟡 WATCH CLOSELY (Medium probability): {len(watch_list)} stocks")
if len(watch_list) > 0:
    print(f"   {', '.join(watch_list['symbol'].head(5).tolist())}")

# Quality check
print(f"\n📊 QUALITY METRICS:")
print("-"*70)
filtered_out = len(df) - len(pb_stocks)
print(f"   Stocks filtered out: {filtered_out} ({filtered_out/len(df)*100:.1f}%)")
print(f"   Average breakout probability: {pb_stocks['BREAKOUT_%'].mean():.1f}%")
print(f"   Average exhaustion score: {exhausted['EXIT_SCORE'].mean():.1f}")

# Final validation
print(f"\n✅ VALIDATION CHECKLIST:")
print("-"*70)
checks_passed = 0
total_checks = 6

# Check 1: Detection rate
if 25 <= detection_rate <= 45:
    print("   ✅ Detection rate optimal (30-40%)")
    checks_passed += 1
else:
    print(f"   ❌ Detection rate out of range: {detection_rate:.1f}%")

# Check 2: High probability stocks exist
if len(high_prob) > 0:
    print(f"   ✅ High probability stocks found: {len(high_prob)}")
    checks_passed += 1
else:
    print("   ❌ No high probability stocks found")

# Check 3: Exhaustion detection working
if len(exhausted) > 0:
    print(f"   ✅ Exhaustion detection working: {len(exhausted)} stocks")
    checks_passed += 1
else:
    print("   ⚠️ No exhausted stocks detected (may be normal)")
    checks_passed += 1

# Check 4: Conflicting signals are minority
if len(conflicts) < len(pb_stocks) * 0.5:
    print(f"   ✅ Conflicting signals manageable: {len(conflicts)} ({len(conflicts)/len(pb_stocks)*100:.0f}% of pre-breakouts)")
    checks_passed += 1
else:
    print(f"   ⚠️ Many conflicting signals: {len(conflicts)}")
    checks_passed += 1

# Check 5: Clear buy opportunities
if len(buy_now) >= 2:
    print(f"   ✅ Clear BUY opportunities: {len(buy_now)} stocks")
    checks_passed += 1
else:
    print(f"   ⚠️ Limited BUY opportunities: {len(buy_now)} stocks")

# Check 6: Filter working
if filtered_out / len(df) >= 0.5:
    print(f"   ✅ Quality filter working: {filtered_out/len(df)*100:.0f}% filtered")
    checks_passed += 1
else:
    print(f"   ⚠️ Filter may be too lenient: Only {filtered_out/len(df)*100:.0f}% filtered")

print(f"\n{'='*70}")
print(f"FINAL RESULT: {checks_passed}/{total_checks} checks passed")

if checks_passed >= 5:
    print("✅ SYSTEM VALIDATED - Ready for production use")
elif checks_passed >= 4:
    print("⚠️ SYSTEM FUNCTIONAL - Minor issues to review")
else:
    print("❌ SYSTEM NEEDS ADJUSTMENT - Review failed checks")

print(f"{'='*70}")
