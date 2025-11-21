import pandas as pd

df = pd.read_csv('data/raw/portfolio_data.csv')

print("="*70)
print("📊 CURRENT PORTFOLIO - All Holdings")
print("="*70)
print(f"\n{'Symbol':<15} {'Quantity':<10} {'Buy Price':<12} {'Company Name'}")
print("-"*70)

for idx, row in df.iterrows():
    print(f"{row['Symbol']:<15} {row['Quantity']:<10} {row['Buy Price']:<12.2f} {row['Company Name'][:40]}")

print("\n" + "="*70)
print(f"Total: {len(df)} stocks, {df['Quantity'].sum():,} shares")
print("="*70)

print("\n💡 Please provide the actual quantities for all 12 stocks you sold:")
print("   Format: SYMBOL: new_quantity")
print("\n   You've already provided:")
print("   - ETERNAL: 29 (was 15, so +14 bought? or was there a sale?)")
print("   - MOTILALOFS: 11 (was 9, so +2 bought? or was there a sale?)")
