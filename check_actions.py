import pandas as pd

df = pd.read_excel('reports/Enhanced_Stock_Report_20260130_113236.xlsx', sheet_name='Portfolio Allocation')

print('ALL UNIQUE ACTION VALUES:\n')
for action in sorted(df['ACTION'].unique()):
    count = (df['ACTION'] == action).sum()
    has_invest = len(df[(df['ACTION'] == action) & (df['INVEST_₹'] > 0)])
    has_value = len(df[(df['ACTION'] == action) & (df['MY_VALUE_₹'] > 0)])
    print(f'{count}x | INVEST:{has_invest} | VALUE:{has_value} | {action}')

print(f'\nTotal stocks: {len(df)}')
