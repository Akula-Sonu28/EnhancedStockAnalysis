import pandas as pd

# Check latest report
latest_report = "reports/Enhanced_Stock_Report_20260129_172213.xlsx"

try:
    xl = pd.ExcelFile(latest_report)
    print(f"📊 Report: {latest_report}")
    print(f"\n✅ Sheets found ({len(xl.sheet_names)}):")
    for i, sheet in enumerate(xl.sheet_names, 1):
        print(f"   {i}. {sheet}")
    
    print(f"\n❌ Portfolio Allocation sheet: NOT FOUND")
    print(f"\n🔍 Checking Complete Data sheet for action_recommendation column...")
    
    df = pd.read_excel(latest_report, sheet_name='Complete Data')
    print(f"   Total columns: {len(df.columns)}")
    
    if 'action_recommendation' in df.columns:
        print(f"   ✅ action_recommendation column EXISTS in Complete Data")
        # Check for conflict-resolved values
        conflict_count = df['action_recommendation'].astype(str).str.contains('⚠️|🟡|🟢', na=False, regex=True).sum()
        print(f"   ✅ Conflict-resolved actions: {conflict_count}")
        
        # Show some examples
        conflicts = df[df['action_recommendation'].astype(str).str.contains('⚠️|🟡|🟢', na=False, regex=True)][['symbol', 'action_recommendation']].head(5)
        if not conflicts.empty:
            print(f"\n   📋 Examples:")
            for _, row in conflicts.iterrows():
                print(f"      {row['symbol']}: {row['action_recommendation']}")
    else:
        print(f"   ❌ action_recommendation column NOT FOUND in Complete Data")
        action_cols = [c for c in df.columns if 'action' in c.lower() or 'recommend' in c.lower()]
        if action_cols:
            print(f"   Similar columns: {action_cols}")
    
    print(f"\n💡 DIAGNOSIS:")
    print(f"   The portfolio allocation generation is failing (returning None)")
    print(f"   Check console output or logs for CHECKPOINT and ERROR messages")
    print(f"   Look for: 'ERROR in portfolio allocation' with traceback")

except Exception as e:
    print(f"❌ Error: {e}")
