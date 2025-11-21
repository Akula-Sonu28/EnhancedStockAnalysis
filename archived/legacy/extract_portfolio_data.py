#!/usr/bin/env python3
"""Extract portfolio data for action plan generation"""

import pandas as pd
import sys

try:
    # Read the Portfolio Allocation sheet
    df = pd.read_excel('reports/Enhanced_Stock_Report_20251017_114430.xlsx', 
                       sheet_name='Portfolio Allocation')
    
    print(f"Total stocks in portfolio: {len(df)}\n")
    print("="*120)
    
    # Key columns for action planning
    key_cols = ['symbol', 'company_name', 'ACTION', 'WHEN_TO_ACT', 
                'INVEST_₹', 'BUY_SHARES', 'MY_SHARES', 'MY_VALUE_₹', 
                'MY_PROFIT_%', 'BOOK_%_IF_SELL', 'SCORE', 'NEW_SCORE', 'TYPE', 'RANK']
    
    # Get available columns
    available_cols = [col for col in key_cols if col in df.columns]
    
    # Display the data
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    pd.set_option('display.max_rows', None)
    
    print(df[available_cols].to_string(index=False))
    
    # Save to CSV for easier processing
    df[available_cols].to_csv('portfolio_data_for_plans.csv', index=False)
    print("\n" + "="*120)
    print("✅ Data saved to: portfolio_data_for_plans.csv")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
