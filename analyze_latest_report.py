import pandas as pd
import glob
import os

# Find latest report
reports = glob.glob('reports/Enhanced_Stock_Report_*.xlsx')
latest_report = max(reports, key=os.path.getctime)

print(f"=== ANALYZING REPORT ===")
print(f"File: {os.path.basename(latest_report)}\n")

# Read Portfolio Allocation sheet
df = pd.read_excel(latest_report, sheet_name='Portfolio Allocation')

print("=== PORTFOLIO ALLOCATION SUMMARY ===")
print(f"Total Stocks: {len(df)}\n")

print("Action Breakdown:")
print(df['ACTION'].value_counts())
print()

# Check for BOOK_₹_AMOUNT column
if 'BOOK_₹_AMOUNT' in df.columns:
    print("✅ BOOK_₹_AMOUNT column exists!\n")
else:
    print("❌ BOOK_₹_AMOUNT column NOT found\n")
    print("Available columns:")
    print([col for col in df.columns if 'BOOK' in col.upper()])
    print()

# Allocation amounts
alloc = df[df['INVEST_₹'].notna() & (df['INVEST_₹'] > 0)]
print("=== ALLOCATION AMOUNTS ===")
print(f"Total Allocated: ₹{alloc['INVEST_₹'].sum():,.2f}\n")

print("By Action:")
for action in ['INCREASE', 'BUY', 'HOLD', 'SELL', 'BOOK_PROFIT']:
    amt = df[df['ACTION'] == action]['INVEST_₹'].sum()
    if amt > 0:
        print(f"  {action}: ₹{amt:,.2f}")

# Show detailed allocation
print("\n=== DETAILED ALLOCATIONS ===")
alloc_stocks = df[df['INVEST_₹'] > 0][['symbol', 'ACTION', 'INVEST_₹', 'MY_SHARES', 'MY_VALUE_₹']].copy()
alloc_stocks = alloc_stocks.sort_values('INVEST_₹', ascending=False)
print(alloc_stocks.to_string(index=False))

# Show BOOK_PROFIT stocks with rupee amounts
if 'BOOK_₹_AMOUNT' in df.columns:
    print("\n=== PROFIT BOOKING DETAILS ===")
    book_stocks = df[df['ACTION'] == 'BOOK_PROFIT'][['symbol', 'MY_VALUE_₹', 'BOOK_%_IF_SELL', 'BOOK_₹_AMOUNT']].copy()
    if not book_stocks.empty:
        print(book_stocks.to_string(index=False))
    else:
        print("No BOOK_PROFIT actions in this report")

# Show ACC details if present
print("\n=== ACC ALLOCATION ===")
acc = df[df['symbol'] == 'ACC']
if not acc.empty:
    print(acc[['symbol', 'ACTION', 'INVEST_₹', 'MY_SHARES', 'SCORE']].to_string(index=False))
else:
    print("ACC not found in Portfolio Allocation")

# Summary of capital
print("\n=== CAPITAL SUMMARY ===")
user_input = 94219
sell_proceeds = df[df['ACTION'] == 'SELL']['MY_VALUE_₹'].sum()
if 'BOOK_₹_AMOUNT' in df.columns:
    book_proceeds = df[df['ACTION'] == 'BOOK_PROFIT']['BOOK_₹_AMOUNT'].sum()
else:
    book_proceeds = 0

total_available = user_input + sell_proceeds + book_proceeds
total_allocated = alloc['INVEST_₹'].sum()
unallocated = total_available - total_allocated

print(f"User Input: ₹{user_input:,.2f}")
print(f"SELL Proceeds: ₹{sell_proceeds:,.2f}")
print(f"BOOK_PROFIT Proceeds: ₹{book_proceeds:,.2f}")
print(f"Total Available: ₹{total_available:,.2f}")
print(f"Total Allocated: ₹{total_allocated:,.2f}")
print(f"Unallocated: ₹{unallocated:,.2f}")
print(f"Deployment %: {(total_allocated/total_available)*100:.1f}%")
