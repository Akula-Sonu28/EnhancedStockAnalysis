import pandas as pd

df = pd.read_excel('reports/Enhanced_Stock_Report_20260129_143809.xlsx', sheet_name='Portfolio Allocation')

print('ACTUAL COLUMNS IN PORTFOLIO ALLOCATION:')
print('=' * 70)
for i, col in enumerate(df.columns, 1):
    print(f'{i}. {col}')

print(f'\nTotal: {len(df.columns)} columns')
