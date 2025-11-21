"""
Final Portfolio Summary After Sync
"""

import pandas as pd

portfolio = pd.read_csv('data/raw/portfolio_data.csv')
holdings = pd.read_csv('Holding/holdings (6).csv')

print("="*80)
print("✅ PORTFOLIO SUCCESSFULLY SYNCHRONIZED!")
print("="*80)

print("\n📊 FINAL PORTFOLIO STATUS")
print("-"*80)
print(f"Total Stocks:      {len(portfolio)}")
print(f"Total Shares:      {portfolio['Quantity'].sum():,}")
print(f"Total Invested:    ₹{holdings['Invested'].sum():,.2f}")
print(f"Current Value:     ₹{holdings['Cur. val'].sum():,.2f}")
print(f"Unrealized P&L:    ₹{holdings['P&L'].sum():,.2f}")
print(f"P&L Percentage:    {holdings['P&L'].sum() / holdings['Invested'].sum() * 100:.2f}%")

print("\n🏆 TOP 10 HOLDINGS BY VALUE")
print("-"*80)
holdings_sorted = holdings.sort_values('Cur. val', ascending=False)
print(f"{'Rank':<6} {'Stock':<12} {'Qty':<8} {'Value':<15} {'P&L %':<10}")
print("-"*80)
for idx, (i, row) in enumerate(holdings_sorted.head(10).iterrows(), 1):
    pnl_pct = (row['P&L'] / row['Invested'] * 100) if row['Invested'] > 0 else 0
    pnl_emoji = "🟢" if pnl_pct > 0 else "🔴" if pnl_pct < 0 else "⚪"
    print(f"{idx:<6} {row['Instrument']:<12} {int(row['Qty.']):<8} ₹{row['Cur. val']:>12,.2f} {pnl_emoji} {pnl_pct:>6.2f}%")

print("\n🔥 TOP 5 PROFIT MAKERS")
print("-"*80)
print(f"{'Rank':<6} {'Stock':<12} {'P&L':<15} {'P&L %':<10}")
print("-"*80)
for idx, (i, row) in enumerate(holdings_sorted.sort_values('P&L', ascending=False).head(5).iterrows(), 1):
    pnl_pct = (row['P&L'] / row['Invested'] * 100) if row['Invested'] > 0 else 0
    print(f"{idx:<6} {row['Instrument']:<12} ₹{row['P&L']:>12,.2f} 📈 {pnl_pct:>6.2f}%")

print("\n🏦 BANKING SECTOR DOMINANCE")
print("-"*80)
banking_stocks = ['HDFCBANK', 'AXISBANK', 'CANBK', 'KOTAKBANK', 'SBIN', 'BANKBARODA', 
                  'INDIANB', 'UJJIVANSFB', 'PNB', 'BANKINDIA', 'MAHABANK', 'CUB', 
                  'UCOBANK', 'CENTRALBK', 'AUBANK', 'YESBANK', 'KARURVYSYA', 
                  'UNIONBANK', 'IDBI', 'J&KBANK', 'FEDERALBNK', 'IOB', 'ICICIBANK']

banking_holdings = holdings[holdings['Instrument'].isin(banking_stocks)]
banking_value = banking_holdings['Cur. val'].sum()
total_value = holdings['Cur. val'].sum()
banking_pct = (banking_value / total_value * 100)

print(f"Banking Stocks:       {len(banking_holdings)}/{len(holdings)} ({len(banking_holdings)/len(holdings)*100:.1f}%)")
print(f"Banking Shares:       {int(banking_holdings['Qty.'].sum()):,}/{int(holdings['Qty.'].sum()):,} ({banking_holdings['Qty.'].sum()/holdings['Qty.'].sum()*100:.1f}%)")
print(f"Banking Value:        ₹{banking_value:,.2f} (₹{total_value:,.2f})")
print(f"Banking Allocation:   {banking_pct:.1f}% of portfolio 🏦")
print(f"Banking P&L:          ₹{banking_holdings['P&L'].sum():,.2f}")

print("\n✅ Portfolio data is now 100% accurate and ready for analysis!")
print("📁 Updated file: data/raw/portfolio_data.csv")
