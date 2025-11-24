import pandas as pd
import glob
import os

# Get latest report
report_files = glob.glob(r"reports\Enhanced_Stock_Report_*.xlsx")
file = max(report_files, key=os.path.getmtime)

print("="*100)
print("🔍 DEBUGGING CAPITAL ALLOCATION")
print("="*100)
print(f"📄 Report: {os.path.basename(file)}\n")

# Read Portfolio Allocation sheet
portfolio = pd.read_excel(file, sheet_name='Portfolio Allocation')

print(f"\n📊 Total stocks in report: {len(portfolio)}")

# Check for SELL stocks
sell_stocks = portfolio[portfolio['ACTION'] == 'SELL']
print(f"\n🔴 SELL stocks: {len(sell_stocks)}")
for _, row in sell_stocks.iterrows():
    print(f"   {row['symbol']:12} - {row['company_name'][:40]:40}")
    print(f"   Value: ₹{row['MY_VALUE_₹']:,.2f} | INVEST_₹: ₹{row['INVEST_₹']:,.2f} | I_OWN_IT?: {row.get('I_OWN_IT?', 'N/A')}")

# Check BOOK_PROFIT stocks
book_profit = portfolio[portfolio['ACTION'] == 'BOOK_PROFIT']
print(f"\n📈 BOOK_PROFIT stocks: {len(book_profit)}")
for _, row in book_profit.iterrows():
    booking_pct = row.get('BOOK_%_IF_SELL', 0) * 100
    proceeds = row['MY_VALUE_₹'] * row.get('BOOK_%_IF_SELL', 0)
    print(f"   {row['symbol']:12} - Book {booking_pct:.0f}% = ₹{proceeds:,.2f}")

# Check INCREASE stocks
increase_stocks = portfolio[portfolio['ACTION'] == 'INCREASE']
buy_stocks = portfolio[portfolio['ACTION'] == 'BUY']

print(f"\n🔼 INCREASE stocks: {len(increase_stocks)}")
total_increase = increase_stocks['INVEST_₹'].sum()
print(f"   Total to invest in INCREASE: ₹{total_increase:,.2f}")
for _, row in increase_stocks[increase_stocks['INVEST_₹'] > 0].iterrows():
    print(f"   {row['symbol']:12} - ₹{row['INVEST_₹']:,.2f} ({row['BUY_SHARES']:.0f} shares)")

print(f"\n🆕 NEW BUY stocks: {len(buy_stocks)}")
total_buy = buy_stocks['INVEST_₹'].sum()
print(f"   Total to invest in BUY: ₹{total_buy:,.2f}")
for _, row in buy_stocks[buy_stocks['INVEST_₹'] > 0].iterrows():
    print(f"   {row['symbol']:12} - ₹{row['INVEST_₹']:,.2f} ({row['BUY_SHARES']:.0f} shares)")

# Calculate expected total
sell_proceeds = sell_stocks['MY_VALUE_₹'].sum()
book_proceeds = sum(row['MY_VALUE_₹'] * row.get('BOOK_%_IF_SELL', 0) for _, row in book_profit.iterrows())
user_capital = 94000  # From your input

print(f"\n💰 CAPITAL CALCULATION:")
print(f"   User input: ₹{user_capital:,.2f}")
print(f"   SELL proceeds: ₹{sell_proceeds:,.2f}")
print(f"   BOOK_PROFIT proceeds: ₹{book_proceeds:,.2f}")
print(f"   ────────────────────────────")
print(f"   TOTAL AVAILABLE: ₹{user_capital + sell_proceeds + book_proceeds:,.2f}")
print(f"\n   ALLOCATED (INCREASE): ₹{total_increase:,.2f}")
print(f"   ALLOCATED (BUY): ₹{total_buy:,.2f}")
print(f"   ────────────────────────────")
print(f"   TOTAL ALLOCATED: ₹{total_increase + total_buy:,.2f}")
print(f"   UNALLOCATED: ₹{user_capital + sell_proceeds + book_proceeds - total_increase - total_buy:,.2f}")

print("\n" + "="*100)
