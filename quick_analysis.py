import pandas as pd

file = r"reports\Enhanced_Stock_Report_20251124_221037.xlsx"

try:
    # Read Complete Data
    df = pd.read_excel(file, sheet_name='Complete Data')
    portfolio = pd.read_excel(file, sheet_name='Portfolio Allocation')
    
    print("="*100)
    print(f"📊 FULL ANALYSIS REPORT - {len(df)} stocks analyzed")
    print("="*100)
    
    # Top 25 by score
    print("\n🏆 TOP 25 STOCKS BY RISK-ADJUSTED SCORE:")
    print("-"*100)
    top = df.nlargest(25, 'risk_adjusted_score')
    for _, r in top.iterrows():
        roe_val = r.get('roe', r.get('ROE_%', 0))
        print(f"{r['symbol']:12} | {r['company_name'][:35]:35} | Score: {r['risk_adjusted_score']:5.1f} | "
              f"Underval: {r['undervaluation_score']:5.1f} | {r['sector'][:18]:18} | "
              f"₹{r['current_price']:8.2f} | P/E:{r.get('pe_ratio', 0):6.1f} | ROE:{roe_val:5.1f}%")
    
    # STRONG BUY (>=85)
    strong = df[df['risk_adjusted_score'] >= 85]
    print(f"\n🟢 STRONG BUY (Score ≥85): {len(strong)} stocks")
    for _, r in strong.iterrows():
        print(f"  • {r['symbol']:12} - {r['company_name'][:40]:40} (Score: {r['risk_adjusted_score']:.1f})")
    
    # BUY (75-84)
    buy = df[(df['risk_adjusted_score'] >= 75) & (df['risk_adjusted_score'] < 85)]
    print(f"\n🔵 BUY (Score 75-84): {len(buy)} stocks")
    for _, r in buy.head(10).iterrows():
        print(f"  • {r['symbol']:12} - {r['company_name'][:40]:40} (Score: {r['risk_adjusted_score']:.1f})")
    
    # Highly undervalued
    underval = df[df['undervaluation_score'] >= 90].nlargest(10, 'undervaluation_score')
    print(f"\n💎 TOP 10 HIGHLY UNDERVALUED (Score ≥90):")
    for _, r in underval.iterrows():
        print(f"  • {r['symbol']:12} - Underval: {r['undervaluation_score']:5.1f} | Score: {r['risk_adjusted_score']:5.1f} | {r['sector']}")
    
    # Diversification - Non-banking
    non_bank = df[(~df['sector'].str.contains('Financial|Bank', case=False, na=False)) & 
                  (df['risk_adjusted_score'] >= 75)].nlargest(15, 'risk_adjusted_score')
    print(f"\n🌐 DIVERSIFICATION - NON-BANKING HIGH SCORES (≥75): {len(non_bank)} stocks")
    for _, r in non_bank.iterrows():
        print(f"  • {r['symbol']:12} - {r['company_name'][:35]:35} | Score: {r['risk_adjusted_score']:5.1f} | {r['sector']}")
    
    # NEW opportunities
    my_shares_col = 'MY_SHARES' if 'MY_SHARES' in portfolio.columns else 'my_shares'
    if my_shares_col in portfolio.columns:
        current_holdings = set(portfolio[portfolio[my_shares_col] > 0]['symbol'])
        new_buys = portfolio[portfolio['ACTION'] == 'BUY'] if 'ACTION' in portfolio.columns else pd.DataFrame()
        
        if len(new_buys) > 0:
            new_opps = new_buys[~new_buys['symbol'].isin(current_holdings)]
            print(f"\n🆕 NEW BUY OPPORTUNITIES (not currently held): {len(new_opps)} stocks")
            score_col = 'SCORE' if 'SCORE' in portfolio.columns else 'risk_adjusted_score'
            for _, r in new_opps.nlargest(10, score_col).iterrows():
                print(f"  • {r['symbol']:12} - {r['company_name'][:35]:35} | Score: {r[score_col]:5.1f}")
    
    # Sector breakdown
    print(f"\n📊 SECTOR DISTRIBUTION (Top 30 stocks):")
    top30_sectors = df.nlargest(30, 'risk_adjusted_score')['sector'].value_counts()
    for sector, count in top30_sectors.items():
        pct = (count/30)*100
        print(f"  {sector:30} : {count:2d} stocks ({pct:4.1f}%)")
    
    # NEW: Check which high-scoring stocks you DON'T own
    my_shares_col = 'MY_SHARES' if 'MY_SHARES' in portfolio.columns else 'my_shares'
    if my_shares_col in portfolio.columns:
        current_holdings = set(portfolio[portfolio[my_shares_col] > 0]['symbol'])
        
        # High scorers (>=75) you don't own
        high_scorers = df[df['risk_adjusted_score'] >= 75]
        not_owned = high_scorers[~high_scorers['symbol'].isin(current_holdings)]
        
        print(f"\n🆕 HIGH-SCORING STOCKS YOU DON'T OWN (Score ≥75): {len(not_owned)} stocks")
        print("="*100)
        
        if len(not_owned) > 0:
            for _, r in not_owned.nlargest(15, 'risk_adjusted_score').iterrows():
                roe_val = r.get('roe', r.get('ROE_%', 0))
                action = "🟢 STRONG BUY" if r['risk_adjusted_score'] >= 85 else "🔵 BUY"
                print(f"{action} | {r['symbol']:12} - {r['company_name'][:35]:35} | "
                      f"Score: {r['risk_adjusted_score']:5.1f} | {r['sector'][:20]:20} | "
                      f"₹{r['current_price']:8.2f} | P/E:{r.get('pe_ratio', 0):6.1f}")
        
        # Compare your holdings vs available opportunities
        print(f"\n📈 YOUR CURRENT HOLDINGS COMPARISON:")
        print("="*100)
        holdings_data = portfolio[portfolio[my_shares_col] > 0].copy()
        score_col = 'SCORE' if 'SCORE' in portfolio.columns else 'risk_adjusted_score'
        
        if len(holdings_data) > 0:
            avg_holding_score = holdings_data[score_col].mean()
            avg_available_score = not_owned['risk_adjusted_score'].mean() if len(not_owned) > 0 else 0
            
            print(f"  Your Average Score: {avg_holding_score:.1f}")
            print(f"  Available Avg Score: {avg_available_score:.1f}")
            print(f"  Difference: {avg_available_score - avg_holding_score:+.1f} points")
            
            print(f"\n  Your Top 5 Holdings:")
            for _, r in holdings_data.nlargest(5, score_col).iterrows():
                shares = r.get(my_shares_col, 0)
                print(f"    • {r['symbol']:12} - Score: {r[score_col]:5.1f} | Shares: {shares:4.0f}")
    
    print("\n" + "="*100)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
