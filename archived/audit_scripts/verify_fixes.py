import pandas as pd
import warnings
warnings.filterwarnings('ignore')
import glob, os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Find latest report
reports = sorted(glob.glob('reports/Enhanced_Stock_Report_*.xlsx'))
if not reports:
    raise FileNotFoundError('No Enhanced_Stock_Report_*.xlsx found in reports/')
latest = reports[-1]
print(f"\nReport: {os.path.basename(latest)}\n")

xl = pd.read_excel(latest, sheet_name='Portfolio Allocation', header=1, nrows=35)

# 1. Check new columns exist
new_cols = ['STOP_LOSS', 'ROTATION_TARGET', 'ROTATION_TRIGGER_PRICE',
            'BOOK %', 'WHEN', 'BOOK ₹']
print("=== NEW COLUMN CHECK ===")
for c in new_cols:
    found = any(c.upper() in str(col).upper() for col in xl.columns)
    book_found = 'BOOK' in str(c) and any('BOOK' in str(col) for col in xl.columns)
    status = 'PASS' if (found or book_found) else 'MISS'
    print(f"  {status}  {c}")

# 2. Show all actual column names that are new
actual_new = [c for c in xl.columns if any(x in str(c).upper() for x in
              ['STOP','ROTATION','BOOK','WHEN'])]
print(f"\n  Actual new cols in sheet: {actual_new}")

# 3. Show owned stock decisions
print("\n=== OWNED STOCK DECISIONS ===")
own_col = [c for c in xl.columns if 'OWN' in str(c).upper()]
if own_col:
    owned = xl[xl[own_col[0]] == True].copy()
    cols_to_show = []
    for want in ['symbol', 'ACTION', 'P&L %', 'STOP_LOSS', 'BOOK %',
                 'WHEN', 'ROTATION_TARGET', 'ROTATION_TRIGGER_PRICE']:
        matches = [c for c in xl.columns if want.lower() in str(c).lower()]
        if matches:
            cols_to_show.append(matches[0])
    print(owned[cols_to_show].to_string(index=False))

# 4. Verify key gap fixes
print("\n=== KEY GAP VERIFICATION ===")
if own_col:
    owned = xl[xl[own_col[0]] == True].copy()
    sym_col = [c for c in xl.columns if 'symbol' in str(c).lower()]
    act_col = [c for c in xl.columns if 'action' in str(c).lower() and 'ACTION' in str(c)]
    sl_col  = [c for c in xl.columns if 'STOP_LOSS' in str(c).upper()]
    bp_col  = [c for c in xl.columns if 'BOOK' in str(c).upper()]

    if sym_col and act_col:
        sym_c, act_c = sym_col[0], act_col[0]
        # MI-C01: Stop loss populated
        if sl_col:
            sl_filled = owned[sl_col[0]].notna().sum()
            print(f"  MI-C01 STOP_LOSS: {sl_filled}/{len(owned)} stocks have stop loss defined")
        # MI-P05: Book% populated
        if bp_col:
            bp_filled = owned[bp_col[0]].notna().sum()
            print(f"  MI-P05 BOOK %:    {bp_filled}/{len(owned)} owned stocks have booking plan")
        # MI-L04: BAJAJHLDNG not sold at a loss
        bajaj_rows = owned[owned[sym_c].str.upper().str.contains('BAJAJ', na=False)]
        if not bajaj_rows.empty:
            bajaj_action = bajaj_rows.iloc[0][act_c]
            result = 'PASS' if 'SELL' not in str(bajaj_action).upper() else 'FAIL'
            print(f"  MI-L04 BAJAJHLDNG: {result} - action={bajaj_action}")
        # RT-08: No INCREASE for clear losers
        inc_rows = owned[owned[act_c].astype(str).str.upper().str.contains('INCREASE', na=False)]
        pnl_col  = [c for c in xl.columns if 'P&L' in str(c) or 'PROFIT' in str(c).upper()]
        if pnl_col and not inc_rows.empty:
            inc_losers = inc_rows[pd.to_numeric(inc_rows[pnl_col[0]], errors='coerce').fillna(0) < -2]
            result = 'PASS' if len(inc_losers) == 0 else 'FAIL'
            print(f"  RT-08  No INCREASE on losers>2%: {result} ({len(inc_losers)} violations)")
