import pandas as pd
import os

print("🔍 DEBUGGING EXCEL FILE")
print("=" * 40)

# Check file existence
report_path = "reports/Stock_Report_2025-09-03.xlsx"
print(f"File exists: {os.path.exists(report_path)}")

if os.path.exists(report_path):
    try:
        # Read all sheets
        all_sheets = pd.read_excel(report_path, sheet_name=None)
        print(f"Available sheets: {list(all_sheets.keys())}")
        
        for sheet_name, df in all_sheets.items():
            print(f"\nSheet '{sheet_name}':")
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {list(df.columns)}")
            if len(df) > 0:
                print(f"  First row: {df.iloc[0].to_dict()}")
                
    except Exception as e:
        print(f"Error reading Excel: {e}")
        
        # Try reading default sheet
        try:
            df = pd.read_excel(report_path)
            print(f"\nDefault sheet:")
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {list(df.columns)}")
            if len(df) > 0:
                print(f"  First 3 rows:")
                print(df.head(3))
        except Exception as e2:
            print(f"Error reading default sheet: {e2}")
