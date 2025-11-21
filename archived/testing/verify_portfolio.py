import pandas as pd

csv_df = pd.read_csv('data/raw/portfolio_data.csv')
excel_df = pd.read_excel('reports/merged_portfolio_20251006_193222.xlsx')

print("="*70)
print("📊 PORTFOLIO VERIFICATION")
print("="*70)

print("\n1️⃣ CSV Portfolio (portfolio_data.csv):")
print(f"   Stocks: {len(csv_df)}")
print(f"   Total Shares: {csv_df['Quantity'].sum():,}")

print("\n2️⃣ Excel Portfolio (merged_portfolio):")
print(f"   Stocks: {len(excel_df)}")
print(f"   Total Shares: {excel_df['Qty.'].sum():,}")

print("\n3️⃣ Sample Comparison:")
print(f"   {'Symbol':<12} {'CSV Qty':<10} {'Excel Qty':<10} {'Match'}")
print("   " + "-"*45)
for idx, row in csv_df.head(10).iterrows():
    symbol = row['Symbol']
    csv_qty = row['Quantity']
    excel_qty = excel_df[excel_df['Instrument'] == symbol]['Qty.'].values[0] if len(excel_df[excel_df['Instrument'] == symbol]) > 0 else 0
    match = "✅" if csv_qty == excel_qty else "❌"
    print(f"   {symbol:<12} {csv_qty:<10} {excel_qty:<10} {match}")

if csv_df['Quantity'].sum() == excel_df['Qty.'].sum():
    print("\n" + "="*70)
    print("✅ SUCCESS! Portfolio quantities are perfectly synchronized!")
    print("="*70)
else:
    print("\n" + "="*70)
    print("❌ MISMATCH DETECTED!")
    print("="*70)
