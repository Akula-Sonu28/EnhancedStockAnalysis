import pandas as pd

df = pd.read_excel('reports/Enhanced_Stock_Report_20251016_121429.xlsx', sheet_name='Portfolio Allocation')

print("=" * 100)
print("VERIFICATION OF ALL CRITICAL ISSUE FIXES")
print("=" * 100)

print(f"\nTotal rows: {len(df)}")
print(f"Columns: {list(df.columns)}\n")

print("=" * 100)
print("FIX #1: PROFIT BOOKING (>20% gains)")
print("=" * 100)

# Check if profit booking columns exist
if 'BOOK_%' in df.columns and 'WHEN_TO_SELL' in df.columns:
    print("✅ Profit booking columns added!")
    
    # Check for BOOK_PROFIT action or profit booking data
    profit_booking = df[(df['BOOK_%'].notna()) & (df['BOOK_%'] > 0)]
    
    if len(profit_booking) > 0:
        print(f"\n{len(profit_booking)} stocks marked for profit booking:")
        print(f"\n{'Stock':<12} {'Profit %':>10} {'Book %':>8} {'Timing':<20} {'Action'}")
        print("-" * 70)
        for _, row in profit_booking.iterrows():
            print(f"{row['symbol']:<12} {row['PROFIT_%']:>9.2f}% {row['BOOK_%']:>7.0f}% {str(row['WHEN_TO_SELL']):<20} {row['ACTION']}")
    else:
        print("⚠️ No stocks marked for profit booking (columns exist but empty)")
        
        # Check high profit stocks
        high_profit = df[(df['HOLDING?']) & (df['PROFIT_%'] > 20)]
        if len(high_profit) > 0:
            print(f"\n⚠️ Found {len(high_profit)} stocks with >20% profit but no booking:")
            for _, row in high_profit.iterrows():
                print(f"   {row['symbol']}: {row['PROFIT_%']:.2f}% | Action: {row['ACTION']}")
else:
    print("❌ Profit booking columns NOT found")

print("\n\n" + "=" * 100)
print("FIX #2: EXECUTION TIMING FOR SELL")
print("=" * 100)

sell_stocks = df[df['ACTION'] == 'SELL']
if len(sell_stocks) > 0:
    print(f"\n{len(sell_stocks)} stocks to SELL with timing:")
    print(f"\n{'Stock':<12} {'Profit %':>10} {'Timing':<25} {'Reason'}")
    print("-" * 90)
    for _, row in sell_stocks.iterrows():
        timing = str(row.get('WHEN_TO_SELL', 'Not specified'))
        reason_short = str(row['REASON']).split('|')[0].strip()
        print(f"{row['symbol']:<12} {row['PROFIT_%']:>9.2f}% {timing:<25} {reason_short}")
    
    # Check if timing is populated
    with_timing = sell_stocks[sell_stocks['WHEN_TO_SELL'].notna()]
    if len(with_timing) == 0:
        print(f"\n⚠️ SELL actions found but WHEN_TO_SELL not populated!")
    else:
        print(f"\n✅ {len(with_timing)}/{len(sell_stocks)} SELL actions have timing")
else:
    print("No SELL actions found")

print("\n\n" + "=" * 100)
print("FIX #3: SECTOR CONCENTRATION CHECK")
print("=" * 100)

