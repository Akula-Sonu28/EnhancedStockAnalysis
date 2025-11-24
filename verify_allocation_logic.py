import pandas as pd
import glob
import os

# Get latest report
report_files = glob.glob(r"reports\Enhanced_Stock_Report_*.xlsx")
file = max(report_files, key=os.path.getmtime)

print("="*100)
print(f"🔍 VERIFYING ALLOCATION LOGIC")
print(f"📄 Report: {os.path.basename(file)}")
print("="*100)

# Read Complete Data to see all analyzed stocks
complete_data = pd.read_excel(file, sheet_name='Complete Data')
portfolio = pd.read_excel(file, sheet_name='Portfolio Allocation')

print(f"\n📊 COMPLETE DATA SHEET: {len(complete_data)} stocks analyzed")
print(f"📊 PORTFOLIO ALLOCATION SHEET: {len(portfolio)} stocks in portfolio")

# Check top scoring stocks and their sectors
print(f"\n🏆 TOP 20 STOCKS BY RISK-ADJUSTED SCORE:")
print("-"*100)
top20 = complete_data.nlargest(20, 'risk_adjusted_score')[['symbol', 'company_name', 'sector', 'risk_adjusted_score', 'final_recommendation']]
for idx, row in top20.iterrows():
    in_portfolio = "✅" if row['symbol'] in portfolio['symbol'].values else "❌"
    print(f"{in_portfolio} {row['symbol']:12} | Score: {row['risk_adjusted_score']:5.1f} | {row['sector'][:25]:25} | {row['final_recommendation'][:20]:20}")

# Sector distribution of top stocks
print(f"\n📊 SECTOR DISTRIBUTION - TOP 30 STOCKS:")
top30_sectors = complete_data.nlargest(30, 'risk_adjusted_score')['sector'].value_counts()
for sector, count in top30_sectors.items():
    print(f"   {sector:30} : {count:2d} stocks")

# Check which top stocks are NOT in portfolio
print(f"\n❌ TOP SCORING STOCKS NOT IN PORTFOLIO (Score ≥75):")
print("-"*100)
portfolio_symbols = set(portfolio['symbol'])
high_scorers = complete_data[complete_data['risk_adjusted_score'] >= 75]
not_in_portfolio = high_scorers[~high_scorers['symbol'].isin(portfolio_symbols)]

if len(not_in_portfolio) > 0:
    print(f"   Found {len(not_in_portfolio)} high-scoring stocks NOT allocated:")
    for idx, row in not_in_portfolio.nlargest(15, 'risk_adjusted_score').iterrows():
        print(f"   • {row['symbol']:12} - Score: {row['risk_adjusted_score']:5.1f} | {row['sector'][:25]:25} | {row['final_recommendation']}")
else:
    print("   ✅ All high-scoring stocks are in portfolio!")

# Check sector distribution in portfolio
print(f"\n📊 SECTOR DISTRIBUTION IN PORTFOLIO:")
portfolio_sectors = portfolio['sector'].value_counts()
for sector, count in portfolio_sectors.items():
    print(f"   {sector:30} : {count:2d} stocks")

# Check allocation amounts
print(f"\n💰 ALLOCATION SUMMARY:")
my_shares = portfolio['MY_SHARES'].fillna(0)
invest_amount = portfolio['INVEST_₹'].fillna(0)

current_holdings = portfolio[my_shares > 0]
new_positions = portfolio[(my_shares == 0) & (invest_amount > 0)]
increase_positions = portfolio[(my_shares > 0) & (invest_amount > 0)]

print(f"   Current Holdings (MY_SHARES > 0): {len(current_holdings)} stocks")
print(f"   New Positions (BUY): {len(new_positions)} stocks")
print(f"   Increase Positions: {len(increase_positions)} stocks")
print(f"   Total allocation (INVEST_₹): ₹{invest_amount.sum():,.2f}")

if len(new_positions) > 0:
    print(f"\n🆕 NEW BUY ALLOCATIONS:")
    for idx, row in new_positions.iterrows():
        print(f"   • {row['symbol']:12} - ₹{row['INVEST_₹']:>10,.2f} | Score: {row['SCORE']:5.1f} | {row['sector']}")

print("\n" + "="*100)
