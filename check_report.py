import pandas as pd

report = "reports/Enhanced_Stock_Report_20251229_133652.xlsx"
df = pd.read_excel(report, sheet_name='Portfolio Allocation')

print(f"\n{'='*60}")
if len(df.columns) >= 30:
    print("RESULT: FULL VERSION")
elif len(df.columns) == 8:
    print("RESULT: FALLBACK VERSION")
else:
    print(f"RESULT: PARTIAL VERSION")

print(f"Total Columns: {len(df.columns)}")
print(f"Total Rows: {len(df)}")
print(f"\n{'='*60}")
print("ALL COLUMN NAMES:")
for i, col in enumerate(df.columns, 1):
    print(f"  {i:2d}. {col}")
print('='*60)
