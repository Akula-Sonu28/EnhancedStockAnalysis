import pandas as pd
import os

# Find latest report
files = [f for f in os.listdir('reports') if f.startswith('Enhanced_Stock_Report_') and f.endswith('.xlsx')]
latest = sorted(files)[-1]

print(f'📊 Latest Report: {latest}\n')

# Load Portfolio Allocation sheet
df = pd.read_excel(f'reports/{latest}', sheet_name='Portfolio Allocation')

print(f'Total columns: {len(df.columns)}\n')
print('='*80)
print('ALL COLUMNS IN PORTFOLIO ALLOCATION:')
print('='*80)
for i, col in enumerate(df.columns, 1):
    print(f'{i:2d}. {col}')

print('\n' + '='*80)
print(f'📊 FIRST STOCK ({df.iloc[0]["symbol"]}) - CHECKING ENHANCED COLUMNS:')
print('='*80)

# Check if our enhanced columns exist
enhanced_cols = [
    'improved_overall_score',
    'pe_ratio', 
    'roe',
    'debt_to_equity',
    '52_week_high',
    '52_week_low',
    'enhanced_price_change_20d',
    'support_level',
    'resistance_level',
    'enhanced_rsi_14',
    'volatility',
    'improved_fundamental_quality',
    'improved_momentum_technical'
]

missing_cols = []
present_cols = []

for col in enhanced_cols:
    if col in df.columns:
        value = df.iloc[0][col]
        present_cols.append(col)
        print(f'✅ {col:35s}: {value}')
    else:
        missing_cols.append(col)
        print(f'❌ {col:35s}: MISSING')

print('\n' + '='*80)
print('SUMMARY:')
print('='*80)
print(f'✅ Present: {len(present_cols)}/{len(enhanced_cols)} columns')
print(f'❌ Missing: {len(missing_cols)}/{len(enhanced_cols)} columns')

if missing_cols:
    print(f'\n⚠️  PROBLEM: Enhanced columns are NOT in the Excel file!')
    print(f'Missing columns: {", ".join(missing_cols)}')
    print(f'\n🔍 This means the allocation_data dictionary may not be populated correctly.')
else:
    print(f'\n🎉 SUCCESS: All enhanced columns are in the Excel file!')
