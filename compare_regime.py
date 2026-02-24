"""
Compare market regime: Today vs Yesterday
"""
import pandas as pd

print("="*80)
print("📊 MARKET REGIME COMPARISON: Week View")
print("="*80)

# Load both reports
try:
    # Yesterday - Feb 2, 2026
    df_yesterday = pd.read_excel('reports/Enhanced_Stock_Report_20260202_142901.xlsx', 
                                  sheet_name='Complete Data', nrows=1)
    
    # Today - Feb 3, 2026
    df_today = pd.read_excel('reports/Enhanced_Stock_Report_20260203_110051.xlsx', 
                             sheet_name='Complete Data', nrows=1)
    
    # Extract regime data
    yesterday_regime = df_yesterday.iloc[0].get('market_regime', 'N/A')
    yesterday_score = df_yesterday.iloc[0].get('regime_score', 0)
    
    today_regime = df_today.iloc[0].get('market_regime', 'N/A')
    today_score = df_today.iloc[0].get('regime_score', 0)
    
    # Calculate change
    score_change = today_score - yesterday_score
    change_pct = (score_change / abs(yesterday_score) * 100) if yesterday_score != 0 else 0
    
    print("\n📅 YESTERDAY (Feb 2, 2026)")
    print("-" * 80)
    print(f"   Regime: {yesterday_regime}")
    print(f"   Score: {yesterday_score:.4f}")
    
    print("\n📅 TODAY (Feb 3, 2026)")
    print("-" * 80)
    print(f"   Regime: {today_regime}")
    print(f"   Score: {today_score:.4f}")
    
    print("\n📊 CHANGE (Today vs Yesterday)")
    print("-" * 80)
    print(f"   Score Change: {score_change:+.4f} ({change_pct:+.1f}%)")
    
    if score_change > 0:
        print(f"   Direction: ⬆️ IMPROVING (Moving towards bullish)")
    elif score_change < 0:
        print(f"   Direction: ⬇️ WEAKENING (Moving towards bearish)")
    else:
        print(f"   Direction: ➡️ UNCHANGED")
    
    # Regime transition check
    if yesterday_regime != today_regime:
        print(f"\n   ⚠️  REGIME CHANGE DETECTED: {yesterday_regime} → {today_regime}")
    else:
        print(f"\n   ✅ Regime Stable: {today_regime} (no transition)")
    
    # Load portfolio actions for both days
    portfolio_yesterday = pd.read_excel('reports/Enhanced_Stock_Report_20260202_142901.xlsx', 
                                       sheet_name='Portfolio Allocation')
    portfolio_today = pd.read_excel('reports/Enhanced_Stock_Report_20260203_110051.xlsx', 
                                    sheet_name='Portfolio Allocation')
    
    # Count actions
    buy_yesterday = len(portfolio_yesterday[portfolio_yesterday['INVEST_₹'] > 0])
    buy_today = len(portfolio_today[portfolio_today['INVEST_₹'] > 0])
    
    sell_yesterday = len(portfolio_yesterday[portfolio_yesterday['ACTION'].str.contains('SELL|EXHAUSTED', na=False, regex=True)])
    sell_today = len(portfolio_today[portfolio_today['ACTION'].str.contains('SELL|EXHAUSTED', na=False, regex=True)])
    
    print("\n💼 PORTFOLIO ACTION CHANGES")
    print("-" * 80)
    print(f"   BUY/INCREASE:")
    print(f"      Yesterday: {buy_yesterday} stocks")
    print(f"      Today: {buy_today} stocks")
    print(f"      Change: {buy_today - buy_yesterday:+d}")
    
    print(f"\n   SELL:")
    print(f"      Yesterday: {sell_yesterday} stocks")
    print(f"      Today: {sell_today} stocks")
    print(f"      Change: {sell_today - sell_yesterday:+d}")
    
    # Market sentiment interpretation
    print("\n" + "="*80)
    print("💡 INTERPRETATION")
    print("="*80)
    
    if abs(score_change) < 0.1:
        print("\n   📊 Market is STABLE - minimal change in regime")
        print("   → Continue with existing strategy")
    elif score_change > 0:
        print("\n   📈 Market is STRENGTHENING")
        if today_regime == 'BULL':
            print("   → Entered bullish phase - increase exposure")
        elif today_regime == 'SIDEWAYS':
            print("   → Still sideways but improving - selective buying")
    else:
        print("\n   📉 Market is WEAKENING")
        if today_regime == 'BEAR':
            print("   → Entered bearish phase - reduce exposure")
        elif today_regime == 'SIDEWAYS':
            print("   → Still sideways but deteriorating - be cautious")
    
    # Weekly trend
    print("\n📅 WEEKLY TREND CONTEXT")
    print("-" * 80)
    if today_regime == 'SIDEWAYS' and yesterday_regime == 'SIDEWAYS':
        print("   Market has been CHOPPY for multiple days")
        print("   → Low conviction trades, wait for clear direction")
        print("   → Focus on quality stocks at support levels")
    
    print("\n" + "="*80)
    
except FileNotFoundError as e:
    print(f"\n❌ Error: Report file not found - {e}")
    print("   Make sure you have run analysis for both dates")
except Exception as e:
    print(f"\n❌ Error: {e}")
