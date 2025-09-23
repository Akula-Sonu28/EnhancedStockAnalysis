import pandas as pd

df = pd.read_excel('reports/Enhanced_Stock_Report_20250919_221055.xlsx', sheet_name='Portfolio Allocation')

print('INVESTMENT AMOUNT ANALYSIS:')
print('='*40)

keep_df = df[df['keep_stock']==True]

print('Investment amounts for KEEP stocks:')
for _, row in keep_df.head(10).iterrows():
    investment_amt = row['investment_amount'] if pd.notna(row['investment_amount']) else 'None'
    suggested_qty = row['suggested_quantity'] if pd.notna(row['suggested_quantity']) else 'None'
    print(f'{row["symbol"]:<12} | Current: ₹{row["current_value"]:>8,.0f} | Investment: {investment_amt} | Suggested Qty: {suggested_qty}')

print()
print('Summary:')
print(f'Stocks with investment amounts: {keep_df["investment_amount"].notna().sum()}')
print(f'Stocks with suggested quantities: {keep_df["suggested_quantity"].notna().sum()}')
print()

# Check if the system calculated reinvestment amounts
if keep_df['investment_amount'].notna().sum() == 0:
    print('❌ NO REINVESTMENT AMOUNTS CALCULATED!')
    print('The system needs to be enhanced to calculate specific investment amounts for each KEEP stock.')
else:
    print('✅ Reinvestment amounts are calculated')