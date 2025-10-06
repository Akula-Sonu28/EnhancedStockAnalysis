"""
Update Portfolio After Sell Orders
Updates quantities for stocks after executed sell orders
"""

import pandas as pd
from datetime import datetime

# Read current portfolio
portfolio = pd.read_csv('data/raw/portfolio_data.csv')

print("="*70)
print("📊 CURRENT PORTFOLIO (Before Sell Orders)")
print("="*70)
print(f"\nTotal stocks: {len(portfolio)}")
print(f"Total shares: {portfolio['Quantity'].sum():,}")

# Your actual holdings after selling (12 executed orders)
# Please update this dictionary with ALL your actual quantities after selling
ACTUAL_HOLDINGS = {
    'ETERNAL': 29,
    'MOTILALOFS': 11,
    # Add more stocks here with their actual quantities after selling
    # Example format:
    # 'SYMBOL': quantity,
}

print("\n" + "="*70)
print("🔄 UPDATING QUANTITIES AFTER SELL ORDERS")
print("="*70)

print(f"\n{'Stock':<15} {'Old Qty':<10} {'New Qty':<10} {'Change':<12}")
print("-"*70)

# Track changes
changes_made = 0
total_shares_sold = 0

for symbol, new_qty in ACTUAL_HOLDINGS.items():
    if symbol in portfolio['Symbol'].values:
        old_qty = portfolio.loc[portfolio['Symbol'] == symbol, 'Quantity'].values[0]
        portfolio.loc[portfolio['Symbol'] == symbol, 'Quantity'] = new_qty
        
        change = new_qty - old_qty
        change_str = f"{change:+d}" if change != 0 else "0"
        print(f"{symbol:<15} {old_qty:<10} {new_qty:<10} {change_str:<12}")
        
        if change < 0:
            total_shares_sold += abs(change)
        changes_made += 1
    else:
        print(f"{symbol:<15} NOT FOUND in portfolio!")

print("\n" + "="*70)
print("📈 SUMMARY")
print("="*70)
print(f"Stocks updated: {changes_made}")
print(f"Total shares sold: {total_shares_sold}")
print(f"New total shares: {portfolio['Quantity'].sum():,}")

# Ask for confirmation before saving
print("\n" + "="*70)
print("⚠️  IMPORTANT: Please edit this script and add ALL 12 stocks")
print("   with their actual quantities in the ACTUAL_HOLDINGS dictionary")
print("="*70)

if len(ACTUAL_HOLDINGS) >= 12:
    # Backup before saving
    portfolio_backup = pd.read_csv('data/raw/portfolio_data.csv')
    portfolio_backup.to_csv(f'data/raw/portfolio_data_BEFORE_SELLING_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', index=False)
    
    # Save updated portfolio
    portfolio.to_csv('data/raw/portfolio_data.csv', index=False)
    print("\n✅ Portfolio updated and saved!")
    print(f"📦 Backup saved with timestamp")
    
    # Display updated portfolio
    print("\n" + "="*70)
    print("📊 UPDATED PORTFOLIO")
    print("="*70)
    updated_stocks = portfolio[portfolio['Symbol'].isin(ACTUAL_HOLDINGS.keys())]
    print(updated_stocks[['Symbol', 'Company Name', 'Quantity', 'Buy Price']].to_string(index=False))
else:
    print(f"\n⚠️  Only {len(ACTUAL_HOLDINGS)} stocks provided. Please add all 12 executed orders.")
    print("   Edit the ACTUAL_HOLDINGS dictionary above and run again.")
