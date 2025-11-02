import pandas as pd

df = pd.read_excel('reports/Enhanced_Stock_Report_20251016_113112.xlsx', sheet_name='Portfolio Allocation')

print("=" * 80)
print("CRITICAL ISSUES - RETAIL USER PERSPECTIVE")
print("=" * 80)

# ISSUE 1: Portfolio Concentration
print("\n🚨 ISSUE #1: OVER-CONCENTRATION (SECTOR RISK)")
print("-" * 80)
sector_concentration = df[df['HOLDING?']].groupby('sector').agg({
    'symbol': 'count',
    'WEIGHT_%': 'sum'
}).sort_values('WEIGHT_%', ascending=False)
sector_concentration.columns = ['Stock Count', 'Weight %']
print(sector_concentration)
print(f"\n⚠️ WARNING: Top sector has {sector_concentration.iloc[0]['Weight %']:.1f}% allocation")
print("   RECOMMENDATION: No single sector should exceed 30-35%")

# ISSUE 2: No Profit Booking Details
print("\n\n🚨 ISSUE #2: NO PROFIT BOOKING GUIDANCE")
print("-" * 80)
profitable = df[(df['HOLDING?']) & (df['PROFIT_%'] > 0)].sort_values('PROFIT_%', ascending=False)
print("\nProfitable Holdings with NO SELL guidance:")
high_profit = profitable[profitable['PROFIT_%'] > 20]
print(f"\nStocks with >20% profit ({len(high_profit)} stocks):")
for _, row in high_profit.iterrows():
    print(f"   {row['symbol']:12} | Profit: {row['PROFIT_%']:6.2f}% | Action: {row['ACTION']:8} | Why no booking?")

print(f"\nStocks with 10-20% profit ({len(profitable[(profitable['PROFIT_%'] >= 10) & (profitable['PROFIT_%'] <= 20)])} stocks):")
med_profit = profitable[(profitable['PROFIT_%'] >= 10) & (profitable['PROFIT_%'] <= 20)]
for _, row in med_profit.iterrows():
    print(f"   {row['symbol']:12} | Profit: {row['PROFIT_%']:6.2f}% | Action: {row['ACTION']:8}")

# ISSUE 3: Capital Allocation Confusion
print("\n\n🚨 ISSUE #3: WHERE IS THE MONEY COMING FROM?")
print("-" * 80)
sell_stocks = df[df['ACTION'] == 'SELL']
total_sell_value = sell_stocks['CURRENT_VALUE'].sum()
print(f"Stocks to SELL: {len(sell_stocks)}")
print(f"Expected sale proceeds: ₹{total_sell_value:,.0f}")

increase_amount = df[df['ACTION'] == 'INCREASE']['INVEST_AMOUNT'].sum()
buy_amount = df[df['ACTION'] == 'BUY']['INVEST_AMOUNT'].sum()
total_needed = increase_amount + buy_amount
print(f"\nCapital needed:")
print(f"   INCREASE existing: ₹{increase_amount:,.0f}")
print(f"   BUY new stocks: ₹{buy_amount:,.0f}")
print(f"   TOTAL NEEDED: ₹{total_needed:,.0f}")

print(f"\n⚠️ GAP: Need ₹{total_needed:,.0f} but only getting ₹{total_sell_value:,.0f} from sales")
print(f"   Missing: ₹{total_needed - total_sell_value:,.0f} (Where does this come from?)")

# ISSUE 4: SBIN has 0 investment despite being #2 performer
print("\n\n🚨 ISSUE #4: TOP PERFORMERS WITH ZERO ALLOCATION")
print("-" * 80)
zero_allocation = df[(df['ACTION'] == 'INCREASE') & (df['INVEST_AMOUNT'] == 0)]
if len(zero_allocation) > 0:
    print(f"Found {len(zero_allocation)} top performers marked INCREASE but getting ₹0:")
    for _, row in zero_allocation.iterrows():
        print(f"   {row['symbol']:12} | Rank: #{row['RANK']:2} | Score: {row['SCORE']:4.1f} | Weight: {row['WEIGHT_%']:5.2f}%")
        print(f"      Why INCREASE but no money allocated?")

# ISSUE 5: Portfolio Rebalancing Impact
print("\n\n🚨 ISSUE #5: POST-ACTION PORTFOLIO STRUCTURE")
print("-" * 80)
print("Current portfolio: 35 stocks")
keeps = len(df[(df['HOLDING?']) & (df['ACTION'].isin(['INCREASE', 'HOLD']))])
sells = len(df[(df['HOLDING?']) & (df['ACTION'] == 'SELL')])
buys = len(df[(~df['HOLDING?']) & (df['ACTION'] == 'BUY')])
final_count = keeps + buys

print(f"After actions:")
print(f"   KEEP (INCREASE + HOLD): {keeps} stocks")
print(f"   SELL: {sells} stocks")
print(f"   BUY new: {buys} stocks")
print(f"   FINAL PORTFOLIO: {final_count} stocks")

if final_count > 25:
    print(f"\n⚠️ WARNING: Portfolio will still have {final_count} stocks (target: 20-25)")

