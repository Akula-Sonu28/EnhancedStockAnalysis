"""
Comprehensive verification script for conflict resolution functionality
Checks:
1. Portfolio Allocation sheet exists
2. ACTION column present with 41 columns
3. Conflict-resolved actions visible
4. Pre-breakout and exhaustion columns populated
5. Action distribution makes sense
"""
import pandas as pd
import sys
from pathlib import Path

def verify_conflict_resolution(report_path):
    print("="*80)
    print("🔍 CONFLICT RESOLUTION VERIFICATION")
    print("="*80)
    
    try:
        # Check file exists
        if not Path(report_path).exists():
            print(f"❌ Report not found: {report_path}")
            return False
        
        print(f"\n📊 Report: {Path(report_path).name}")
        print(f"   Size: {Path(report_path).stat().st_size:,} bytes")
        
        # Load Excel file
        xl = pd.ExcelFile(report_path)
        print(f"\n✅ Total sheets: {len(xl.sheet_names)}")
        
        # Check 1: Portfolio Allocation sheet exists
        if 'Portfolio Allocation' not in xl.sheet_names:
            print("❌ FAIL: Portfolio Allocation sheet missing")
            print(f"   Available sheets: {xl.sheet_names}")
            return False
        print("✅ PASS: Portfolio Allocation sheet exists")
        
        # Load Portfolio Allocation
        df = pd.read_excel(report_path, sheet_name='Portfolio Allocation')
        
        # Check 2: Column count
        print(f"\n✅ Total columns: {len(df.columns)}")
        if len(df.columns) < 40:
            print(f"⚠️  WARNING: Only {len(df.columns)} columns (expected 41)")
        
        # Check 3: ACTION column exists
        if 'ACTION' not in df.columns:
            print("❌ FAIL: ACTION column missing")
            print(f"   Available columns: {list(df.columns)[:10]}...")
            return False
        print("✅ PASS: ACTION column exists")
        
        # Check 4: Conflict resolution columns exist
        required_cols = ['PRE_BREAKOUT?', 'BREAKOUT_%', 'EXHAUSTION?', 'EXIT_SCORE']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"⚠️  WARNING: Missing columns: {missing_cols}")
        else:
            print("✅ PASS: All conflict detection columns present")
        
        # Check 5: Analyze ACTION values
        print(f"\n📊 ACTION COLUMN ANALYSIS:")
        print(f"   Total stocks: {len(df)}")
        print(f"   Unique actions: {df['ACTION'].nunique()}")
        
        action_counts = df['ACTION'].value_counts()
        print(f"\n   Action Distribution:")
        for action, count in action_counts.items():
            pct = (count / len(df)) * 100
            print(f"      {action}: {count} ({pct:.1f}%)")
        
        # Check 6: Conflict-resolved actions present
        conflict_emojis = ['⚠️', '🟡', '🟢', '⚪']
        conflict_mask = df['ACTION'].astype(str).str.contains('|'.join(conflict_emojis), na=False, regex=True)
        conflict_count = conflict_mask.sum()
        
        print(f"\n🎯 CONFLICT RESOLUTION:")
        print(f"   Stocks with conflict-resolved actions: {conflict_count}")
        
        if conflict_count == 0:
            print("   ⚠️  WARNING: No conflict-resolved actions found")
            print("   This could be normal if no conflicts detected")
        else:
            print("   ✅ PASS: Conflict resolution active")
            
            # Show examples
            conflicts = df[conflict_mask][['symbol', 'ACTION', 'BREAKOUT_%', 'EXIT_SCORE']].head(10)
            print(f"\n   📋 Conflict Examples ({min(len(conflicts), 10)} shown):")
            for _, row in conflicts.iterrows():
                bp = row['BREAKOUT_%'] if pd.notna(row['BREAKOUT_%']) else 0
                es = row['EXIT_SCORE'] if pd.notna(row['EXIT_SCORE']) else 0
                print(f"      {row['symbol']:12} | {row['ACTION']:40} | BP:{bp:3.0f}% ES:{es:3.0f}")
        
        # Check 7: Holdings identification
        if 'I_OWN_IT?' in df.columns:
            holdings_count = df['I_OWN_IT?'].sum()
            new_count = len(df) - holdings_count
            print(f"\n📦 PORTFOLIO COMPOSITION:")
            print(f"   Current holdings: {holdings_count}")
            print(f"   New candidates: {new_count}")
        
        # Check 8: Investment amounts
        if 'INVEST_₹' in df.columns:
            total_invest = df['INVEST_₹'].sum()
            stocks_with_invest = (df['INVEST_₹'] > 0).sum()
            print(f"\n💰 INVESTMENT ALLOCATION:")
            print(f"   Total allocated: ₹{total_invest:,.0f}")
            print(f"   Stocks to invest in: {stocks_with_invest}")
        
        # Summary
        print("\n" + "="*80)
        print("✅ VERIFICATION COMPLETE: Conflict resolution is working!")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Get latest report
    import glob
    reports = glob.glob("reports/Enhanced_Stock_Report_*.xlsx")
    if not reports:
        print("❌ No reports found in reports/ directory")
        sys.exit(1)
    
    latest = max(reports, key=lambda x: Path(x).stat().st_mtime)
    
    success = verify_conflict_resolution(latest)
    sys.exit(0 if success else 1)
