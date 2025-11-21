import pandas as pd

# Load the latest Excel report
excel_file = r'C:\Users\Sanji\Downloads\New folder\Stock_Analysis\reports\Enhanced_Stock_Report_20251016_171228.xlsx'

print("=" * 80)
print("COMPLETE DATA SHEET - CLASSIFICATION ANALYSIS")
print("=" * 80)

# Load Complete Data sheet
df = pd.read_excel(excel_file, sheet_name='Complete Data')

print(f"\nTotal Stocks Analyzed: {len(df)}")

# Check if stock_classification exists
if 'stock_classification' in df.columns:
    print(f"\n{'=' * 80}")
    print("CLASSIFICATION BREAKDOWN (All 209 Stocks)")
    print("=" * 80)
    
    classification = df['stock_classification'].value_counts()
    total = len(df)
    
    for cat, count in classification.items():
        pct = (count / total) * 100
        print(f"{cat:20s}: {count:3d} stocks ({pct:5.1f}%)")
    
    print(f"\n{'=' * 80}")
    print("STRATEGY TARGET vs ACTUAL")
    print("=" * 80)
    
    target = {
        'CORE_VALUE': 40,
        'CORE_MOMENTUM': 30,
        'OPPORTUNISTIC': 20,
        'SPECULATIVE': 10
    }
    
    for cat in ['CORE_VALUE', 'CORE_MOMENTUM', 'OPPORTUNISTIC', 'SPECULATIVE']:
        actual_count = classification.get(cat, 0)
        actual_pct = (actual_count / total) * 100
        target_pct = target[cat]
        diff = actual_pct - target_pct
        status = "✅" if abs(diff) < 10 else ("⚠️" if abs(diff) < 20 else "❌")
        
        print(f"{status} {cat:20s}: Target {target_pct:3d}% | Actual {actual_pct:5.1f}% | Diff: {diff:+5.1f}%")
    
    # Show top stocks by category
    print(f"\n{'=' * 80}")
    print("TOP 5 STOCKS BY CATEGORY")
    print("=" * 80)
    
    for cat in ['CORE_VALUE', 'CORE_MOMENTUM', 'OPPORTUNISTIC', 'SPECULATIVE']:
        cat_stocks = df[df['stock_classification'] == cat].copy()
        if not cat_stocks.empty and 'risk_adjusted_score' in cat_stocks.columns:
            top5 = cat_stocks.nlargest(5, 'risk_adjusted_score')[['symbol', 'risk_adjusted_score', 'pe_ratio', 'pb_ratio']]
            print(f"\n{cat}:")
            for idx, row in top5.iterrows():
                pe = row['pe_ratio'] if pd.notna(row['pe_ratio']) else 'N/A'
                pb = row['pb_ratio'] if pd.notna(row['pb_ratio']) else 'N/A'
                print(f"  {row['symbol']:15s} Score: {row['risk_adjusted_score']:5.1f} | P/E: {pe:>6} | P/B: {pb:>6}")

else:
    print("\n❌ stock_classification column not found in Complete Data sheet!")
    print(f"Available columns: {list(df.columns[:20])}")