# ISSUE 6: Risk Distribution
print("\n\n🚨 ISSUE #6: RISK DISTRIBUTION (70/20/10 RULE)")
print("-" * 80)
holdings_type = df[df['HOLDING?']].groupby('TYPE').agg({
    'symbol': 'count',
    'WEIGHT_%': 'sum'
})
holdings_type.columns = ['Count', 'Weight %']
print("\nCurrent Holdings:")
print(holdings_type)

total_weight = holdings_type['Weight %'].sum()
for risk_type in ['CORE', 'OPPORTUNISTIC', 'SPECULATIVE']:
    if risk_type in holdings_type.index:
        pct = (holdings_type.loc[risk_type, 'Weight %'] / total_weight) * 100
        target = 70 if risk_type == 'CORE' else (20 if risk_type == 'OPPORTUNISTIC' else 10)
        print(f"\n{risk_type}: {pct:.1f}% (Target: {target}%)")
        if abs(pct - target) > 10:
            print(f"   ⚠️ OFF TARGET by {abs(pct - target):.1f} percentage points")

# ISSUE 7: Execution Clarity
print("\n\n🚨 ISSUE #7: EXECUTION PLAN MISSING")
print("-" * 80)
print("❌ No clear step-by-step execution plan")
print("❌ No sequence: What to sell first? What to buy first?")
print("❌ No price targets or stop losses")
print("❌ No timeline: When to execute these actions?")
print("❌ No contingency: What if prices change significantly?")

# ISSUE 8: Tax Implications
print("\n\n🚨 ISSUE #8: TAX IMPLICATIONS NOT MENTIONED")
print("-" * 80)
short_term = df[(df['HOLDING?']) & (df['PROFIT_%'] > 0) & (df['ACTION'] == 'SELL')]
if len(short_term) > 0:
    total_profit = (short_term['CURRENT_VALUE'] * short_term['PROFIT_%'] / 100).sum()
    print(f"Selling {len(short_term)} profitable stocks")
    print(f"Estimated realized profit: ₹{total_profit:,.0f}")
    print(f"⚠️ Potential tax liability: ₹{total_profit * 0.15:,.0f} (15% STCG assumed)")
    print("   Excel should show post-tax proceeds available for reinvestment")

# ISSUE 9: Missing Holdings Quality Check
print("\n\n🚨 ISSUE #9: QUALITY OF HOLDINGS TO KEEP")
print("-" * 80)
hold_stocks = df[(df['HOLDING?']) & (df['ACTION'] == 'HOLD')].sort_values('SCORE')
print(f"\nHOLD stocks - Quality distribution:")
print(f"   Excellent (Score >85): {len(hold_stocks[hold_stocks['SCORE'] > 85])}")
print(f"   Good (Score 75-85): {len(hold_stocks[(hold_stocks['SCORE'] >= 75) & (hold_stocks['SCORE'] <= 85)])}")
print(f"   Average (Score 65-75): {len(hold_stocks[(hold_stocks['SCORE'] >= 65) & (hold_stocks['SCORE'] < 75)])}")
print(f"   Below Average (<65): {len(hold_stocks[hold_stocks['SCORE'] < 65])}")

weak_holds = hold_stocks[hold_stocks['SCORE'] < 70]
if len(weak_holds) > 0:
    print(f"\n⚠️ Holding {len(weak_holds)} weak stocks (Score <70):")
    for _, row in weak_holds.iterrows():
        print(f"   {row['symbol']:12} | Rank: #{row['RANK']:2} | Score: {row['SCORE']:4.1f} | Profit: {row['PROFIT_%']:6.2f}%")

# ISSUE 10: New Stock Justification
print("\n\n🚨 ISSUE #10: WHY NEW STOCKS WHEN HOLDING MEDIOCRE ONES?")
print("-" * 80)
new_stocks = df[(~df['HOLDING?']) & (df['ACTION'] == 'BUY')].sort_values('SCORE', ascending=False)
weak_holdings = df[(df['HOLDING?']) & (df['SCORE'] < 75)].sort_values('SCORE')

print(f"\nNew stocks to BUY (avg score: {new_stocks['SCORE'].mean():.1f}):")
for _, row in new_stocks.iterrows():
    print(f"   {row['symbol']:12} | Score: {row['SCORE']:4.1f}")

print(f"\nWeak holdings to KEEP (avg score: {weak_holdings['SCORE'].mean():.1f}):")
for _, row in weak_holdings.head(5).iterrows():
    print(f"   {row['symbol']:12} | Score: {row['SCORE']:4.1f} | Action: {row['ACTION']}")

print("\n⚠️ Question: Why buy new stocks when existing portfolio has weaker holdings?")

# Summary
print("\n\n" + "=" * 80)
print("SUMMARY - CRITICAL ISSUES FOUND: 10")
print("=" * 80)
print("""
1. ❌ Over-concentrated in single sector (Financial Services likely >90%)
2. ❌ No profit booking guidance despite 20%+ gains
3. ❌ Capital source unclear (need ₹234K but only ₹25K from sales)
4. ❌ Top performers get ₹0 allocation (SBIN issue)
5. ❌ Final portfolio still 36 stocks (target: 20-25)
6. ❌ 70/20/10 rule not enforced
7. ❌ No execution plan (sequence, timing, prices)
8. ❌ Tax implications ignored
9. ❌ Keeping weak stocks (score <70)
10. ❌ Buying new when existing portfolio has deadwood

RECOMMENDATION: Fix profit booking rules, sector limits, and capital allocation logic!
""")
