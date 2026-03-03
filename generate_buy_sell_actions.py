"""
Actionable Buy/Sell Decision Framework using all 41 columns
Shows you EXACTLY what to do with each position
"""
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/intelligence.db')

print("="*80)
print("BUY/SELL DECISION FRAMEWORK - Using All 41 Columns")
print("="*80)

# Get latest report data (positions you currently own)
current_positions = pd.read_sql("""
    SELECT *
    FROM user_portfolio
    WHERE date = (SELECT MAX(date) FROM user_portfolio)
    AND i_own_it = 1
    ORDER BY my_value DESC
""", conn)

print(f"\nAnalyzing {len(current_positions)} current holdings from latest report...")
print("="*80)

# SELL DECISIONS - Which positions to exit NOW
print("\n[IMMEDIATE SELLS] - Exit These Positions Now")
print("="*80)

sell_now = []
for _, row in current_positions.iterrows():
    sell_score = 0
    reasons = []
    
    # Reason 1: System says SELL
    if 'SELL' in str(row['action']).upper():
        sell_score += 40
        reasons.append(f"System SELL signal")
    
    # Reason 2: Exhaustion detected
    if row['exhaustion'] and row['exhaustion'] not in ['False', '', None]:
        sell_score += 30
        reasons.append(f"Exhausted: {row['exhaustion']}")
    
    # Reason 3: Exit signals present
    if row['exit_signals'] and row['exit_signals'] not in ['', None]:
        sell_score += 20
        reasons.append(f"Exit signals: {str(row['exit_signals'])[:50]}")
    
    # Reason 4: Losing position
    if row['my_profit_pct'] < -0.05:  # -5% loss
        sell_score += 30
        reasons.append(f"Loss: {row['my_profit_pct']*100:.1f}%")
    
    # Reason 5: High RSI (overbought)
    if row['rsi'] and row['rsi'] > 80:
        sell_score += 15
        reasons.append(f"Overbought RSI: {row['rsi']:.0f}")
    
    # Reason 6: Below support
    if row['support'] and row['price'] < row['support']:
        sell_score += 20
        reasons.append(f"Below support (₹{row['support']:.0f})")
    
    # Reason 7: Should book partial profit
    if 'BOOK' in str(row['action']).upper():
        sell_score += 25
        reasons.append(f"Book {row['book_pct_if_sell']:.0f}% profit")
    
    if sell_score >= 50:  # Strong sell signal
        sell_now.append({
            'symbol': row['symbol'],
            'action': row['action'],
            'shares': row['my_shares'],
            'value': row['my_value'],
            'profit_pct': row['my_profit_pct']*100,
            'book_amount': row['book_amount'],
            'sell_score': sell_score,
            'reasons': reasons,
            'exit_score': row['exit_score']
        })

if len(sell_now) > 0:
    sell_df = pd.DataFrame(sell_now).sort_values('sell_score', ascending=False)
    
    for _, pos in sell_df.head(10).iterrows():
        profit_icon = "LOSS" if pos['profit_pct'] < 0 else "PROFIT"
        print(f"\n{pos['symbol']:12} | SELL SCORE: {pos['sell_score']}/100")
        print(f"   Current: {pos['shares']:.0f} shares, ₹{pos['value']:,.0f} ({profit_icon}: {pos['profit_pct']:.2f}%)")
        print(f"   Book Amount: ₹{pos['book_amount']:,.0f}")
        print(f"   System Action: {pos['action']}")
        print(f"   Reasons:")
        for reason in pos['reasons']:
            print(f"      - {reason}")
        print(f"   --> ACTION: SELL {pos['shares']:.0f} shares")
else:
    print("   [NONE] - No immediate sells required")

# REDUCE POSITIONS - Partial exits
print("\n" + "="*80)
print("[BOOK PARTIAL PROFITS] - Reduce These Positions")
print("="*80)

book_profit = []
for _, row in current_positions.iterrows():
    # Already in SELL list, skip
    if row['symbol'] in [s['symbol'] for s in sell_now]:
        continue
    
    book_score = 0
    reasons = []
    
    # Strong profit + exhaustion
    if row['my_profit_pct'] > 0.15 and row['exhaustion']:  # 15%+ profit
        book_score += 40
        reasons.append(f"High profit ({row['my_profit_pct']*100:.1f}%) + exhausted")
    
    # System says BOOK
    if 'BOOK' in str(row['action']).upper():
        book_score += 35
        book_pct = row['book_pct_if_sell']
        reasons.append(f"System: Book {book_pct:.0f}% profit")
    
    # High RSI but still profitable
    if row['rsi'] and row['rsi'] > 75 and row['my_profit_pct'] > 0.10:
        book_score += 25
        reasons.append(f"Overbought (RSI {row['rsi']:.0f}) + profitable")
    
    # Near resistance
    if row['resistance'] and row['price'] >= row['resistance'] * 0.98:
        book_score += 20
        reasons.append(f"Near resistance (₹{row['resistance']:.0f})")
    
    if book_score >= 40:
        book_profit.append({
            'symbol': row['symbol'],
            'shares': row['my_shares'],
            'value': row['my_value'],
            'profit_pct': row['my_profit_pct']*100,
            'book_pct': row['book_pct_if_sell'],
            'book_amount': row['book_amount'],
            'book_score': book_score,
            'reasons': reasons
        })

