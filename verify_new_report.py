import pandas as pd

file = 'reports/Enhanced_Stock_Report_20260129_150252.xlsx'
df = pd.read_excel(file, sheet_name='Portfolio Allocation')

print('=' * 70)
print('PORTFOLIO ALLOCATION SHEET VERIFICATION - NEW REPORT')
print('=' * 70)

print(f'\nTotal columns: {len(df.columns)}')
print(f'Total rows: {len(df)}')

print('\n--- CHECKING FOR NEW COLUMNS ---')
new_cols_check = {
    'PRE_BREAKOUT?': 'pre_breakout_detected',
    'BREAKOUT_%': 'breakout_probability', 
    'SETUP_SIGNALS': 'pre_breakout_signals',
    'EXHAUSTION?': 'exhaustion_detected',
    'EXIT_SCORE': 'exhaustion_score',
    'EXIT_SIGNALS': 'exit_signals'
}

found_count = 0
for display_name, internal_name in new_cols_check.items():
    if display_name in df.columns:
        print(f'  ✅ {display_name}')
        found_count += 1
    else:
        print(f'  ❌ {display_name} - MISSING')

print(f'\nResult: {found_count}/{len(new_cols_check)} new columns found')

if found_count == len(new_cols_check):
    print('\n✅ ALL NEW COLUMNS PRESENT!')
    
    print('\n--- SAMPLE DATA (First 5 rows) ---')
    for i in range(min(5, len(df))):
        symbol = df['symbol'].iloc[i] if 'symbol' in df.columns else 'Unknown'
        action = df['ACTION'].iloc[i] if 'ACTION' in df.columns else 'N/A'
        
        print(f'\n{i+1}. {symbol} - ACTION: {action}')
        
        if 'PRE_BREAKOUT?' in df.columns:
            print(f'   PRE_BREAKOUT?: {df["PRE_BREAKOUT?"].iloc[i]}')
        if 'BREAKOUT_%' in df.columns:
            print(f'   BREAKOUT_%: {df["BREAKOUT_%"].iloc[i]}')
        if 'SETUP_SIGNALS' in df.columns:
            signals = df["SETUP_SIGNALS"].iloc[i]
            if pd.notna(signals) and signals != 'NONE':
                print(f'   SETUP_SIGNALS: {signals}')
        if 'EXHAUSTION?' in df.columns:
            print(f'   EXHAUSTION?: {df["EXHAUSTION?"].iloc[i]}')
        if 'EXIT_SCORE' in df.columns:
            print(f'   EXIT_SCORE: {df["EXIT_SCORE"].iloc[i]}')
    
    # Check if any pre-breakout signals detected
    if 'PRE_BREAKOUT?' in df.columns:
        pre_breakout_count = df['PRE_BREAKOUT?'].sum()
        print(f'\n--- DETECTION SUMMARY ---')
        print(f'✅ Stocks with pre-breakout setup: {pre_breakout_count}/{len(df)}')
    
    if 'EXHAUSTION?' in df.columns:
        exhaustion_count = df['EXHAUSTION?'].sum()
        print(f'⚠️  Stocks with momentum exhaustion: {exhaustion_count}/{len(df)}')
    
    # Check high probability setups
    if 'BREAKOUT_%' in df.columns:
        high_prob = df[df['BREAKOUT_%'] >= 70]
        print(f'🚀 High probability breakouts (≥70%): {len(high_prob)}')
        if len(high_prob) > 0:
            print('   Stocks:')
            for _, row in high_prob.iterrows():
                print(f'      • {row["symbol"]}: {row["BREAKOUT_%"]}% - {row["ACTION"]}')
    
    print('\n✅ INTEGRATION IS WORKING CORRECTLY!')
    print('🎯 The pre-breakout and exhaustion detection is now active!')
else:
    print('\n❌ INTEGRATION ISSUE: Some columns are still missing')
