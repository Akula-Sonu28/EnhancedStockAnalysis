#!/usr/bin/env python3
"""
Check which sheet is being used for comparison
"""

from report_comparison.analyzer import ReportComparator
import pandas as pd

# Create comparator and load the latest reports
comparator = ReportComparator()
reports = comparator.get_latest_reports(2)

print('📊 COMPARISON SHEET ANALYSIS')
print('='*50)

# Load both reports
old_data = comparator.load_report_data(reports[1])  # Older report
new_data = comparator.load_report_data(reports[0])  # Newer report

print(f'\n🔍 Available sheets in reports:')
print(f'Old report sheets: {list(old_data.keys())}')
print(f'New report sheets: {list(new_data.keys())}')

print(f'\n📋 Detailed sheet analysis:')
for sheet_name, df in new_data.items():
    try:
        if hasattr(df, 'columns') and 'Symbol' in df.columns:
            print(f'\n   ✅ {sheet_name}:')
            print(f'      📊 Stocks: {len(df)}')
            print(f'      📋 Columns: {len(df.columns)}')
            key_cols = [col for col in df.columns if any(key in col for key in ['Symbol', 'Company', 'LTP', 'Return', 'Rank', 'Score', 'Price'])]
            print(f'      🎯 Key columns: {key_cols[:10]}')  # Show first 10
            
            if len(df) > 0:
                print(f'      📈 Sample data: {df["Symbol"].head(3).tolist()}')
    except:
        print(f'   ❌ {sheet_name}: Cannot analyze (not a DataFrame or no Symbol column)')

# Test which sheet is actually selected for comparison
print(f'\n🎯 TESTING COMPARISON LOGIC:')
print('='*40)

# Simulate the selection logic
possible_sheets = ['Summary', 'Top_Stocks', 'Analysis_Results', 'Main', 'Stock_Analysis']
selected_sheet = None

for sheet_name in possible_sheets:
    if sheet_name in old_data and sheet_name in new_data:
        selected_sheet = sheet_name
        print(f'✅ Found matching sheet: {sheet_name}')
        break

if not selected_sheet:
    print('🔍 No standard sheet found, using fallback logic...')
    for sheet_name, df in new_data.items():
        if hasattr(df, 'columns') and 'Symbol' in df.columns and len(df) > 0:
            selected_sheet = sheet_name
            print(f'✅ Selected fallback sheet: {sheet_name}')
            break

if selected_sheet:
    print(f'\n📊 FINAL SELECTION: {selected_sheet}')
    print(f'   Old report data: {len(old_data[selected_sheet])} rows')
    print(f'   New report data: {len(new_data[selected_sheet])} rows')
else:
    print('❌ No suitable sheet found for comparison!')