if len(book_profit) > 0:
    book_df = pd.DataFrame(book_profit).sort_values('book_score', ascending=False)
    
    for _, pos in book_df.head(10).iterrows():
        sell_shares = int(pos['shares'] * pos['book_pct'] / 100) if pos['book_pct'] > 0 else int(pos['shares'] * 0.5)
        keep_shares = pos['shares'] - sell_shares
        
        print(f"\n{pos['symbol']:12} | BOOK SCORE: {pos['book_score']}/100")
        print(f"   Current: {pos['shares']:.0f} shares, ₹{pos['value']:,.0f} (+{pos['profit_pct']:.2f}%)")
        print(f"   Book Amount: ₹{pos['book_amount']:,.0f}")
        print(f"   Reasons:")
        for reason in pos['reasons']:
            print(f"      - {reason}")
        print(f"   --> ACTION: SELL {sell_shares} shares, KEEP {keep_shares} shares")
else:
    print("   [NONE] - No partial profit booking needed")

# BUY DECISIONS - New positions to enter
print("\n" + "="*80)
print("[NEW BUYS] - Enter These Positions")
print("="*80)

# Get stocks you DON'T own from latest report
new_buys = pd.read_sql("""
    SELECT *
    FROM user_portfolio
    WHERE date = (SELECT MAX(date) FROM user_portfolio)
    AND i_own_it = 0
    AND action NOT LIKE '%SELL%'
    AND action NOT LIKE '%SKIP%'
""", conn)

buy_opportunities = []
for _, row in new_buys.iterrows():
    buy_score = 0
    reasons = []
    
    # Reason 1: High system score
    if row['score'] > 80:
        buy_score += 30
        reasons.append(f"High score: {row['score']:.1f}")
    
    # Reason 2: Pre-breakout setup
    if row['pre_breakout'] in ['YES', 'True', True]:
        buy_score += 35
        reasons.append(f"Pre-breakout ({row['breakout_pct']:.1f}% potential)")
    
    # Reason 3: Strong fundamentals
    if row['fund_score'] and row['fund_score'] > 75:
        buy_score += 20
        reasons.append(f"Strong fundamentals: {row['fund_score']:.1f}")
    
    # Reason 4: High momentum
    if row['mom_score'] and row['mom_score'] > 75:
        buy_score += 20
        reasons.append(f"High momentum: {row['mom_score']:.1f}")
    
    # Reason 5: Good value
    if row['value_score'] and row['value_score'] > 75:
        buy_score += 15
        reasons.append(f"Good value: {row['value_score']:.1f}")
    
    # Reason 6: Strong setup signals
    if row['setup_signals'] and len(str(row['setup_signals'])) > 10:
        buy_score += 20
        reasons.append(f"Setup: {str(row['setup_signals'])[:50]}")
    
    # Reason 7: Above support, below resistance
    if row['support'] and row['resistance']:
        if row['support'] < row['price'] < row['resistance']:
            buy_score += 15
            reasons.append(f"Good zone (Support ₹{row['support']:.0f} - Resistance ₹{row['resistance']:.0f})")
    
    # Reason 8: Moderate RSI (not overbought)
    if row['rsi'] and 40 < row['rsi'] < 65:
        buy_score += 10
        reasons.append(f"Healthy RSI: {row['rsi']:.0f}")
    
    if buy_score >= 60:  # Strong buy signal
        buy_opportunities.append({
            'symbol': row['symbol'],
            'action': row['action'],
            'price': row['price'],
            'invest_amount': row['invest_amount'],
            'buy_shares': row['buy_shares'],
            'score': row['score'],
            'buy_score': buy_score,
            'sector': row['sector'],
            'risk': row['risk'],
            'reasons': reasons
        })

if len(buy_opportunities) > 0:
    buy_df = pd.DataFrame(buy_opportunities).sort_values('buy_score', ascending=False)
    
    print(f"\nFound {len(buy_df)} strong opportunities:")
    
    for _, pos in buy_df.head(10).iterrows():
        print(f"\n{pos['symbol']:12} | BUY SCORE: {pos['buy_score']}/100")
        print(f"   Price: ₹{pos['price']:.2f} | Sector: {pos['sector']} | Risk: {pos['risk']}")
        print(f"   System Score: {pos['score']:.1f}")
        print(f"   Invest: ₹{pos['invest_amount']:,.0f} ({pos['buy_shares']:.0f} shares)")
        print(f"   Reasons:")
        for reason in pos['reasons']:
            print(f"      - {reason}")
        print(f"   --> ACTION: BUY {pos['buy_shares']:.0f} shares at ₹{pos['price']:.2f}")
