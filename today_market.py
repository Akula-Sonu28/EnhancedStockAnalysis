import pandas as pd
from datetime import datetime

print("="*80)
print("📊 MARKET CONDITION - February 6, 2026")
print("="*80)

# Load today's report
df_today = pd.read_excel('reports/Enhanced_Stock_Report_20260206_095752.xlsx', 
                         sheet_name='Complete Data', nrows=1)

regime = df_today.iloc[0].get('market_regime', 'N/A')
regime_score = df_today.iloc[0].get('regime_score', 'N/A')

print(f'\n🎯 Market Regime: {regime}')
print(f'📈 Regime Score: {regime_score:.4f}' if isinstance(regime_score, (int, float)) else f'📈 Regime Score: {regime_score}')

# Load portfolio actions
df_portfolio = pd.read_excel('reports/Enhanced_Stock_Report_20260206_095752.xlsx', 
                             sheet_name='Portfolio Allocation')

buy_actions = len(df_portfolio[df_portfolio['INVEST_₹'] > 0])
sell_actions = len(df_portfolio[df_portfolio['ACTION'].str.contains('SELL|EXHAUSTED', na=False, regex=True)])
hold_actions = len(df_portfolio[df_portfolio['ACTION'].str.contains('HOLD|KEEP', na=False)])

print(f'\n💼 Portfolio Actions:')
print(f'   🆕 BUY/INCREASE: {buy_actions} stocks')
print(f'   ❌ SELL: {sell_actions} stocks')
print(f'   ✋ HOLD: {hold_actions} stocks')

# Compare with Feb 3
try:
    df_feb3 = pd.read_excel('reports/Enhanced_Stock_Report_20260203_110051.xlsx', 
                           sheet_name='Complete Data', nrows=1)
    feb3_score = df_feb3.iloc[0].get('regime_score', 0)
    feb3_regime = df_feb3.iloc[0].get('market_regime', 'N/A')
    
    if isinstance(regime_score, (int, float)) and isinstance(feb3_score, (int, float)):
        score_change = regime_score - feb3_score
        
        print(f'\n📊 CHANGE (vs Feb 3):')
        print(f'   Previous: {feb3_regime} ({feb3_score:.4f})')
        print(f'   Change: {score_change:+.4f}')
        
        if score_change > 0.3:
            print(f'   📈 STRONG IMPROVEMENT - Market strengthening significantly')
        elif score_change > 0:
            print(f'   ⬆️  IMPROVING - Market getting better')
        elif score_change < -0.3:
            print(f'   📉 STRONG DECLINE - Market weakening significantly')
        elif score_change < 0:
            print(f'   ⬇️  WEAKENING - Market deteriorating')
        else:
            print(f'   ➡️  STABLE - Minimal change')
        
        # Check for regime transition
        if regime != feb3_regime:
            print(f'\n   ⚠️  REGIME TRANSITION: {feb3_regime} → {regime}')
            if regime == 'BULL':
                print(f'   🎉 Market has turned BULLISH! Time to increase exposure')
            elif regime == 'BEAR':
                print(f'   ⚠️  Market has turned BEARISH! Reduce risk exposure')
except:
    pass

print('\n' + '='*80)
print('💡 TRADING IMPLICATIONS')
print('='*80)

if isinstance(regime_score, (int, float)):
    if regime == 'BULL':
        print('\n✅ BULLISH MARKET - Favorable conditions')
        print('   → Aggressive buying opportunities')
        print('   → Focus on growth & momentum stocks')
        print('   → Can increase position sizes')
    elif regime == 'BEAR':
        print('\n❌ BEARISH MARKET - Challenging conditions')
        print('   → Defensive positioning')
        print('   → Focus on quality & value stocks')
        print('   → Reduce exposure, keep cash')
    else:  # SIDEWAYS
        print('\n⚠️  SIDEWAYS MARKET - Choppy conditions')
        print('   → Be selective, avoid momentum trades')
        print('   → Focus on support/resistance levels')
        print('   → Trade range-bound opportunities')
        
        if regime_score > 0:
            print('   → Bias: Slightly bullish (score positive)')
        elif regime_score < 0:
            print('   → Bias: Slightly bearish (score negative)')

print('\n' + '='*80)
