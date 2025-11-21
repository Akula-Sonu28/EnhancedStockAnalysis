import pandas as pd
import os

report_path = r"c:\Users\A KAVYA SHREE\OneDrive\Documents\Sanji\Stock Analyis\Stock_Analysis - Copy\reports\Enhanced_Stock_Report_20251119_235925.xlsx"

print(f"Analyzing report: {report_path}")

try:
    # Read Top Picks
    print("\n--- Top Picks Analysis ---")
    try:
        df_top = pd.read_excel(report_path, sheet_name='Top Picks')
        print(f"Total stocks in Top Picks: {len(df_top)}")
        
        # Check for score column (might be 'Overall Score' or similar)
        score_col = next((col for col in df_top.columns if 'Score' in col and 'Overall' in col), None)
        if not score_col:
             score_col = next((col for col in df_top.columns if 'Score' in col), None)
             
        if score_col and 'Symbol' in df_top.columns:
            top_5 = df_top.nlargest(5, score_col)[['Symbol', score_col, 'Recommendation', 'Current Price']]
            print(f"\nTop 5 Stocks by {score_col}:")
            print(top_5.to_string(index=False))
        
        if 'Sector' in df_top.columns:
            print("\nSector Distribution (Top 5):")
            print(df_top['Sector'].value_counts().head(5).to_string())
            
    except Exception as e:
        print(f"Error reading Top Picks: {e}")

    # Read Portfolio Allocation
    print("\n--- Portfolio Allocation Analysis ---")
    try:
        df_alloc = pd.read_excel(report_path, sheet_name='Portfolio Allocation')
        print(f"Total stocks in Portfolio Allocation: {len(df_alloc)}")
        
        if 'ACTION' in df_alloc.columns:
            print("\nAction Recommendations:")
            print(df_alloc['ACTION'].value_counts().to_string())
            
        if 'INVEST_₹' in df_alloc.columns:
            total_invest = df_alloc['INVEST_₹'].sum()
            print(f"\nTotal Suggested Investment: ₹{total_invest:,.2f}")
            
            # Top buys
            if 'symbol' in df_alloc.columns:
                 buys = df_alloc[df_alloc['ACTION'] == 'BUY'].nlargest(5, 'INVEST_₹')[['symbol', 'INVEST_₹', 'WHY']]
                 print("\nTop 5 Suggested Buys:")
                 print(buys.to_string(index=False))

    except Exception as e:
        print(f"Error reading Portfolio Allocation: {e}")

except Exception as e:
    print(f"Error analyzing report: {e}")
