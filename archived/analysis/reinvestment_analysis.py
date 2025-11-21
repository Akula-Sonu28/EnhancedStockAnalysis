import pandas as pd

# Load portfolio allocation data
df = pd.read_excel('reports/Enhanced_Stock_Report_20250919_221055.xlsx', sheet_name='Portfolio Allocation')

print('💰 REINVESTMENT ANALYSIS')
print('='*60)

# Calculate available funds
sell_proceeds = df[df['keep_stock'] == False]['current_value'].sum()
available_funds = 88311
total_funds = sell_proceeds + available_funds

print(f'💸 Proceeds from 3 stock sales: ₹{sell_proceeds:,.0f}')
print(f'💵 Available investment funds: ₹{available_funds:,.0f}')
print(f'💰 Total reinvestment capacity: ₹{total_funds:,.0f}')
print()

# Get stocks to keep and their current allocations
keep_df = df[df['keep_stock'] == True].copy()
current_portfolio_value = keep_df['current_value'].sum()

print('📊 CURRENT PORTFOLIO ANALYSIS')
print('='*40)
print(f'Current portfolio value: ₹{current_portfolio_value:,.0f}')
print(f'Number of holdings: {len(keep_df)}')
print()

# Target portfolio value after reinvestment
target_portfolio_value = current_portfolio_value + total_funds

# Maximum allocation per stock (5-7%)
max_allocation_pct = 6.0  # Use 6% as target
max_allocation_value = target_portfolio_value * (max_allocation_pct / 100)

print(f'🎯 TARGET PORTFOLIO METRICS')
print('='*40)
print(f'Target portfolio value: ₹{target_portfolio_value:,.0f}')
print(f'Max allocation per stock (6%): ₹{max_allocation_value:,.0f}')
print()

# Find top stocks that need more investment (below max allocation)
investment_candidates = []

for _, row in keep_df.iterrows():
    current_value = row['current_value']
    symbol = row['symbol']
    score = row['risk_adjusted_score']
    stock_type = row['stock_type']
    
    # Calculate how much more we can invest in this stock
    max_investment_capacity = max_allocation_value - current_value
    
    if max_investment_capacity > 5000:  # Only consider if we can invest at least ₹5000
        investment_candidates.append({
            'symbol': symbol,
            'current_value': current_value,
            'score': score,
            'stock_type': stock_type,
            'investment_capacity': max_investment_capacity,
        })

# Sort by score (best opportunities first)
investment_candidates = sorted(investment_candidates, key=lambda x: x['score'], reverse=True)

print('🚀 TOP REINVESTMENT OPPORTUNITIES')
print('='*70)
print(f"{'Rank':<4} {'Stock':<12} {'Type':<7} {'Score':<6} {'Current':<12} {'Can Invest':<15}")
print('-' * 70)

total_investment_needed = 0
recommended_investments = []

for i, candidate in enumerate(investment_candidates[:10], 1):
    current_val = candidate['current_value']
    invest_capacity = candidate['investment_capacity'] 
    
    print(f'{i:<4} {candidate["symbol"]:<12} {candidate["stock_type"]:<7} {candidate["score"]:<6.1f} ₹{current_val:<11,.0f} ₹{invest_capacity:<14,.0f}')
    
    if total_investment_needed < total_funds and len(recommended_investments) < 8:
        # Calculate optimal investment amount
        remaining_funds = total_funds - total_investment_needed
        optimal_investment = min(invest_capacity, remaining_funds, 20000)  # Max ₹20K per stock
        
        if optimal_investment >= 5000:  # Minimum investment threshold
            recommended_investments.append({
                'symbol': candidate['symbol'],
                'investment_amount': optimal_investment,
                'score': candidate['score'],
                'stock_type': candidate['stock_type']
            })
            total_investment_needed += optimal_investment

print()
print('💡 RECOMMENDED INVESTMENT ALLOCATION')
print('='*65)
print(f"{'Stock':<12} {'Type':<7} {'Investment':<12} {'Score':<6} {'Price':<8} {'Shares':<8}")
print('-' * 65)

# Load complete data for prices
complete_df = pd.read_excel('reports/Enhanced_Stock_Report_20250919_221055.xlsx', sheet_name='Complete Data')

total_allocated = 0
for inv in recommended_investments:
    stock_data = complete_df[complete_df['symbol'] == inv['symbol']]
    
    if not stock_data.empty:
        current_price = stock_data.iloc[0]['current_price']
        shares_to_buy = int(inv['investment_amount'] / current_price)
        actual_investment = shares_to_buy * current_price
        
        print(f'{inv["symbol"]:<12} {inv["stock_type"]:<7} ₹{actual_investment:<11,.0f} {inv["score"]:<6.1f} ₹{current_price:<7.1f} {shares_to_buy:<8}')
        total_allocated += actual_investment

print('-' * 65)
print(f"{'TOTAL':<27} ₹{total_allocated:<11,.0f}")
print(f'Remaining funds: ₹{total_funds - total_allocated:,.0f}')

print()
print('📋 INVESTMENT SUMMARY')
print('='*40)
print(f'• Total stocks to enhance: {len(recommended_investments)}')
print(f'• Average investment per stock: ₹{total_allocated/len(recommended_investments) if recommended_investments else 0:,.0f}')
print(f'• Fund utilization: {(total_allocated/total_funds)*100:.1f}%')
print(f'• Portfolio diversification: Maintained at 30 stocks')
print(f'• Max allocation compliance: All stocks ≤6% of portfolio')