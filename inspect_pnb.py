import pandas as pd
import os

# Find latest report
reports_dir = 'reports'
reports = [os.path.join(reports_dir, f) for f in os.listdir(reports_dir) if f.endswith('.xlsx') and not f.startswith('~$')]
latest_report = max(reports, key=os.path.getmtime)
print(f"Reading: {latest_report}")

# Read 'Portfolio Allocation' sheet (or 'Dashboard' if Allocation not found, but likely 'Portfolio Allocation')
try:
    df = pd.read_excel(latest_report, sheet_name='Portfolio Allocation')
except:
    try:
        df = pd.read_excel(latest_report, sheet_name='Data') # Fallback
    except:
        print("Could not find standard sheets. Printing sheet names...")
        xl = pd.ExcelFile(latest_report)
        print(xl.sheet_names)
        exit()

# Find PNB
pnb_row = df[df['symbol'] == 'PNB']
if not pnb_row.empty:
    print("\n=== PNB STATUS ===")
    print(pnb_row.iloc[0])
    # Print specific current value column if it exists
    val_cols = [c for c in df.columns if 'VAL' in c.upper() or 'CURRENT' in c.upper() or 'MY_SH_VAL' in c.upper()]
    print(f"Value Columns Found: {val_cols}")
    for c in val_cols:
        print(f"{c}: {pnb_row.iloc[0].get(c)}")
else:
    print("\nPNB not found in report!")

# Find Top Superstars (Non-Held)
print("\n=== TOP 5 NON-HELD STOCKS (POTENTIAL SWAPS) ===")
# Identify score column
cols = df.columns.tolist()
score_col = next((c for c in cols if 'SCORE' in c.upper() and 'FUND' not in c.upper() and 'MOM' not in c.upper() and 'VALUE' not in c.upper()), 'VALUE_SCORE') # Fallback
print(f"Using Score Column: {score_col}")

# Filter for Non-Held (OWN_IT? == 'No' or similar, or MY_SHARES == 0)
if 'MY_SHARES' in df.columns:
    non_held = df[df['MY_SHARES'] == 0]
elif 'OWN_IT?' in df.columns:
    non_held = df[df['OWN_IT?'] == 'No']
else:
    non_held = df

# Sort by score
superstars = non_held.sort_values(score_col, ascending=False).head(5)
invest_cols = [c for c in df.columns if 'INVEST' in c.upper()]
print(f"Invest Columns: {invest_cols}")
print(superstars[['symbol', score_col] + invest_cols])
