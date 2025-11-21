import pandas as pd

# Load the Excel report
excel_file = r'C:\Users\Sanji\Downloads\New folder\Stock_Analysis\reports\Enhanced_Stock_Report_20251016_142911.xlsx'
df = pd.read_excel(excel_file, sheet_name='Portfolio Allocation')

print("=" * 80)
print("PORTFOLIO CLASSIFICATION CHECK")
print("=" * 80)

print(f"\nTotal Stocks: {len(df)}")

# Check columns
print(f"\nColumns in Portfolio Allocation sheet:")
for i, col in enumerate(df.columns, 1):
    print(f"  {i}. {col}")

# Check for classification columns
cls_cols = [c for c in df.columns if 'class' in c.lower() or 'category' in c.lower() or 'strategy' in c.lower() or c.upper() == 'TYPE']

if cls_cols:
    print(f"\n{'=' * 80}")
    print("CLASSIFICATION BREAKDOWN")
    print("=" * 80)
    for col in cls_cols:
        print(f"\n{col}:")
        print(df[col].value_counts())
        print(f"\nTotal: {df[col].count()} stocks classified")
else:
    print("\n❌ NO CLASSIFICATION COLUMNS FOUND!")
    print("   Looking for: 'stock_classification', 'category', 'strategy', 'TYPE'")

# Check if actions exist
action_cols = [c for c in df.columns if 'action' in c.lower() or 'recommendation' in c.lower()]
if action_cols:
    print(f"\n{'=' * 80}")
    print("ACTIONS/RECOMMENDATIONS")
    print("=" * 80)
    for col in action_cols:
        print(f"\n{col}:")
        print(df[col].value_counts())

# Show sample data
print(f"\n{'=' * 80}")
print("SAMPLE DATA (First 10 stocks)")
print("=" * 80)
display_cols = ['symbol']
if 'company_name' in df.columns:
    display_cols.append('company_name')
if cls_cols:
    display_cols.extend(cls_cols)
if action_cols:
    display_cols.extend(action_cols)

print(df[display_cols].head(10).to_string(index=False))

# Check strategy alignment
print(f"\n{'=' * 80}")
print("STRATEGY ALIGNMENT CHECK")
print("=" * 80)
print("\nYour Target:")
print("  70% CORE (40% deep value + 30% momentum)")
print("  20% HEDGING (defensive)")
print("  10% SPECULATIVE (high risk/reward)")

if cls_cols:
    for col in cls_cols:
        counts = df[col].value_counts()
        total = len(df)
        print(f"\nActual ({col}):")
        for cat, count in counts.items():
            pct = (count / total) * 100
            print(f"  {cat}: {count} stocks ({pct:.1f}%)")
