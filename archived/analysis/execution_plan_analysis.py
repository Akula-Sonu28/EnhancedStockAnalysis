import pandas as pd
from datetime import datetime, timedelta

df = pd.read_excel('reports/Enhanced_Stock_Report_20251016_113112.xlsx', sheet_name='Portfolio Allocation')

print("=" * 100)
print("EXECUTION PLAN - WHEN TO SELL & BOOK PROFITS")
print("=" * 100)

holdings = df[df['HOLDING?']].copy()

# STEP 1: Identify stocks to sell
print("\n" + "=" * 100)
print("STEP 1: IMMEDIATE SELLS (Execute within 1-2 trading days)")
print("=" * 100)

sell_stocks = holdings[holdings['ACTION'] == 'SELL'].sort_values('RANK', ascending=False)
print(f"\n{'Priority':<10} {'Stock':<12} {'Reason':<35} {'Profit %':<10} {'Value':<12} {'When?'}")
print("-" * 100)

priority = 1
total_sell_value = 0
for _, row in sell_stocks.iterrows():
    reason_short = row['REASON'].split('|')[0].strip()
    timing = "TODAY" if row['PROFIT_%'] < 0 else "Next 2 days"
    print(f"Priority {priority:<3} {row['symbol']:<12} {reason_short:<35} {row['PROFIT_%']:>8.2f}% ₹{row['CURRENT_VALUE']:>10,.0f}  {timing}")
    total_sell_value += row['CURRENT_VALUE']
    priority += 1

print(f"\nTotal from immediate sells: ₹{total_sell_value:,.0f}")

# STEP 2: Profit booking candidates
print("\n\n" + "=" * 100)
print("STEP 2: PROFIT BOOKING CANDIDATES (>20% gains)")
print("=" * 100)
print("Strategy: Book 30-50% profit, keep 70-50% for long term")
print("-" * 100)

profit_booking = holdings[holdings['PROFIT_%'] > 20].sort_values('PROFIT_%', ascending=False)
print(f"\n{'Stock':<12} {'Current':<10} {'Profit %':<10} {'Book %':<10} {'Sell Value':<12} {'Keep Value':<12} {'When?'}")
print("-" * 100)

total_profit_book_value = 0
for _, row in profit_booking.iterrows():
    current_val = row['CURRENT_VALUE']
    
    # Profit booking rule: 30% at 20-30%, 40% at 30-40%, 50% at >40%
    if row['PROFIT_%'] > 40:
        book_pct = 50
        timing = "Within 1 week"
    elif row['PROFIT_%'] > 30:
        book_pct = 40
        timing = "Within 2 weeks"
    else:
        book_pct = 30
        timing = "Within 3 weeks"
    
    sell_val = current_val * book_pct / 100
    keep_val = current_val - sell_val
    
    print(f"{row['symbol']:<12} ₹{current_val:>8,.0f} {row['PROFIT_%']:>8.2f}% {book_pct:>8}%  ₹{sell_val:>10,.0f} ₹{keep_val:>10,.0f}  {timing}")
    total_profit_book_value += sell_val

print(f"\nTotal from profit booking: ₹{total_profit_book_value:,.0f}")

# STEP 3: Underperformers to free up capital
print("\n\n" + "=" * 100)
print("STEP 3: UNDERPERFORMERS TO CONSIDER SELLING (Reduce portfolio size)")
print("=" * 100)
print("Current: 35 stocks → Target: 20-25 stocks")
print("Need to sell: 10-15 more stocks beyond current 4 SELL recommendations")
print("-" * 100)

# Bottom performers that are currently HOLD
bottom_performers = holdings[holdings['ACTION'] == 'HOLD'].sort_values('RANK', ascending=False).head(12)
print(f"\n{'Stock':<12} {'Rank':<8} {'Score':<8} {'Profit %':<10} {'Value':<12} {'Consider?'}")
print("-" * 100)

consider_sell_value = 0
for _, row in bottom_performers.iterrows():
    # Criteria to consider selling: Low score OR small position OR near breakeven
    consider = ""
    if row['SCORE'] < 70:
        consider = "❌ Weak score"
    elif abs(row['PROFIT_%']) < 2:
        consider = "⚠️ Dead money"
    elif row['WEIGHT_%'] < 2:
        consider = "💼 Small position"
    else:
        consider = "🤔 Review"
    
    print(f"{row['symbol']:<12} #{row['RANK']:<7.0f} {row['SCORE']:<8.1f} {row['PROFIT_%']:>8.2f}% ₹{row['CURRENT_VALUE']:>10,.0f}  {consider}")
    if consider in ["❌ Weak score", "⚠️ Dead money"]:
        consider_sell_value += row['CURRENT_VALUE']

print(f"\nPotential additional capital: ₹{consider_sell_value:,.0f}")

# STEP 4: Total capital available
print("\n\n" + "=" * 100)
print("STEP 4: TOTAL CAPITAL AVAILABLE FOR REALLOCATION")
print("=" * 100)

