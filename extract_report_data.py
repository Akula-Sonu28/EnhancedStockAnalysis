import pandas as pd
import json

excel_path = r"c:\Users\A KAVYA SHREE\OneDrive\Documents\Sanji\Stock Analyis\Stock_Analysis - Copy\reports\Enhanced_Stock_Report_20251210_153136.xlsx"

try:
    # Read the excel file
    xls = pd.ExcelFile(excel_path)
    sheet_name = 'Portfolio Allocation'
    try:
        df = pd.read_excel(xls, sheet_name=sheet_name)
    except:
        # Try finding a sheet with 'Allocation' in name
        sheets = [s for s in xls.sheet_names if 'Allocation' in s]
        if sheets:
            sheet_name = sheets[0]
            df = pd.read_excel(xls, sheet_name=sheet_name)
        else:
            print("Portfolio Allocation sheet not found.")
            exit()

    # Clean column names
    df.columns = [str(c).strip() for c in df.columns]
    
    # Print structure
    print(f"\n--- SHEET: {sheet_name} ---")
    
    # Check for duplicates using the actual column name for symbol
    symbol_col = None
    for col in df.columns:
        if str(col).lower() in ['symbol', 'instrument', 'stock']:
            symbol_col = col
            break
            
    if symbol_col:
        duplicates = df[df.duplicated(subset=[symbol_col], keep=False)]
        if not duplicates.empty:
            print(f"⚠️ FOUND {len(duplicates)} DUPLICATE ROWS BY SYMBOL:")
            dup_cols = [c for c in df.columns if c in [symbol_col, 'ACTION', 'SCORE', 'RISK', 'priority']]
            print(duplicates[dup_cols].sort_values(symbol_col).to_string())
        else:
            print(f"✅ No duplicates found in '{symbol_col}' column.")
    
    # Print all symbols in Portfolio Allocation
    print(f"\n--- ALL STOCKS IN PORTFOLIO ALLOCATION ({len(df)} rows) ---")
    if 'symbol' in df.columns:
        cols_to_show = [c for c in df.columns if c in ['symbol', 'ACTION', 'SCORE', 'INVEST_₹', 'PORTFOLIO_%', 'BUY_SHARES']]
        print(df[cols_to_show].head(20).to_string())
        
    # Check KOTAKBANK specifically
    stock_row = df[df['symbol'] == 'KOTAKBANK']
    if not stock_row.empty:
        print("\n--- KOTAKBANK DATA ---")
        cols_of_interest = [c for c in df.columns if c in ['symbol', 'ACTION', 'SCORE', 'RISK_SCORE', 'V3_SCORE']]
        print(stock_row.iloc[0][cols_of_interest].to_json(indent=2))
        
    # Check HINDALCO specifically
    hindalco_row = df[df['symbol'] == 'HINDALCO']
    if not hindalco_row.empty:
        print("\n--- HINDALCO DATA ---")
        cols_of_interest = [c for c in df.columns if c in ['symbol', 'ACTION', 'SCORE', 'RISK_SCORE', 'V3_SCORE']]
        print(hindalco_row.iloc[0][cols_of_interest].to_json(indent=2))

            
except Exception as e:
    print(f"Error reading excel: {e}")