holdings = df[df['HOLDING?']].copy()
if not holdings.empty:
    # Overall sector concentration
    sector_dist = holdings.groupby('sector').agg({
        'symbol': 'count',
        'WEIGHT_%': 'sum'
    }).sort_values('WEIGHT_%', ascending=False)
    sector_dist.columns = ['Count', 'Weight %']
    
    print("\nOverall sector distribution:")
    print(sector_dist)
    
    top_sector = sector_dist.iloc[0]
    print(f"\n⚠️ Top sector: {sector_dist.index[0]} = {top_sector['Weight %']:.1f}%")
    
    if top_sector['Weight %'] > 50:
        print(f"   OVER 50% LIMIT! Should trigger rotation.")
        
        # Check if sector rotation SELLs were added
        fin_services_sells = df[(df['sector'] == sector_dist.index[0]) & 
                                 (df['ACTION'] == 'SELL') & 
                                 (df['REASON'].str.contains('SECTOR ROTATION', na=False))]
        
        if len(fin_services_sells) > 0:
            print(f"   ✅ {len(fin_services_sells)} stocks marked for SECTOR ROTATION")
            for _, row in fin_services_sells.iterrows():
                print(f"      {row['symbol']}: {row['REASON'][:60]}")
        else:
            print(f"   ⚠️ No stocks marked for sector rotation despite over-concentration")
    else:
        print(f"   ✅ Within 50% limit")
    
    # CORE sector distribution
    core_holdings = holdings[holdings['TYPE'] == 'CORE']
    if not core_holdings.empty:
        core_sector = core_holdings.groupby('sector')['WEIGHT_%'].sum().sort_values(ascending=False)
        core_total = core_holdings['WEIGHT_%'].sum()
        
        print(f"\n\nCORE (70%) sector distribution:")
        for sector, weight in core_sector.head(3).items():
            sector_pct = (weight / core_total * 100) if core_total > 0 else 0
            status = "✅" if sector_pct <= 50 else "⚠️"
            print(f"   {status} {sector}: {sector_pct:.1f}% of CORE")

print("\n\n" + "=" * 100)
print("FIX #4: PORTFOLIO SIZE REDUCTION")
print("=" * 100)

current_count = len(holdings)
sell_count = len(df[(df['HOLDING?']) & (df['ACTION'] == 'SELL')])
buy_count = len(df[(~df['HOLDING?']) & (df['ACTION'] == 'BUY')])
final_count = current_count - sell_count + buy_count

print(f"Current holdings: {current_count}")
print(f"To SELL: {sell_count}")
print(f"To BUY: {buy_count}")
print(f"Final portfolio: {final_count} stocks")

if final_count <= 25:
    print(f"✅ Within target (20-25 stocks)")
elif final_count <= 30:
    print(f"⚠️ Close to target but still {final_count - 25} stocks over")
else:
    print(f"❌ Still {final_count - 25} stocks over target")

print("\n\n" + "=" * 100)
print("FIX #5: CAPITAL ALLOCATION MATH")
print("=" * 100)

total_investment = df['INVEST_AMOUNT'].sum()
increase_investment = df[df['ACTION'] == 'INCREASE']['INVEST_AMOUNT'].sum()
buy_investment = df[df['ACTION'] == 'BUY']['INVEST_AMOUNT'].sum()

# Calculate expected sale proceeds
sell_value = df[df['ACTION'] == 'SELL']['CURRENT_VALUE'].sum()

# Calculate profit booking proceeds
if 'BOOK_%' in df.columns:
    profit_book_proceeds = 0
    for _, row in df[df['BOOK_%'].notna()].iterrows():
        if row['BOOK_%'] > 0:
            profit_book_proceeds += row['CURRENT_VALUE'] * row['BOOK_%'] / 100
else:
    profit_book_proceeds = 0

total_available = sell_value + profit_book_proceeds

print(f"Capital needed:")
print(f"   INCREASE existing: ₹{increase_investment:,.0f}")
print(f"   BUY new: ₹{buy_investment:,.0f}")
print(f"   TOTAL: ₹{total_investment:,.0f}")

print(f"\nCapital available:")
print(f"   From SELL: ₹{sell_value:,.0f}")
print(f"   From profit booking: ₹{profit_book_proceeds:,.0f}")
print(f"   TOTAL: ₹{total_available:,.0f}")

gap = total_investment - total_available
if abs(gap) < 10000:
    print(f"\n✅ Capital allocation balanced (gap: ₹{gap:,.0f})")
elif gap > 0:
    print(f"\n⚠️ Need ₹{gap:,.0f} more capital")
else:
    print(f"\n✅ Surplus of ₹{-gap:,.0f}")

print("\n\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"""
FIXES IMPLEMENTED:
1. Profit Booking: {len(profit_booking) if 'profit_booking' in locals() else 0} stocks marked
2. Execution Timing: {len(sell_stocks)} SELL actions
3. Sector Concentration: Top sector {top_sector['Weight %']:.1f}%
4. Portfolio Size: {final_count} stocks (target: 20-25)
5. Capital Allocation: ₹{total_investment:,.0f} vs ₹{total_available:,.0f}
""")
