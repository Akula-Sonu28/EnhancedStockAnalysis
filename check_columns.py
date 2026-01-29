import pandas as pd
import sys

if len(sys.argv) > 1:
    file = sys.argv[1]
else:
    file = 'reports/Enhanced_Stock_Report_20260129_163006.xlsx'

df = pd.read_excel(file, sheet_name='Portfolio Allocation')
cols = df.columns.tolist()
print(f'Total columns: {len(cols)}')
print('\nAll columns:')
for i, col in enumerate(cols, 1):
    print(f'{i}. {col}')

print('\n\n📊 CHECKING FOR CONFLICT-RESOLVED ACTIONS:')
print('='*70)
if 'ACTION' in df.columns:
    print('✅ ACTION column found!')
    actions = df['ACTION'].unique()
    print(f'\nUnique ACTION values: {len(actions)}')
    for action in actions[:10]:
        print(f'  - {action}')
    
    # Check for conflict resolution emojis
    conflict_actions = df[df['ACTION'].astype(str).str.contains('⚠️|🟡|🟢', na=False, regex=True)]
    print(f'\n✅ Conflict-resolved actions: {len(conflict_actions)}')
    if not conflict_actions.empty:
        print(conflict_actions[['symbol', 'ACTION']].to_string(index=False))
else:
    print('❌ ACTION column NOT found!')
    print('\nLooking for similar columns...')
    similar = [c for c in cols if 'action' in c.lower() or 'recommend' in c.lower()]
    for col in similar:
        print(f'  - {col}')
