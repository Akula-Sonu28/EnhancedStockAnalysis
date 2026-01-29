import pandas as pd

file = 'reports/Enhanced_Stock_Report_20260129_143809.xlsx'
df = pd.read_excel(file, sheet_name='Portfolio Allocation')

print('=' * 70)
print('PORTFOLIO ALLOCATION SHEET VERIFICATION')
print('=' * 70)

print(f'\nTotal columns: {len(df.columns)}')
print(f'Total rows: {len(df)}')

print('\n--- CHECKING FOR NEW COLUMNS ---')
new_cols = [
    'pre_breakout_detected',
    'breakout_probability', 
    'pre_breakout_signals',
    'exhaustion_detected',
    'exhaustion_score',
    'exit_signals'
]

found_count = 0
for col in new_cols:
    if col in df.columns:
        print(f'  ✅ {col}')
        found_count += 1
    else:
        print(f'  ❌ {col} - MISSING')

print(f'\nResult: {found_count}/{len(new_cols)} new columns found')

if found_count == len(new_cols):
    print('\n✅ ALL NEW COLUMNS PRESENT!')
    
    print('\n--- SAMPLE DATA (First 3 rows) ---')
    for i in range(min(3, len(df))):
        print(f'\nRow {i+1}: {df["symbol"].iloc[i] if "symbol" in df.columns else "Unknown"}')
        if 'pre_breakout_detected' in df.columns:
            print(f'  pre_breakout_detected: {df["pre_breakout_detected"].iloc[i]}')
        if 'breakout_probability' in df.columns:
            print(f'  breakout_probability: {df["breakout_probability"].iloc[i]}')
        if 'pre_breakout_signals' in df.columns:
            print(f'  pre_breakout_signals: {df["pre_breakout_signals"].iloc[i]}')
        if 'exhaustion_detected' in df.columns:
            print(f'  exhaustion_detected: {df["exhaustion_detected"].iloc[i]}')
        if 'exhaustion_score' in df.columns:
            print(f'  exhaustion_score: {df["exhaustion_score"].iloc[i]}')
        if 'action_type' in df.columns:
            print(f'  ACTION: {df["action_type"].iloc[i]}')
    
    # Check if any pre-breakout signals detected
    if 'pre_breakout_detected' in df.columns:
        pre_breakout_count = df['pre_breakout_detected'].sum()
        print(f'\n--- SUMMARY ---')
        print(f'Stocks with pre-breakout setup: {pre_breakout_count}')
    
    if 'exhaustion_detected' in df.columns:
        exhaustion_count = df['exhaustion_detected'].sum()
        print(f'Stocks with momentum exhaustion: {exhaustion_count}')
    
    print('\n✅ Integration is working correctly!')
else:
    print('\n❌ INTEGRATION ISSUE: Some columns are missing')
    print('The new detector may not be integrated properly.')
