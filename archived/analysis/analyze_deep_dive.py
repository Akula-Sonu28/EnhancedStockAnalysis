import pandas as pd

df = pd.read_excel('reports/Enhanced_Stock_Report_20251016_113112.xlsx', sheet_name='Portfolio Allocation')

print(f'=== DEEP DIVE RESULTS ===\n')
print(f'Total stocks: {df.shape[0]}')
print(f'Holdings: {df["HOLDING?"].sum()}')
print(f'New recommendations: {(~df["HOLDING?"]).sum()}\n')

print(f'=== ACTION Summary ===')
actions = df['ACTION'].value_counts()
print(actions)

print(f'\n=== TYPE (70/20/10) Summary ===')
types = df['TYPE'].value_counts()
print(types)

print(f'\n=== REASON Breakdown ===')
reasons = df['REASON'].str.extract(r'^([^:]+):', expand=False).value_counts()
print(reasons)

print(f'\n=== SELL Stocks ({len(df[df["ACTION"]=="SELL"])}) ===')
sells = df[df['ACTION']=='SELL'][['symbol', 'RANK', 'REASON', 'PROFIT_%', 'HOLDING?']].sort_values('RANK')
if len(sells) > 0:
    print(sells.to_string(index=False))
else:
    print("None")

print(f'\n=== INCREASE Stocks ({len(df[df["ACTION"]=="INCREASE"])}) ===')
increases = df[df['ACTION']=='INCREASE'][['symbol', 'RANK', 'INVEST_AMOUNT', 'REASON', 'HOLDING?']].sort_values('RANK')
if len(increases) > 0:
    print(increases.to_string(index=False))
else:
    print("None")

print(f'\n=== HOLD Stocks ({len(df[df["ACTION"]=="HOLD"])}) ===')
holds = df[df['ACTION']=='HOLD'][['symbol', 'RANK', 'REASON', 'PROFIT_%']].sort_values('RANK')
if len(holds) > 0:
    print(holds.to_string(index=False))
else:
    print("None")

print(f'\n=== New BUY Stocks ({len(df[df["ACTION"]=="BUY"])}) ===')
buys = df[(df['ACTION']=='BUY') & (~df['HOLDING?'])][['symbol', 'TYPE', 'INVEST_AMOUNT', 'REASON']]
if len(buys) > 0:
    print(buys.to_string(index=False))
else:
    print("None")

# Check portfolio weight
print(f'\n=== Portfolio Metrics ===')
print(f'Total portfolio weight: {df["WEIGHT_%"].sum():.2f}%')
holdings_weight = df[df['HOLDING?']]['WEIGHT_%'].sum()
print(f'Holdings weight: {holdings_weight:.2f}%')

# Check investment amounts
print(f'\n=== Capital Allocation ===')
total_investment = df['INVEST_AMOUNT'].sum()
increase_investment = df[df['ACTION']=='INCREASE']['INVEST_AMOUNT'].sum()
buy_investment = df[df['ACTION']=='BUY']['INVEST_AMOUNT'].sum()
print(f'Total capital: ₹{total_investment:,.0f}')
print(f'To existing (INCREASE): ₹{increase_investment:,.0f} ({increase_investment/total_investment*100:.1f}%)')
print(f'To new (BUY): ₹{buy_investment:,.0f} ({buy_investment/total_investment*100:.1f}%)')