else:
    print("   [NONE] - No strong buy opportunities right now")

# INCREASE POSITIONS - Add to existing winners
print("\n" + "="*80)
print("[INCREASE POSITIONS] - Add to These Winners")
print("="*80)

increase_positions = []
for _, row in current_positions.iterrows():
    # Skip if in SELL or BOOK list
    if row['symbol'] in [s['symbol'] for s in sell_now]:
        continue
    if row['symbol'] in [s['symbol'] for s in book_profit]:
        continue
    
    increase_score = 0
    reasons = []
    
    # Reason 1: System says INCREASE
    if 'INCREASE' in str(row['action']).upper():
        increase_score += 40
        reasons.append("System: Add more")
    
    # Reason 2: Profitable position
    if row['my_profit_pct'] > 0.05:  # 5%+ profit
        increase_score += 20
        reasons.append(f"Profitable: +{row['my_profit_pct']*100:.1f}%")
    
    # Reason 3: Still has momentum
    if row['mom_score'] and row['mom_score'] > 70 and row['rsi'] < 70:
        increase_score += 25
        reasons.append(f"Momentum intact (RSI {row['rsi']:.0f})")
    
    # Reason 4: Above support
    if row['support'] and row['price'] > row['support'] * 1.02:
        increase_score += 15
        reasons.append(f"Above support (₹{row['support']:.0f})")
    
    # Reason 5: High score
    if row['score'] > 80:
        increase_score += 20
        reasons.append(f"High score: {row['score']:.1f}")
    
    if increase_score >= 50:
        increase_positions.append({
            'symbol': row['symbol'],
            'current_shares': row['my_shares'],
            'current_value': row['my_value'],
            'profit_pct': row['my_profit_pct']*100,
            'price': row['price'],
            'invest_more': row['invest_amount'],
            'add_shares': row['buy_shares'],
            'increase_score': increase_score,
            'reasons': reasons
        })

if len(increase_positions) > 0:
    increase_df = pd.DataFrame(increase_positions).sort_values('increase_score', ascending=False)
    
    for _, pos in increase_df.head(10).iterrows():
        total_shares = pos['current_shares'] + pos['add_shares']
        
        print(f"\n{pos['symbol']:12} | INCREASE SCORE: {pos['increase_score']}/100")
        print(f"   Current: {pos['current_shares']:.0f} shares, ₹{pos['current_value']:,.0f} (+{pos['profit_pct']:.2f}%)")
        print(f"   Add: {pos['add_shares']:.0f} shares for ₹{pos['invest_more']:,.0f}")
        print(f"   New Total: {total_shares:.0f} shares")
        print(f"   Reasons:")
        for reason in pos['reasons']:
            print(f"      - {reason}")
        print(f"   --> ACTION: BUY {pos['add_shares']:.0f} more shares at ₹{pos['price']:.2f}")
else:
    print("   [NONE] - No positions to increase right now")

# SUMMARY
print("\n" + "="*80)
print("[ACTION SUMMARY]")
print("="*80)

total_sell_value = sum([s['value'] for s in sell_now])
total_book_amount = sum([s['book_amount'] for s in book_profit])
total_invest_new = sum([b['invest_amount'] for b in buy_opportunities[:10]])
total_invest_increase = sum([i['invest_more'] for i in increase_positions[:10]])

print(f"\nSELLS (Immediate):")
print(f"   Count: {len(sell_now)} positions")
print(f"   Release: ₹{total_sell_value:,.0f}")

print(f"\nBOOK PROFITS (Partial):")
print(f"   Count: {len(book_profit)} positions")
print(f"   Book: ₹{total_book_amount:,.0f}")

print(f"\nNEW BUYS:")
print(f"   Count: {len(buy_opportunities)} opportunities")
print(f"   Required: ₹{total_invest_new:,.0f}")

print(f"\nINCREASE POSITIONS:")
print(f"   Count: {len(increase_positions)} positions")
print(f"   Required: ₹{total_invest_increase:,.0f}")

print(f"\nNET CAPITAL FLOW:")
cash_in = total_sell_value + total_book_amount
cash_out = total_invest_new + total_invest_increase
net_flow = cash_in - cash_out

if net_flow > 0:
    print(f"   Cash Released: ₹{net_flow:,.0f} (sell more than buy)")
else:
    print(f"   Cash Needed: ₹{abs(net_flow):,.0f} (buy more than sell)")

print("\n" + "="*80)
print("Copy this analysis to execute trades tomorrow!")
print("="*80)

conn.close()

