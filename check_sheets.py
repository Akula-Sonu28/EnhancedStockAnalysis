import pandas as pd

file = r"reports\Enhanced_Stock_Report_20251124_221037.xlsx"

# Read Excel file
xl_file = pd.ExcelFile(file)

print(f"📊 Sheet names in {file}:")
for sheet in xl_file.sheet_names:
    print(f"   - {sheet}")
