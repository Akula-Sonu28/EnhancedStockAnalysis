import pandas as pd

# Load latest report
df = pd.read_excel('reports/Enhanced_Stock_Report_20260203_110051.xlsx', sheet_name='Complete Data', nrows=1)

print('\n' + '='*70)
print('📊 MARKET CONDITION - February 3, 2026')
print('='*70)

# Extract market regime data
regime = df.iloc[0].get('market_regime', 'N/A')
regime_score = df.iloc[0].get('regime_score', 'N/A')
trend = df.iloc[0].get('market_trend', 'N/A')
volatility = df.iloc[0].get('market_volatility', 'N/A')
momentum = df.iloc[0].get('market_momentum', 'N/A')

print(f'\n🎯 Market Regime: {regime}')
print(f'📈 Regime Score: {regime_score}')
print(f'📊 Trend: {trend}')
print(f'⚡ Volatility: {volatility}')
print(f'🚀 Momentum: {momentum}')

# Load Portfolio Allocation to get recommended actions
df_portfolio = pd.read_excel('reports/Enhanced_Stock_Report_20260203_110051.xlsx', sheet_name='Portfolio Allocation')

buy_actions = len(df_portfolio[df_portfolio['INVEST_₹'] > 0])
sell_actions = len(df_portfolio[df_portfolio['ACTION'].str.contains('SELL|EXHAUSTED', na=False, regex=True)])
hold_actions = len(df_portfolio[df_portfolio['ACTION'].str.contains('HOLD|KEEP', na=False)])

print(f'\n💼 Portfolio Actions:')
print(f'   🆕 BUY/INCREASE: {buy_actions} stocks')
print(f'   ❌ SELL: {sell_actions} stocks')
print(f'   ✋ HOLD: {hold_actions} stocks')

print('\n' + '='*70)
