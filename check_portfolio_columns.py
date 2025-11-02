import pandas as pd

# Load the Portfolio Allocation sheet
df = pd.read_excel('reports/Enhanced_Stock_Report_20251016_181907.xlsx', sheet_name='Portfolio Allocation')

print('\n✅ PORTFOLIO ALLOCATION COLUMNS:')
print(f'Total columns: {len(df.columns)}\n')

for i, col in enumerate(df.columns, 1):
    print(f'{i:2d}. {col}')

print(f'\n📊 SAMPLE DATA (First stock - {df.iloc[0]["symbol"]}):')
print('='*60)

# Display key columns if they exist
key_columns = ['ACTION', 'SCORE', 'NEW_SCORE', 'PE', 'ROE_%', 'DEBT/EQUITY', 
               'RISK', 'PRICE', '52W_HIGH', '52W_LOW', 'RSI', 'VOLATILITY_%']

for col in key_columns:
    if col in df.columns:
        value = df.iloc[0][col]
        print(f'{col:15s}: {value}')
    else:
        print(f'{col:15s}: ❌ MISSING')

print('\n✅ Column check complete!')
