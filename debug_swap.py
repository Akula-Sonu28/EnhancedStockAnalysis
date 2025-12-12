import pandas as pd
import glob
import os

# Auto-detect latest report
list_of_files = glob.glob('reports/Enhanced_Stock_Report_*.xlsx') 
report_path = max(list_of_files, key=os.path.getctime)
print(f"Reading {report_path}...")

try:
    # Check Top Picks (Source of Truth for Scores)
    df_top = pd.read_excel(report_path, sheet_name='Top Picks')
    nmdc_top = df_top[df_top['symbol'] == 'NMDC']
    if not nmdc_top.empty:
        print("\nNMDC in Top Picks:")
        # Use available columns only
        print(nmdc_top[['symbol', 'final_recommendation', 'risk_adjusted_score', 'overall_score_with_value']].to_string())
    else:
        print("\nNMDC NOT found in Top Picks!")

    # Check Portfolio Allocation (Where Swaps happen)
    df_port = pd.read_excel(report_path, sheet_name='Portfolio Allocation')
    nmdc_port = df_port[df_port['symbol'] == 'NMDC']
    if not nmdc_port.empty:
        print("\nNMDC in Portfolio Allocation:")
        print(nmdc_port[['symbol', 'ACTION', 'SCORE', 'INVEST_₹']].to_string())
    else:
        print("\nNMDC NOT found in Portfolio Allocation!")
        
    # Check PNB
    pnb_port = df_port[df_port['symbol'] == 'PNB']
    print("\nPNB Status:")
    print(pnb_port[['symbol', 'ACTION', 'SCORE']].to_string())

except Exception as e:
    print(f"Error: {e}")
