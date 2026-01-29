"""
Analyze why low exhaustion stocks didn't get investment allocation
"""
import pandas as pd

df = pd.read_excel('reports/Enhanced_Stock_Report_20260129_180753.xlsx', sheet_name='Portfolio Allocation')

print("="*80)
print("📊 INVESTMENT ALLOCATION ANALYSIS")
print("="*80)

# Focus on stocks with low/moderate exhaustion and action-oriented recommendations
focus_stocks = df[
    (df['EXIT_SCORE'] < 60) & 
    (df['ACTION'].isin(['INCREASE', 'BUY', 'NEW POSITION']) | 
     df['ACTION'].str.contains('ENTER|SMALL', na=False))
].copy()

print(f"\nStocks with low/moderate exhaustion & buy/increase actions: {len(focus_stocks)}")
print("\n" + "-"*80)

for _, row in focus_stocks.sort_values('EXIT_SCORE').iterrows():
    symbol = row['symbol']
    action = row['ACTION']
    invest = row['INVEST_₹']
    score = row['SCORE']
    exit_score = row['EXIT_SCORE']
    rank = row.get('RANK', 'N/A')
    
    got_funds = "✅" if invest > 0 else "❌"
    
    print(f"{got_funds} {symbol:12} | Exit:{exit_score:3.0f} Score:{score:5.1f} Rank:{rank:3} | {action:30} | ₹{invest:,.0f}")

print("\n" + "="*80)
print("🔍 DETAILED ANALYSIS OF MISSED OPPORTUNITIES")
print("="*80)

missed = focus_stocks[focus_stocks['INVEST_₹'] == 0].sort_values('SCORE', ascending=False)

print(f"\nStocks with ₹0 investment: {len(missed)}")
print("\nTop missed by score:")
print("-"*80)

for _, row in missed.head(10).iterrows():
    print(f"\n{row['symbol']} (Score: {row['SCORE']:.1f}, Exit: {row['EXIT_SCORE']:.0f})")
    print(f"  Action: {row['ACTION']}")
    print(f"  Current holding: {row.get('I_OWN_IT?', False)}")
    print(f"  Current value: ₹{row.get('MY_VALUE_₹', 0):,.0f}")
    print(f"  Rank: {row.get('RANK', 'N/A')}")
    
    # Check why it might have been skipped
    reasons = []
    
    if row.get('I_OWN_IT?', False) and row['ACTION'] == 'HOLD':
        reasons.append("❌ HOLD action = no change needed")
    
    if row.get('I_OWN_IT?', False) and row['ACTION'] == 'INCREASE' and row['MY_VALUE_₹'] > 50000:
        reasons.append("⚠️ May be at allocation cap already")
    
    if not row.get('I_OWN_IT?', False) and 'ENTER' in row['ACTION']:
        reasons.append("⚠️ Conflict-resolved ENTER with emoji - may have been filtered")
    
    if reasons:
        for reason in reasons:
            print(f"  {reason}")

print("\n" + "="*80)
print("📈 ALLOCATION DISTRIBUTION")
print("="*80)

all_invested = df[df['INVEST_₹'] > 0].sort_values('INVEST_₹', ascending=False)
print(f"\nTotal stocks that got investment: {len(all_invested)}")
print(f"Total allocated: ₹{all_invested['INVEST_₹'].sum():,.0f}")

print("\nBreakdown by action type:")
for action_type in all_invested['ACTION'].unique():
    subset = all_invested[all_invested['ACTION'] == action_type]
    total = subset['INVEST_₹'].sum()
    count = len(subset)
    avg = total / count if count > 0 else 0
    print(f"  {action_type:30} : {count:2} stocks | Total: ₹{total:8,.0f} | Avg: ₹{avg:8,.0f}")
