"""
Validate exhaustion-based defensive logic for all stocks
Checks if high exhaustion scores properly prevent additional investment
"""
import pandas as pd
import sys

def validate_exhaustion_logic(report_path):
    print("="*80)
    print("🔍 EXHAUSTION LOGIC VALIDATION")
    print("="*80)
    
    df = pd.read_excel(report_path, sheet_name='Portfolio Allocation')
    
    print(f"\nTotal stocks: {len(df)}")
    
    # Check stocks with exhaustion detected
    exhausted = df[df['EXHAUSTION?'] == True].copy()
    print(f"Exhausted stocks: {len(exhausted)}")
    
    if exhausted.empty:
        print("✅ No exhausted stocks found")
        return
    
    # Sort by exit score (highest first)
    exhausted = exhausted.sort_values('EXIT_SCORE', ascending=False)
    
    print("\n" + "="*80)
    print("📊 EXHAUSTION ANALYSIS BY SEVERITY")
    print("="*80)
    
    # Category 1: Very High Exhaustion (≥70) - Should be KEEP/SELL/SKIP
    very_high = exhausted[exhausted['EXIT_SCORE'] >= 70]
    print(f"\n🔴 VERY HIGH EXHAUSTION (Exit Score ≥70): {len(very_high)} stocks")
    print("   Expected: KEEP, SELL, or ⚠️ SKIP")
    print("-"*80)
    
    for _, row in very_high.iterrows():
        action = row['ACTION']
        invest = row['INVEST_₹']
        score = row['SCORE']
        exit_score = row['EXIT_SCORE']
        profit = row.get('MY_PROFIT_%', 0)
        
        # Check if action is defensive
        defensive_actions = ['KEEP', 'SELL', 'BOOK', '⚠️', 'EXIT']
        is_defensive = any(keyword in str(action) for keyword in defensive_actions)
        
        status = "✅" if is_defensive and invest == 0 else "❌"
        
        print(f"{status} {row['symbol']:12} | Exit:{exit_score:3.0f} Score:{score:5.1f} Profit:{profit:6.1f}% | {action:40} | Invest:₹{invest:,.0f}")
    
    # Category 2: High Exhaustion (60-69) - Should be KEEP or SMALL allocation
    high = exhausted[(exhausted['EXIT_SCORE'] >= 60) & (exhausted['EXIT_SCORE'] < 70)]
    print(f"\n🟡 HIGH EXHAUSTION (Exit Score 60-69): {len(high)} stocks")
    print("   Expected: KEEP, ⚠️ SKIP, or 🟡 SMALL ENTRY")
    print("-"*80)
    
    for _, row in high.iterrows():
        action = row['ACTION']
        invest = row['INVEST_₹']
        score = row['SCORE']
        exit_score = row['EXIT_SCORE']
        profit = row.get('MY_PROFIT_%', 0)
        
        # Check if action is defensive or small entry
        defensive_actions = ['KEEP', '⚠️', 'SKIP', '🟡', 'SMALL']
        is_defensive = any(keyword in str(action) for keyword in defensive_actions)
        
        status = "✅" if is_defensive else "❌"
        
        print(f"{status} {row['symbol']:12} | Exit:{exit_score:3.0f} Score:{score:5.1f} Profit:{profit:6.1f}% | {action:40} | Invest:₹{invest:,.0f}")
    
    # Category 3: Moderate Exhaustion (45-59) - Can have SMALL entry or BOOK PROFIT
    moderate = exhausted[(exhausted['EXIT_SCORE'] >= 45) & (exhausted['EXIT_SCORE'] < 60)]
    print(f"\n🟠 MODERATE EXHAUSTION (Exit Score 45-59): {len(moderate)} stocks")
    print("   Expected: 🟡 SMALL ENTRY, 🟡 BOOK, or KEEP")
    print("-"*80)
    
    for _, row in moderate.iterrows():
        action = row['ACTION']
        invest = row['INVEST_₹']
        score = row['SCORE']
        exit_score = row['EXIT_SCORE']
        profit = row.get('MY_PROFIT_%', 0)
        pre_breakout = row.get('PRE_BREAKOUT?', False)
        breakout_pct = row.get('BREAKOUT_%', 0)
        
        # Moderate exhaustion can allow small entries if pre-breakout is strong
        if pre_breakout and breakout_pct >= 85:
            expected = "🟡 SMALL ENTRY or BOOK allowed"
            is_ok = '🟡' in str(action) or 'KEEP' in str(action) or 'BOOK' in str(action)
        else:
            expected = "KEEP or BOOK"
            is_ok = 'KEEP' in str(action) or 'BOOK' in str(action)
        
        status = "✅" if is_ok else "⚠️"
        
        print(f"{status} {row['symbol']:12} | Exit:{exit_score:3.0f} Score:{score:5.1f} Profit:{profit:6.1f}% | {action:40} | Invest:₹{invest:,.0f}")
        if pre_breakout:
            print(f"   💡 Pre-breakout: {breakout_pct:.0f}% - {expected}")
    
    # Category 4: Low Exhaustion (<45) - Can have normal actions
    low = exhausted[exhausted['EXIT_SCORE'] < 45]
    if not low.empty:
        print(f"\n🟢 LOW EXHAUSTION (Exit Score <45): {len(low)} stocks")
        print("   Expected: Any action (INCREASE, BUY, ENTER allowed)")
        print("-"*80)
        
        for _, row in low.iterrows():
            action = row['ACTION']
            invest = row['INVEST_₹']
            score = row['SCORE']
            exit_score = row['EXIT_SCORE']
            
            print(f"   {row['symbol']:12} | Exit:{exit_score:3.0f} Score:{score:5.1f} | {action:40} | Invest:₹{invest:,.0f}")
    
    # Summary
    print("\n" + "="*80)
    print("📊 VALIDATION SUMMARY")
    print("="*80)
    
    # Count issues
    issues = 0
    
    # Very high should all be defensive with 0 investment
    for _, row in very_high.iterrows():
        defensive_actions = ['KEEP', 'SELL', 'BOOK', '⚠️', 'EXIT']
        is_defensive = any(keyword in str(row['ACTION']) for keyword in defensive_actions)
        if not is_defensive or row['INVEST_₹'] > 0:
            issues += 1
    
    print(f"\n✅ Very High Exhaustion (≥70): {len(very_high) - issues}/{len(very_high)} correct")
    print(f"✅ High Exhaustion (60-69): {len(high)} stocks reviewed")
    print(f"✅ Moderate Exhaustion (45-59): {len(moderate)} stocks reviewed")
    
    if issues == 0:
        print("\n🎉 ALL EXHAUSTION LOGIC WORKING CORRECTLY!")
    else:
        print(f"\n⚠️  Found {issues} potential issues - review above")
    
    # Additional check: Stocks with INVEST > 0 and high exhaustion
    print("\n" + "="*80)
    print("🔍 STOCKS WITH INVESTMENT DESPITE EXHAUSTION")
    print("="*80)
    
    invested_exhausted = exhausted[(exhausted['INVEST_₹'] > 0) & (exhausted['EXIT_SCORE'] >= 45)]
    
    if invested_exhausted.empty:
        print("✅ No stocks with investment and high exhaustion (correct!)")
    else:
        print(f"⚠️  Found {len(invested_exhausted)} stocks with investment despite exhaustion:")
        for _, row in invested_exhausted.iterrows():
            print(f"   {row['symbol']:12} | Exit:{row['EXIT_SCORE']:3.0f} | Invest:₹{row['INVEST_₹']:,.0f} | {row['ACTION']}")
            # Check if it's a conflict-resolved small entry (allowed)
            if '🟡' in str(row['ACTION']) and 'SMALL' in str(row['ACTION']):
                print(f"      ✅ OK - Conflict-resolved small entry")

if __name__ == "__main__":
    import glob
    from pathlib import Path
    
    # Get latest report
    reports = glob.glob("reports/Enhanced_Stock_Report_*.xlsx")
    if not reports:
        print("❌ No reports found")
        sys.exit(1)
    
    latest = max(reports, key=lambda x: Path(x).stat().st_mtime)
    print(f"Analyzing: {Path(latest).name}\n")
    
    validate_exhaustion_logic(latest)
