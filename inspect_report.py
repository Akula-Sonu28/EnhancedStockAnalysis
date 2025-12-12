import pandas as pd
import os

import glob

# Auto-detect latest report
list_of_files = glob.glob('reports/Enhanced_Stock_Report_*.xlsx') 
report_path = max(list_of_files, key=os.path.getctime)
print(f"Latest Report Found: {report_path}")

try:
    print(f"Reading {report_path}...")
    df = pd.read_excel(report_path, sheet_name='Portfolio Allocation')
    
    print(f"Total Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    
    if 'ACTION' in df.columns:
        print("\nAction Counts:")
        print(df['ACTION'].value_counts())
        
        # Check for SWAPS
        swaps = df[df['ACTION'].str.contains('SWAP', na=False)]
        print(f"\n🔄 Swap Recommendations ({len(swaps)}):")
        if not swaps.empty:
            print(swaps[['symbol', 'ACTION', 'SCORE']].head(10))
            
        # Check for CUTS
        cuts = df[df['ACTION'].str.contains('WEAK', na=False)]
        print(f"\n❌ Cut Candidates ({len(cuts)}):")
        if not cuts.empty:
            print(cuts[['symbol', 'ACTION', 'SCORE']].head(10))

    if 'ACTION' in df.columns and 'SCORE' in df.columns:
        print("\n📊 New Opportunities:")
        new_ops = df[df['ACTION'] == 'NEW POSITION']
        print(new_ops[['symbol', 'ACTION', 'SCORE']].sort_values('SCORE', ascending=False))

        print("\n📊 Full Portfolio Status:")
        holdings = df[~df['ACTION'].isin(['NEW POSITION', 'BUY'])]
        print(holdings[['symbol', 'ACTION', 'SCORE']].sort_values('SCORE'))
        
except Exception as e:
    print(f"Error: {e}")
