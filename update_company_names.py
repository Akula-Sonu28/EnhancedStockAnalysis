"""
Get Company Names from NSE Ticker Data
"""

import pandas as pd
import yfinance as yf

# Stock name mappings (NSE common stocks)
STOCK_NAMES = {
    'HDFCBANK': 'HDFC Bank Ltd',
    'AXISBANK': 'Axis Bank Ltd',
    'CANBK': 'Canara Bank',
    'KOTAKBANK': 'Kotak Mahindra Bank Ltd',
    'SBIN': 'State Bank of India',
    'ETERNAL': 'Eternal Ltd',
    'BANKBARODA': 'Bank of Baroda',
    'INDIANB': 'Indian Bank',
    'HINDUNILVR': 'Hindustan Unilever Ltd',
    'UJJIVANSFB': 'Ujjivan Small Finance Bank Ltd',
    'PNB': 'Punjab National Bank',
    'BANKINDIA': 'Bank of India',
    'MAHABANK': 'Bank of Maharashtra',
    'CUB': 'City Union Bank Ltd',
    'UCOBANK': 'UCO Bank',
    'CENTRALBK': 'Central Bank of India',
    'MUTHOOTFIN': 'Muthoot Finance Ltd',
    'MOTILALOFS': 'Motilal Oswal Financial Services Ltd',
    'GICRE': 'General Insurance Corporation of India',
    'AUBANK': 'AU Small Finance Bank Ltd',
    'RECLTD': 'REC Ltd',
    'PFC': 'Power Finance Corporation Ltd',
    'YESBANK': 'Yes Bank Ltd',
    'NESTLEIND': 'Nestle India Ltd',
    'KARURVYSYA': 'Karur Vysya Bank Ltd',
    'LICHSGFIN': 'LIC Housing Finance Ltd',
    'UNIONBANK': 'Union Bank of India',
    'IDBI': 'IDBI Bank Ltd',
    'J&KBANK': 'Jammu & Kashmir Bank Ltd',
    'NMDC': 'NMDC Ltd',
    'FEDERALBNK': 'Federal Bank Ltd',
    'IOB': 'Indian Overseas Bank',
    'DRREDDY': 'Dr. Reddy\'s Laboratories Ltd',
    'WIPRO': 'Wipro Ltd',
    'ICICIBANK': 'ICICI Bank Ltd',
    'BAJAJHLDNG': 'Bajaj Holdings & Investment Ltd'
}

# Read portfolio
portfolio = pd.read_csv('data/raw/portfolio_data.csv')

# Update company names
portfolio['Company Name'] = portfolio['Symbol'].map(STOCK_NAMES)

# Fill any missing with "Unknown"
portfolio['Company Name'] = portfolio['Company Name'].fillna('Unknown')

# Save
portfolio.to_csv('data/raw/portfolio_data.csv', index=False)

print("✅ Updated company names in portfolio_data.csv")
print(f"\n{'Symbol':<15} {'Quantity':<10} {'Company Name':<50}")
print("-"*75)
for idx, row in portfolio.head(15).iterrows():
    print(f"{row['Symbol']:<15} {row['Quantity']:<10} {row['Company Name']:<50}")
print(f"... and {len(portfolio)-15} more stocks")

print(f"\n📊 Total Holdings: {len(portfolio)} stocks, {portfolio['Quantity'].sum()} shares")
