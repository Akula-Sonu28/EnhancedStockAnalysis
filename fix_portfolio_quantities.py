"""
Fix Portfolio Quantity Mismatch
Syncs portfolio_data.csv with actual holdings from merged_portfolio Excel file
"""

import pandas as pd
from datetime import datetime

# Read the actual holdings from merged portfolio
print("📊 Reading actual holdings from merged portfolio...")
df = pd.read_excel('reports/merged_portfolio_20251006_193222.xlsx')

# Create corrected portfolio data
corrected = pd.DataFrame({
    'Symbol': df['Instrument'],
    'Company Name': df['Company_Name'],
    'Quantity': df['Qty.'].astype(int),
    'Buy Price': df['Avg. cost'].round(2),
    'Current Price': '',
    'Date Purchased': ''
})

# Backup old file
old_data = pd.read_csv('data/raw/portfolio_data.csv')
old_data.to_csv('data/raw/portfolio_data_OLD_BACKUP.csv', index=False)
print("✅ Backed up old portfolio_data.csv")

# Save corrected file
corrected.to_csv('data/raw/portfolio_data.csv', index=False)
print("✅ Updated portfolio_data.csv with actual holdings")

# Display comparison
print("\n" + "="*70)
print("📊 QUANTITY COMPARISON")
print("="*70)
print(f"\n{'Stock':<15} {'Old Qty':<10} {'New Qty':<10} {'Difference':<12}")
print("-"*70)

# Merge to compare
old_dict = dict(zip(old_data['Symbol'], old_data['Quantity']))
for idx, row in corrected.iterrows():
    symbol = row['Symbol']
    new_qty = row['Quantity']
    old_qty = old_dict.get(symbol, 0)
    diff = new_qty - old_qty
    diff_str = f"+{diff}" if diff > 0 else str(diff)
    print(f"{symbol:<15} {old_qty:<10} {new_qty:<10} {diff_str:<12}")

print("\n" + "="*70)
print("📈 SUMMARY")
print("="*70)
print(f"Total stocks in OLD file: {len(old_data)}")
print(f"Total stocks in NEW file: {len(corrected)}")
print(f"Old total quantity: {old_data['Quantity'].sum()}")
print(f"New total quantity: {corrected['Quantity'].sum()}")
print(f"Stocks added: {len(set(corrected['Symbol']) - set(old_data['Symbol']))}")
print(f"Stocks removed: {len(set(old_data['Symbol']) - set(corrected['Symbol']))}")

print("\n✅ Portfolio data synchronized successfully!")
print("📁 Backup saved as: data/raw/portfolio_data_OLD_BACKUP.csv")
