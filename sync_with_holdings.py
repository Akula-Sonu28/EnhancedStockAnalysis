"""
Sync Portfolio with Latest Holdings from Zerodha
Updates portfolio_data.csv with actual quantities from holdings (6).csv
"""

import pandas as pd
from datetime import datetime

print("="*80)
print("🔄 SYNCING PORTFOLIO WITH ACTUAL HOLDINGS")
print("="*80)

# Read the actual holdings from Zerodha export
holdings = pd.read_csv('Holding/holdings (6).csv')
print(f"\n✅ Loaded actual holdings: {len(holdings)} stocks")

# Read current portfolio
portfolio = pd.read_csv('data/raw/portfolio_data.csv')
print(f"✅ Loaded current portfolio: {len(portfolio)} stocks")

# Backup current portfolio
backup_filename = f'data/raw/portfolio_data_BEFORE_SYNC_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
portfolio.to_csv(backup_filename, index=False)
print(f"✅ Backup saved: {backup_filename}")

# Create comparison
print("\n" + "="*80)
print("📊 QUANTITY CHANGES AFTER SELL ORDERS")
print("="*80)
print(f"\n{'Stock':<15} {'Old Qty':<10} {'New Qty':<10} {'Change':<15} {'Status'}")
print("-"*80)

changes_made = 0
total_bought = 0
total_sold = 0
new_stocks = []
removed_stocks = []

# Update quantities from holdings file
for idx, holding in holdings.iterrows():
    symbol = holding['Instrument']
    new_qty = holding['Qty.']
    new_avg_cost = holding['Avg. cost']
    
    if symbol in portfolio['Symbol'].values:
        # Stock exists - update quantity
        old_qty = portfolio.loc[portfolio['Symbol'] == symbol, 'Quantity'].values[0]
        portfolio.loc[portfolio['Symbol'] == symbol, 'Quantity'] = new_qty
        portfolio.loc[portfolio['Symbol'] == symbol, 'Buy Price'] = new_avg_cost
        
        change = new_qty - old_qty
        if change > 0:
            status = "📈 BOUGHT"
            total_bought += change
            change_str = f"+{change}"
        elif change < 0:
            status = "📉 SOLD"
            total_sold += abs(change)
            change_str = f"{change}"
        else:
            status = "━ NO CHANGE"
            change_str = "0"
        
        if change != 0:
            print(f"{symbol:<15} {old_qty:<10} {new_qty:<10} {change_str:<15} {status}")
            changes_made += 1
    else:
        # New stock - add to portfolio
        new_stocks.append(symbol)
        print(f"{symbol:<15} {'0':<10} {new_qty:<10} {f'+{new_qty}':<15} {'🆕 NEW STOCK'}")

# Check for removed stocks (in portfolio but not in holdings)
for symbol in portfolio['Symbol'].values:
    if symbol not in holdings['Instrument'].values:
        old_qty = portfolio.loc[portfolio['Symbol'] == symbol, 'Quantity'].values[0]
        removed_stocks.append((symbol, old_qty))
        print(f"{symbol:<15} {old_qty:<10} {'0':<10} {f'-{old_qty}':<15} {'❌ FULLY SOLD'}")

# Remove stocks that were fully sold
if removed_stocks:
    portfolio = portfolio[portfolio['Symbol'].isin(holdings['Instrument'].values)]

# Save updated portfolio
portfolio.to_csv('data/raw/portfolio_data.csv', index=False)

print("\n" + "="*80)
print("📈 SUMMARY OF CHANGES")
print("="*80)
print(f"Stocks with quantity changes: {changes_made}")
print(f"Total shares bought: +{total_bought}")
print(f"Total shares sold: -{total_sold}")
print(f"Net change: {total_bought - total_sold:+d} shares")
print(f"New stocks added: {len(new_stocks)}")
print(f"Stocks fully sold: {len(removed_stocks)}")

if removed_stocks:
    print(f"\n❌ Fully sold stocks:")
    for symbol, qty in removed_stocks:
        print(f"   - {symbol} ({qty} shares)")

print("\n" + "="*80)
print("📊 UPDATED PORTFOLIO")
print("="*80)
print(f"Total stocks: {len(portfolio)}")
print(f"Total shares: {portfolio['Quantity'].sum():,}")
print(f"Total invested: ₹{holdings['Invested'].sum():,.2f}")
print(f"Current value: ₹{holdings['Cur. val'].sum():,.2f}")
print(f"Total P&L: ₹{holdings['P&L'].sum():,.2f} ({holdings['P&L'].sum() / holdings['Invested'].sum() * 100:.2f}%)")

print("\n✅ Portfolio synchronized successfully!")
print(f"📁 Updated file: data/raw/portfolio_data.csv")
print(f"📦 Backup file: {backup_filename}")
