"""
Generate Action Plan from Latest Portfolio Report - ACCURATE VERSION
"""
import pandas as pd

# Load latest report
df = pd.read_excel('reports/Enhanced_Stock_Report_20260130_113236.xlsx', sheet_name='Portfolio Allocation')

print('\n' + '='*120)
print('📋 YOUR ACCURATE ACTION PLAN - EXECUTE IN THIS ORDER')
print('='*120)

# PRIORITY 1: SWAP POSITIONS (Sell + Buy simultaneously)
swaps = df[df['ACTION'].str.contains('SWAP', na=False)].sort_values('MY_VALUE_₹', ascending=False)
if len(swaps) > 0:
    print('\n🔄 PRIORITY 1: SWAP POSITIONS (Sell + Buy Simultaneously)')
    print('-'*120)
    swap_total = 0
    for _, row in swaps.iterrows():
        symbol = row['symbol']
        shares = row['MY_SHARES']
        price = row['PRICE']
        value = row['MY_VALUE_₹']
        action = row['ACTION']
        target = action.split('->')[1].strip() if '->' in action else 'Unknown'
        print(f'   🔄 SELL {symbol:12s} ({shares:>4.0f} shares @ ₹{price:>7.2f}) → Get ₹{value:>9,.0f}')
        print(f'      ➡️  Immediately BUY {target} with proceeds')
        swap_total += value
    print(f'\n   💵 Total SWAP Capital: ₹{swap_total:,.0f}')

# PRIORITY 2: EXHAUSTED POSITIONS (Sell immediately - high risk)
exhausted = df[(df['ACTION'].str.contains('EXHAUSTED', na=False)) & (~df['ACTION'].str.contains('SWAP', na=False))].sort_values('MY_VALUE_₹', ascending=False)
if len(exhausted) > 0:
    print('\n\n⚠️  PRIORITY 2: EXHAUSTED POSITIONS (Sell Immediately - High Risk)')
    print('-'*120)
    exhausted_total = 0
    for _, row in exhausted.iterrows():
        symbol = row['symbol']
        shares = row['MY_SHARES']
        price = row['PRICE']
        value = row['MY_VALUE_₹']
        print(f'   ❌ SELL {symbol:12s} | Sell ALL {shares:>4.0f} shares @ ₹{price:>7.2f} → Get ₹{value:>9,.0f}')
        print(f'      ⚠️  Reason: Momentum exhausted, high correction risk')
        exhausted_total += value
    print(f'\n   💵 Total EXHAUSTED Proceeds: ₹{exhausted_total:,.0f}')

# PRIORITY 3: BOOK PARTIAL PROFITS (50-60%)
book_profit = df[(df['ACTION'].str.contains('BOOK', na=False)) & (df['MY_VALUE_₹'] > 0)].sort_values('MY_VALUE_₹', ascending=False)
if len(book_profit) > 0:
    print('\n\n🟡 PRIORITY 3: BOOK PARTIAL PROFITS (Sell 50-60% Only - Keep Rest)')
    print('-'*120)
    book_total = 0
    for _, row in book_profit.iterrows():
        symbol = row['symbol']
        current_shares = row['MY_SHARES']
        price = row['PRICE']
        current_value = row['MY_VALUE_₹']
        # Calculate 50-60% range
        sell_shares_min = int(current_shares * 0.50)
        sell_shares_max = int(current_shares * 0.60)
        proceeds_min = sell_shares_min * price
        proceeds_max = sell_shares_max * price
        keep_shares_min = current_shares - sell_shares_max
        keep_shares_max = current_shares - sell_shares_min
        
        print(f'   🟡 BOOK {symbol:12s} | Sell {sell_shares_min}-{sell_shares_max} shares @ ₹{price:>7.2f} → Get ₹{proceeds_min:>9,.0f}-₹{proceeds_max:>9,.0f}')
        print(f'      KEEP: {keep_shares_min}-{keep_shares_max} shares remaining (Current total: {current_shares} shares = ₹{current_value:>9,.0f})')
        book_total += (proceeds_min + proceeds_max) / 2
    print(f'\n   💵 Estimated BOOK Proceeds: ₹{book_total:,.0f}')
    print(f'   ⚠️  IMPORTANT: This is PARTIAL profit booking - you KEEP the remaining shares!')

# PRIORITY 4: BUY NEW POSITIONS (Fresh setups)
new_buys = df[(df['MY_VALUE_₹'] == 0) & (df['INVEST_₹'] > 0)].sort_values('INVEST_₹', ascending=False)
if len(new_buys) > 0:
    print('\n\n🆕 PRIORITY 4: BUY NEW POSITIONS (Fresh Capital)')
    print('-'*120)
    for _, row in new_buys.iterrows():
        symbol = row['symbol']
        invest = row['INVEST_₹']
        shares = row['BUY_SHARES']
        price = row['PRICE']
        action = row['ACTION']
        print(f'   ✅ BUY {symbol:12s} | Invest: ₹{invest:>8,.0f} | Buy {shares:>4.0f} shares @ ₹{price:>7.2f}')
        print(f'      Signal: {action}')
    print(f'\n   💰 Total NEW Investment: ₹{new_buys["INVEST_₹"].sum():,.0f}')

