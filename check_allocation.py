import pandas as pd
import sys

report = sys.argv[1] if len(sys.argv) > 1 else 'reports/Enhanced_Stock_Report_20260129_180338.xlsx'

df = pd.read_excel(report, sheet_name='Portfolio Allocation')
invest_df = df[df['INVEST_₹'] > 0][['symbol', 'ACTION', 'INVEST_₹', 'SCORE']].sort_values('INVEST_₹', ascending=False)

print(f'Stocks with INVEST_₹ > 0: {len(invest_df)}\n')
print(invest_df.to_string(index=False))
print(f'\nTotal allocated: ₹{invest_df["INVEST_₹"].sum():,.0f}')
