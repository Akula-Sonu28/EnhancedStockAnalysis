import pandas as pd

# Check Portfolio Allocation sheet structure
excel_file = 'reports/Enhanced_Stock_Report_20250919_233305.xlsx'
portfolio_df = pd.read_excel(excel_file, sheet_name='Portfolio Allocation')

print("Portfolio Allocation Columns:")
print(portfolio_df.columns.tolist())
print(f"\nDataFrame shape: {portfolio_df.shape}")
print(f"\nFirst few rows:")
print(portfolio_df.head())