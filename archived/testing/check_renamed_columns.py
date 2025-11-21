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
print(f'📊 FIRST STOCK ({df.iloc[0]["symbol"]}) - CHECKING RENAMED COLUMNS:')
print('='*80)

# Check the RENAMED columns (as they appear in Excel)
renamed_cols = {
    'NEW_SCORE': 'improved_overall_score',
    'PE': 'pe_ratio', 
    'ROE_%': 'roe',
    'DEBT/EQUITY': 'debt_to_equity',
    '52W_HIGH': '52_week_high',
    '52W_LOW': '52_week_low',
    '20D_CHANGE_%': 'enhanced_price_change_20d',
    'SUPPORT': 'support_level',
    'RESISTANCE': 'resistance_level',
    'RSI': 'enhanced_rsi_14',
    'VOLATILITY_%': 'volatility',
    'FUND_SCORE': 'improved_fundamental_quality',
    'MOM_SCORE': 'improved_momentum_technical'
}

missing_cols = []
present_cols = []
empty_cols = []

for display_name, original_name in renamed_cols.items():
    if display_name in df.columns:
        value = df.iloc[0][display_name]
        present_cols.append(display_name)
        if pd.isna(value):
            empty_cols.append(display_name)
            print(f'⚠️  {display_name:20s}: PRESENT but EMPTY (None/NaN)')
        else:
            print(f'✅ {display_name:20s}: {value}')
    else:
        missing_cols.append(display_name)
        print(f'❌ {display_name:20s}: MISSING')

print('\n' + '='*80)
print('SUMMARY:')
print('='*80)
print(f'✅ Present:     {len(present_cols)}/{len(renamed_cols)} columns')
print(f'⚠️  Empty data:  {len(empty_cols)}/{len(renamed_cols)} columns')
print(f'❌ Missing:     {len(missing_cols)}/{len(renamed_cols)} columns')

if not missing_cols and not empty_cols:
    print(f'\n🎉 PERFECT! All enhanced columns are present with data!')
elif not missing_cols:
    print(f'\n⚠️  COLUMNS EXIST but have NO DATA!')
    print(f'Empty columns: {", ".join(empty_cols)}')
    print(f'\n🔍 This means stock_data.get() is returning None for these fields.')
    print(f'Check if stock analysis is populating these fields correctly.')
else:
    print(f'\n❌ PROBLEM: Some columns are completely missing!')
    print(f'Missing: {", ".join(missing_cols)}')