total_capital = total_sell_value + total_profit_book_value + consider_sell_value
print(f"\nFrom immediate sells:        ₹{total_sell_value:>10,.0f}")
print(f"From profit booking (30-50%): ₹{total_profit_book_value:>10,.0f}")
print(f"From underperformers:        ₹{consider_sell_value:>10,.0f}")
print("-" * 50)
print(f"TOTAL AVAILABLE:             ₹{total_capital:>10,.0f}")

print(f"\nAllocation strategy:")
print(f"   80% to existing winners:  ₹{total_capital * 0.8:>10,.0f}")
print(f"   20% to new opportunities: ₹{total_capital * 0.2:>10,.0f}")

# STEP 5: Sector rotation opportunity
print("\n\n" + "=" * 100)
print("STEP 5: SECTOR ROTATION ANALYSIS")
print("=" * 100)

current_sector = holdings.groupby('sector').agg({
    'symbol': 'count',
    'WEIGHT_%': 'sum'
}).sort_values('WEIGHT_%', ascending=False)
current_sector.columns = ['Count', 'Weight %']

print("\nCurrent sector allocation:")
print(current_sector)

fin_services_pct = current_sector.loc['Financial Services', 'Weight %']
print(f"\n⚠️ Financial Services: {fin_services_pct:.1f}% (Max allowed in CORE 70%: 50%)")
if fin_services_pct > 50:
    excess = fin_services_pct - 50
    print(f"   Need to reduce by {excess:.1f}% through rotation")

# Check which new stocks are in different sectors
new_stocks = df[(~df['HOLDING?']) & (df['ACTION'] == 'BUY')]
print(f"\nNew recommendations by sector:")
new_sector = new_stocks.groupby('sector').agg({
    'symbol': 'count',
    'INVEST_AMOUNT': 'sum'
})
new_sector.columns = ['Count', 'Amount']
print(new_sector)

# STEP 6: Execution sequence
print("\n\n" + "=" * 100)
print("STEP 6: EXECUTION SEQUENCE (Day-by-Day Plan)")
print("=" * 100)

today = datetime.now()
print(f"\n📅 Starting from: {today.strftime('%d-%b-%Y')}")
print("-" * 100)

day = 0
print(f"\n{'Day':<6} {'Date':<12} {'Action':<60} {'Capital'}")
print("-" * 100)

# Day 0: Sell losers first
if len(sell_stocks[sell_stocks['PROFIT_%'] < 0]) > 0:
    loss_stocks = ', '.join(sell_stocks[sell_stocks['PROFIT_%'] < 0]['symbol'].tolist())
    loss_value = sell_stocks[sell_stocks['PROFIT_%'] < 0]['CURRENT_VALUE'].sum()
    print(f"Day {day:<3} {today.strftime('%d-%b-%Y'):<12} SELL losers: {loss_stocks:<40} +₹{loss_value:>8,.0f}")
    day += 1

# Day 1-2: Sell weak fundamentals
if len(sell_stocks[sell_stocks['PROFIT_%'] >= 0]) > 0:
    weak_stocks = ', '.join(sell_stocks[sell_stocks['PROFIT_%'] >= 0]['symbol'].tolist())
    weak_value = sell_stocks[sell_stocks['PROFIT_%'] >= 0]['CURRENT_VALUE'].sum()
    next_day = today + timedelta(days=1)
    print(f"Day {day:<3} {next_day.strftime('%d-%b-%Y'):<12} SELL weak stocks: {weak_stocks:<38} +₹{weak_value:>8,.0f}")
    day += 2

# Day 3: Review and place GTT orders for profit booking
gtt_day = today + timedelta(days=3)
print(f"Day {day:<3} {gtt_day.strftime('%d-%b-%Y'):<12} Place GTT orders for profit booking (30-50% quantities)    Review")
day += 1

# Day 4-5: Start buying strong performers
buy_day = today + timedelta(days=4)
print(f"Day {day:<3} {buy_day.strftime('%d-%b-%Y'):<12} INCREASE top performers (allocate 80% of available capital)   -₹{total_capital * 0.8:>8,.0f}")
day += 2

# Day 6-7: Buy new opportunities
new_day = today + timedelta(days=6)
print(f"Day {day:<3} {new_day.strftime('%d-%b-%Y'):<12} BUY new stocks (allocate 20% of available capital)          -₹{total_capital * 0.2:>8,.0f}")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"""
✅ SELL SEQUENCE:
   1. Losers first (lock losses, claim tax benefit)
   2. Weak fundamentals next (free up capital)
   3. Profit booking via GTT (gradual, automated)

✅ BUY SEQUENCE:
   1. Strengthen existing winners (80% capital)
   2. Add new quality stocks (20% capital)

✅ TIMING:
   - Immediate sells: 1-2 days
   - Profit booking: 1-3 weeks (staggered via GTT)
   - Reallocation: After capital is freed up

✅ PORTFOLIO IMPACT:
   - Current: 35 stocks
   - After action: ~25 stocks (target achieved)
   - Sector diversification: Rotate from Financial Services to new sectors
""")
