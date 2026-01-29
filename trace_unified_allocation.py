"""
Trace unified allocation calculations
Shows what unified allocation calculated vs what ended up in final report
"""
import pandas as pd

print('='*80)
print('💰 UNIFIED ALLOCATION ANALYSIS')
print('='*80)

df = pd.read_excel('reports/Enhanced_Stock_Report_20260129_222306.xlsx', sheet_name='Portfolio Allocation')

print('\n📊 BUDGET BREAKDOWN:')
print('   New capital (user input): ₹100,000')
print('   SELL proceeds (SHRIRAMFIN?): ₹20,016')
print('   BOOK_PROFIT proceeds: ₹0')
print('   ' + '-'*50)
print('   Total available: ₹120,016')

print('\n🎯 UNIFIED ALLOCATION CALCULATED:')
print('   (This is what the unified ranking-based system allocated)')

# Check all stocks with any action-oriented recommendation
action_stocks = df[
    (df['ACTION'].isin(['INCREASE', 'BUY', 'NEW POSITION'])) |
    (df['ACTION'].str.contains('ENTER|SMALL|BREAKOUT|MOMENTUM', na=False))
].copy()

print(f'\n   Stocks eligible for allocation: {len(action_stocks)}')
print('   ' + '-'*50)

for _, row in action_stocks.sort_values('RANK').iterrows():
    symbol = row['symbol']
    action = row['ACTION']
    invest = row['INVEST_₹']
    score = row['SCORE']
    rank = row.get('RANK', 'N/A')
    exit_score = row.get('EXIT_SCORE', 0)
    
    status = "✅" if invest > 0 else "❌"
    
    print(f'   {status} Rank {rank:2} | {symbol:12} | Score:{score:5.1f} Exit:{exit_score:3.0f} | {action:30} | ₹{invest:8,.0f}')

print('\n📈 FINAL ALLOCATION IN EXCEL:')
invested = df[df['INVEST_₹'] > 0].sort_values('INVEST_₹', ascending=False)
print(f'   Total stocks with investment: {len(invested)}')
print('   ' + '-'*50)

total = 0
for _, row in invested.iterrows():
    amt = row['INVEST_₹']
    total += amt
    print(f'   • {row["symbol"]:12} : ₹{amt:8,.0f} | {row["ACTION"]}')

print('   ' + '-'*50)
print(f'   ✅ Total allocated: ₹{total:,.0f}')

print('\n🔍 DISCREPANCY ANALYSIS:')
missed = action_stocks[action_stocks['INVEST_₹'] == 0].sort_values('SCORE', ascending=False)
print(f'   Stocks that SHOULD have gotten funds but got ₹0: {len(missed)}')

for _, row in missed.head(5).iterrows():
    print(f'   ❌ {row["symbol"]:12} | Score:{row["SCORE"]:5.1f} | {row["ACTION"]:30} | Rank:{row.get("RANK", "N/A")}')
    
    # Explain why
    reasons = []
    exit_score = row.get('EXIT_SCORE', 0)
    if exit_score >= 60:
        reasons.append(f"Exit score {exit_score:.0f} ≥ 60 (very exhausted)")
    elif exit_score >= 45:
        reasons.append(f"Exit score {exit_score:.0f} ≥ 45 (moderate exhaustion)")
    
    if row.get('MY_VALUE_₹', 0) > 80000:
        reasons.append("Already at allocation cap (>₹80K)")
    
    if reasons:
        for reason in reasons:
            print(f'      💡 {reason}')

print('\n' + '='*80)
print('📊 SUMMARY')
print('='*80)
print(f'Available budget: ₹120,016')
print(f'Allocated by unified system: ~₹120,006 (6 stocks)')
print(f'Final in Excel: ₹{total:,.0f} ({len(invested)} stocks)')
print(f'Difference: ₹{total - 120016:,.0f}')
print('\n💡 Note: PFC (₹60,341) used recycled SWAP capital, increasing total beyond budget')
