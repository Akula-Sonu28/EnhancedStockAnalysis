import pandas as pd

df = pd.read_excel('reports/Enhanced_Stock_Report_20260129_180753.xlsx', sheet_name='Portfolio Allocation')

print('NATIONALUM Details:')
nat = df[df['symbol'] == 'NATIONALUM']
if not nat.empty:
    print(nat[['symbol', 'ACTION', 'INVEST_₹', 'MY_SHARES', 'MY_VALUE_₹', 'SCORE', 'PRE_BREAKOUT?', 'BREAKOUT_%', 'EXHAUSTION?', 'EXIT_SCORE']].to_string(index=False))
else:
    print('NATIONALUM not found')

print('\n\nAll INCREASE actions:')
increases = df[df['ACTION'] == 'INCREASE'][['symbol', 'ACTION', 'INVEST_₹', 'SCORE', 'EXIT_SCORE']]
print(increases.to_string(index=False))
