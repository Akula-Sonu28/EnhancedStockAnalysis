"""
Fix Company Names in Portfolio Data
"""

import pandas as pd

# Read the corrected portfolio
portfolio = pd.read_csv('data/raw/portfolio_data.csv')

# Read the merged portfolio to get correct company names
merged = pd.read_excel('reports/merged_portfolio_20251006_193222.xlsx')

# Create a mapping of Symbol -> Company Name
symbol_to_name = dict(zip(merged['Instrument'], merged['Company_Name']))

# Update company names
portfolio['Company Name'] = portfolio['Symbol'].map(symbol_to_name)

# Save the updated file
portfolio.to_csv('data/raw/portfolio_data.csv', index=False)

print("✅ Fixed company names in portfolio_data.csv")
print(f"\n{'Symbol':<15} {'Company Name':<50}")
print("-"*65)
for idx, row in portfolio.iterrows():
    print(f"{row['Symbol']:<15} {row['Company Name']:<50}")