# PRIORITY 5: INCREASE WINNERS (Add to existing)
increases = df[(df['MY_VALUE_₹'] > 0) & (df['INVEST_₹'] > 0) & (df['ACTION'].str.contains('^INCREASE$', na=False, regex=True))].sort_values('INVEST_₹', ascending=False)
if len(increases) > 0:
    print('\n\n📈 PRIORITY 5: INCREASE EXISTING WINNERS (Add More)')
    print('-'*120)
    for _, row in increases.iterrows():
        symbol = row['symbol']
        invest = row['INVEST_₹']
        buy_shares = row['BUY_SHARES']
        current_shares = row['MY_SHARES']
        current_value = row['MY_VALUE_₹']
        new_total = current_shares + buy_shares
        print(f'   ✅ ADD {symbol:12s} | Add ₹{invest:>8,.0f} ({buy_shares:>4.0f} shares) → Total: {new_total:>4.0f} shares')
        print(f'      Current: {current_shares:>4.0f} shares (₹{current_value:>9,.0f})')
    print(f'\n   💰 Total INCREASE Investment: ₹{increases["INVEST_₹"].sum():,.0f}')

# PRIORITY 6: HOLD POSITIONS (No action)
holds = df[(df['MY_VALUE_₹'] > 0) & ((df['INVEST_₹'] == 0) | pd.isna(df['INVEST_₹'])) & (df['ACTION'].str.contains('HOLD|KEEP', na=False))].sort_values('MY_VALUE_₹', ascending=False)
if len(holds) > 0:
    print('\n\n✋ PRIORITY 6: HOLD - NO ACTION NEEDED (Keep As Is)')
    print('-'*120)
    for _, row in holds.iterrows():
        symbol = row['symbol']
        shares = row['MY_SHARES']
        value = row['MY_VALUE_₹']
        print(f'   ⚪ HOLD {symbol:12s} | Keep: {shares:>4.0f} shares (₹{value:>9,.0f})')
    print(f'\n   📊 Total HOLD Value: ₹{holds["MY_VALUE_₹"].sum():,.0f}')

# PRIORITY 7: OPTIONAL EXITS (Skip-Wait)
skip_wait = df[(df['MY_VALUE_₹'] > 0) & (df['ACTION'].str.contains('SKIP - WAIT', na=False))].sort_values('MY_VALUE_₹', ascending=False)
if len(skip_wait) > 0:
    print('\n\n⚪ PRIORITY 7: OPTIONAL EXITS (Consider Selling - Lower Priority)')
    print('-'*120)
    skip_total = 0
    for _, row in skip_wait.iterrows():
        symbol = row['symbol']
        shares = row['MY_SHARES']
        price = row['PRICE']
        value = row['MY_VALUE_₹']
        print(f'   ⚪ OPTIONAL SELL {symbol:12s} | {shares:>4.0f} shares @ ₹{price:>7.2f} → Get ₹{value:>9,.0f}')
        print(f'      Reason: Better opportunities available, not urgent')
        skip_total += value
    print(f'\n   💵 Optional SKIP-WAIT Proceeds: ₹{skip_total:,.0f}')

# FINAL SUMMARY
print('\n\n' + '='*120)
print('💼 CAPITAL FLOW SUMMARY')
print('='*120)
total_new = new_buys['INVEST_₹'].sum() if len(new_buys) > 0 else 0
total_increase = increases['INVEST_₹'].sum() if len(increases) > 0 else 0
swap_proceeds = swaps['MY_VALUE_₹'].sum() if len(swaps) > 0 else 0
exhausted_proceeds = exhausted['MY_VALUE_₹'].sum() if len(exhausted) > 0 else 0
book_proceeds = book_total if len(book_profit) > 0 else 0
skip_proceeds = skip_total if len(skip_wait) > 0 else 0

total_investment = total_new + total_increase
total_proceeds = swap_proceeds + exhausted_proceeds + book_proceeds + skip_proceeds

print(f'\n💸 CAPITAL OUT (Investments):')
print(f'   • NEW Positions:      ₹{total_new:>10,.0f}')
print(f'   • INCREASE Positions: ₹{total_increase:>10,.0f}')
print(f'   • SWAP Investments:   ₹{swap_proceeds:>10,.0f} (from sell proceeds)')
print(f'   ─────────────────────────────────')
print(f'   • Total Investment:   ₹{total_investment:>10,.0f}')

print(f'\n💰 CAPITAL IN (Sell Proceeds):')
print(f'   • SWAP Sales:         ₹{swap_proceeds:>10,.0f}')
print(f'   • EXHAUSTED Sales:    ₹{exhausted_proceeds:>10,.0f}')
print(f'   • BOOK 50-60%:        ₹{book_proceeds:>10,.0f}')
print(f'   • SKIP-WAIT (opt):    ₹{skip_proceeds:>10,.0f}')
print(f'   ─────────────────────────────────')
print(f'   • Total Proceeds:     ₹{total_proceeds:>10,.0f}')

net_capital = total_investment - total_proceeds
print(f'\n📊 NET CAPITAL REQUIRED: ₹{net_capital:>10,.0f}')
if net_capital < 0:
    print(f'   ✅ You will GET ₹{abs(net_capital):,.0f} BACK (sells > buys)')
else:
    print(f'   ⚠️  You need ₹{net_capital:,.0f} NEW capital (buys > sells)')

print('\n📈 Action Summary:')
print(f'   {len(swaps)} SWAP + {len(exhausted)} EXHAUSTED + {len(book_profit)} BOOK + {len(new_buys)} NEW + {len(increases)} INCREASE + {len(holds)} HOLD + {len(skip_wait)} SKIP = {len(df)} Total')
print('='*120)
