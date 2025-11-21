import pandas as pd

# Load current data
df = pd.read_excel('reports/Enhanced_Stock_Report_20250919_224614.xlsx', sheet_name='Portfolio Allocation')
complete_data = pd.read_excel('reports/Enhanced_Stock_Report_20250919_224614.xlsx', sheet_name='Complete Data')

print('🔍 CURRENT ALLOCATION ANALYSIS:')
print('=' * 50)

# Current concentrated allocation
keep_with_investment = df[(df['action_recommendation'] == 'KEEP') & (df['investment_amount'] > 0)]
current_total = keep_with_investment['investment_amount'].sum()
print(f'Current: ₹{current_total:,.0f} across {len(keep_with_investment)} stocks')

# Sector analysis
sectors = keep_with_investment['sector'].value_counts()
print(f'Sectors: {dict(sectors)}')
print(f'⚠️  Risk: {(sectors.iloc[0]/len(keep_with_investment)*100):.1f}% in single sector!')

print(f'\n💡 DIVERSIFIED ALTERNATIVES:')
print('=' * 50)

# Get all KEEP stocks for diversification
all_keep = df[df['action_recommendation'] == 'KEEP'].copy()
available_funds = 88311

# Strategy 1: Equal distribution across all KEEP stocks
equal_amount = available_funds // len(all_keep)
print(f'Strategy 1: EQUAL DISTRIBUTION')
print(f'- ₹{equal_amount:,} each across {len(all_keep)} stocks')
print(f'- Sectors covered: {len(all_keep["sector"].unique())}')
print(f'- Max per stock: {(equal_amount/826950*100):.1f}%')

# Strategy 2: Top performers focus (more concentrated but diversified)
top_performers = all_keep.nlargest(15, 'risk_adjusted_score')
focused_amount = available_funds // len(top_performers)
print(f'\nStrategy 2: TOP 15 PERFORMERS')
print(f'- ₹{focused_amount:,} each across top 15 stocks')
print(f'- Avg score: {top_performers["risk_adjusted_score"].mean():.1f}')
print(f'- Sectors: {len(top_performers["sector"].unique())}')

# Show current vs diversified sector allocation
print(f'\n📊 SECTOR DIVERSIFICATION COMPARISON:')
print('-' * 50)
print('Current (5 stocks):')
for sector, count in sectors.head(3).items():
    print(f'  {sector}: {count} stocks')

print(f'\nDiversified (Top 15):')
diverse_sectors = top_performers['sector'].value_counts()
for sector, count in diverse_sectors.head(5).items():
    print(f'  {sector}: {count} stocks')

# Show top 10 opportunities with better details
print(f'\n🎯 TOP 10 INVESTMENT OPPORTUNITIES:')
print('-' * 60)
top_10 = all_keep.nlargest(10, 'risk_adjusted_score')
for _, stock in top_10.iterrows():
    symbol = stock['symbol']
    score = stock['risk_adjusted_score']
    sector = stock['sector'][:15]  # Limit sector name length
    current_val = stock['current_value']
    allocation = focused_amount / 826950 * 100
    print(f'{symbol:12s}: {score:5.1f} | ₹{focused_amount:6,} ({allocation:.1f}%) | {sector}')

print(f'\n🎯 FINAL RECOMMENDATIONS:')
print('=' * 50)
print(f'✅ Use Strategy 2: Top 15 stocks approach')
print(f'✅ Better sector diversification ({len(top_performers["sector"].unique())} sectors vs 1)')
print(f'✅ Higher average quality (score: {top_performers["risk_adjusted_score"].mean():.1f})')
print(f'✅ Reduced concentration risk')
print(f'✅ Maintains growth potential with quality stocks')