"""
VALUE INVESTING SCORING FORMULA
================================

USER'S ACTUAL STRATEGY:
-----------------------
70% CORE: "Buy low, sell high" - Undervalued with high potential
   - 30% Momentum chasers (riding trends)
   - 40% Deep value (undervalued → fair/overvalued exit)
   
20% HEDGING: Market protection, defensive stocks

10% SPECULATIVE: High risk/high reward (momentum or lottery tickets)

KEY PRINCIPLE: Don't sell blue chips like HDFCBANK just because score is low!
They are QUALITY holdings that have ALREADY appreciated - that's SUCCESS!

NEW SCORING APPROACH:
---------------------
1. For HOLDINGS: Score based on "should I add more?" not "should I sell?"
2. For NEW STOCKS: Score based on "undervalued + potential"
3. Separate CORE stocks (keep forever) from tactical trades

"""

import pandas as pd
import numpy as np
import glob
import os

def calculate_value_investing_score(stock_data, is_holding=False):
    """
    Score for VALUE INVESTING strategy:
    - Undervaluation (40%)
    - Growth Potential (30%)
    - Quality/Momentum Mix (20%)
    - Risk Adjustment (10%)
    """
    
    # 1. UNDERVALUATION SCORE (40%) - Most important!
    underval_score = stock_data.get('undervaluation_score', 50)
    
    # PE relative to sector
    pe_ratio = stock_data.get('pe_ratio', 20)
    sector_avg_pe = stock_data.get('sector_avg_pe', 20)
    
    # Lower PE = more undervalued
    if pe_ratio > 0 and sector_avg_pe > 0:
        pe_relative = (sector_avg_pe - pe_ratio) / sector_avg_pe * 100
        pe_score = max(0, min(100, 50 + pe_relative))
    else:
        pe_score = 50
    
    # PB ratio
    pb_ratio = stock_data.get('pb_ratio', 3)
    pb_score = 100 if pb_ratio < 1 else (80 if pb_ratio < 2 else (60 if pb_ratio < 3 else 40))
    
    undervaluation = (underval_score * 0.5) + (pe_score * 0.3) + (pb_score * 0.2)
    undervaluation_final = undervaluation * 0.40  # 40% weight
    
    # 2. GROWTH POTENTIAL (30%)
    # Revenue growth
    revenue_growth = stock_data.get('revenue_growth', 0)
    earnings_growth = stock_data.get('earnings_growth', 0)
    
    growth_score = 0
    if revenue_growth > 20:
        growth_score += 15
    elif revenue_growth > 10:
        growth_score += 10
    elif revenue_growth > 5:
        growth_score += 5
    
    if earnings_growth > 20:
        growth_score += 15
    elif earnings_growth > 10:
        growth_score += 10
    elif earnings_growth > 5:
        growth_score += 5
    
    growth_final = growth_score  # Out of 30
    
    # 3. QUALITY/MOMENTUM MIX (20%)
    # For CORE 70%: Balance quality and momentum
    
    # Quality indicators
    roe = stock_data.get('roe', 10)
    operating_margin = stock_data.get('operating_margin', 10)
    
    quality_score = 0
    if roe > 20:
        quality_score += 5
    elif roe > 15:
        quality_score += 3
    elif roe > 10:
        quality_score += 1
    
    if operating_margin > 20:
        quality_score += 5
    elif operating_margin > 10:
        quality_score += 3
    
    # Momentum (for 30% momentum chasers)
    price_change_3m = stock_data.get('price_change_3m', 0)
    sentiment = stock_data.get('sentiment_composite_score', 50)
    
    momentum_score = 0
    if price_change_3m > 15:
        momentum_score += 5
    elif price_change_3m > 10:
        momentum_score += 3
    elif price_change_3m > 5:
        momentum_score += 2
    
    momentum_score += ((sentiment - 50) / 50) * 5  # -5 to +5
    
    quality_momentum = quality_score + momentum_score  # Out of 20
    
    # 4. RISK ADJUSTMENT (10%)
    volatility = stock_data.get('volatility_6m', 30)
    debt_to_equity = stock_data.get('debt_to_equity', 1)
    
    risk_score = 10  # Start at full points
    
    # Penalize high volatility (but don't penalize too much - volatility creates opportunity!)
    if volatility > 50:
        risk_score -= 3
    elif volatility > 40:
        risk_score -= 2
    elif volatility > 35:
        risk_score -= 1
    
    # Penalize high debt
    if debt_to_equity > 2:
        risk_score -= 3
    elif debt_to_equity > 1.5:
        risk_score -= 2
    elif debt_to_equity > 1:
        risk_score -= 1
    
    risk_final = max(0, risk_score)
    
    # TOTAL SCORE
    total_score = undervaluation_final + growth_final + quality_momentum + risk_final
    
    # SPECIAL HANDLING FOR HOLDINGS
    if is_holding:
        profit_pct = stock_data.get('profit_pct', 0)
        
        # If already profitable, DON'T penalize! This is a SUCCESS!
        # Instead, adjust score to reflect "should I add more?"
        if profit_pct > 40:
            # Major winner - maybe take some profits, but keep core position
            total_score = total_score * 0.8  # Slight reduction, still good
        elif profit_pct > 20:
            # Good performer - hold and potentially add on dips
            total_score = total_score * 0.9
        elif profit_pct < -10:
            # Loser - reduce score significantly
            total_score = total_score * 0.6
    
    total_score = max(0, min(100, total_score))
    
    return {
        'value_score': round(total_score, 1),
        'undervaluation_component': round(undervaluation_final, 1),
        'growth_component': round(growth_final, 1),
        'quality_momentum_component': round(quality_momentum, 1),
        'risk_component': round(risk_final, 1)
    }


def classify_by_strategy(stock_data, is_holding=False):
    """
    Classify stock into user's 70/20/10 categories
    """
    
    underval_score = stock_data.get('undervaluation_score', 50)
    price_change_3m = stock_data.get('price_change_3m', 0)
    volatility = stock_data.get('volatility_6m', 30)
    pe_ratio = stock_data.get('pe_ratio', 20)
    
    # CORE 70% - Split into two sub-strategies
    
    # Momentum Chasers (30% of CORE = 21% overall)
    if price_change_3m > 15 and volatility < 40:
        return 'CORE_MOMENTUM', 'Riding strong trends with controlled risk'
    
    # Deep Value (40% of CORE = 28% overall)
    if underval_score > 70 or pe_ratio < 15:
        return 'CORE_VALUE', 'Undervalued stocks with high potential'
    
    # General CORE (remaining)
    if volatility < 35 and pe_ratio < 25:
        return 'CORE_BALANCED', 'Balanced quality stocks'
    
    # HEDGING 20% - Defensive, low volatility
    if volatility < 25:
        return 'HEDGING', 'Market protection, defensive'
    
    # SPECULATIVE 10% - High risk/high reward
    if volatility > 45 or price_change_3m > 30 or price_change_3m < -20:
        return 'SPECULATIVE', 'High risk/high reward'
    
    # Default to CORE_BALANCED
    return 'CORE_BALANCED', 'General core holding'


def analyze_value_portfolio():
    """
    Analyze portfolio using VALUE INVESTING approach
    """
    
    # Load data
    excel_files = glob.glob('reports/Enhanced_Stock_Report_*.xlsx')
    if not excel_files:
        print("❌ No Excel files found")
        return
    
    latest_excel = max(excel_files, key=os.path.getctime)
    print(f"📊 Analyzing: {latest_excel}\n")
    
    df = pd.read_excel(latest_excel, sheet_name='Complete Data')
    portfolio_df = pd.read_excel(latest_excel, sheet_name='Portfolio Allocation')
    
    current_holdings = set(portfolio_df['symbol'].tolist())
    
    print("="*80)
    print("VALUE INVESTING PORTFOLIO ANALYSIS")
    print("="*80)
    print("""
YOUR STRATEGY:
   70% CORE:
      - 30% Momentum chasers (riding trends)
      - 40% Deep value (buy low, sell high)
   20% HEDGING: Defensive stocks
   10% SPECULATIVE: High risk/high reward
    """)
    
    # Score all stocks
    results = []
    
    for idx, row in df.iterrows():
        is_holding = row['symbol'] in current_holdings
        profit_pct = 0
        
        if is_holding:
            holding_data = portfolio_df[portfolio_df['symbol'] == row['symbol']].iloc[0]
            profit_pct = holding_data.get('PROFIT_%', 0)
        
        stock_data = {
            'undervaluation_score': row.get('undervaluation_score', 50),
            'pe_ratio': row.get('pe_ratio', 20),
            'pb_ratio': row.get('pb_ratio', 3),
            'sector_avg_pe': 20,  # Would calculate from sector average
            'revenue_growth': row.get('revenue_growth', 0),
            'earnings_growth': row.get('earnings_growth', 0),
            'roe': row.get('roe', 10),
            'operating_margin': row.get('operating_margin', 10),
            'price_change_3m': row.get('price_change_3m', 0),
            'sentiment_composite_score': row.get('sentiment_composite_score', 50),
            'volatility_6m': row.get('volatility_6m', 30),
            'debt_to_equity': row.get('debt_to_equity', 1),
            'profit_pct': profit_pct
        }
        
        # Calculate value score
        value_scores = calculate_value_investing_score(stock_data, is_holding)
        
        # Classify
        category, reason = classify_by_strategy(stock_data, is_holding)
        
        results.append({
            'symbol': row['symbol'],
            'company_name': row['company_name'],
            'sector': row['sector'],
            'is_holding': is_holding,
            'profit_pct': profit_pct if is_holding else None,
            'value_score': value_scores['value_score'],
            'underval_component': value_scores['undervaluation_component'],
            'growth_component': value_scores['growth_component'],
            'category': category,
            'category_reason': reason,
            'current_price': row.get('current_price', 0),
            'pe_ratio': stock_data['pe_ratio'],
            'undervaluation_score': stock_data['undervaluation_score']
        })
    
    results_df = pd.DataFrame(results)
    
    # Analyze current holdings
    print("\n" + "="*80)
    print("CURRENT HOLDINGS ANALYSIS")
    print("="*80)
    
    holdings = results_df[results_df['is_holding'] == True].copy()
    holdings = holdings.sort_values('profit_pct', ascending=False)
    
    print(f"\nTotal Holdings: {len(holdings)}")
    print(f"Average Profit: {holdings['profit_pct'].mean():.2f}%")
    
    # Classify holdings
    print("\n📊 HOLDINGS BY STRATEGY:")
    for cat in ['CORE_MOMENTUM', 'CORE_VALUE', 'CORE_BALANCED', 'HEDGING', 'SPECULATIVE']:
        cat_stocks = holdings[holdings['category'] == cat]
        if len(cat_stocks) > 0:
            pct = len(cat_stocks) / len(holdings) * 100
            avg_profit = cat_stocks['profit_pct'].mean()
            print(f"\n{cat}: {len(cat_stocks)} stocks ({pct:.1f}%)")
            print(f"   Average Profit: {avg_profit:.2f}%")
            print(f"   Average Value Score: {cat_stocks['value_score'].mean():.1f}")
            
            # Show examples
            examples = cat_stocks.head(5)[['symbol', 'company_name', 'value_score', 'profit_pct']]
            print(examples.to_string(index=False))
    
    # Identify QUALITY WINNERS (don't sell these!)
    print("\n" + "="*80)
    print("🏆 QUALITY WINNERS - KEEP THESE! (Blue Chips)")
    print("="*80)
    
    quality_winners = holdings[
        (holdings['profit_pct'] > 20) & 
        (holdings['pe_ratio'] > 0)
    ].sort_values('profit_pct', ascending=False)
    
    print(f"\n{len(quality_winners)} stocks with >20% profit:")
    display = quality_winners[['symbol', 'company_name', 'profit_pct', 'value_score', 'category']]
    print(display.to_string(index=False))
    
    print("\n💡 These are SUCCESS stories - they appreciated because they're QUALITY!")
    print("   Don't sell just because value score is lower now.")
    print("   Consider: Keep core position, take partial profits if needed.")
    
    # Identify TRUE LOSERS (actual sell candidates)
    print("\n" + "="*80)
    print("❌ TRUE SELL CANDIDATES")
    print("="*80)
    
    true_losers = holdings[
        (holdings['profit_pct'] < -5) |
        ((holdings['profit_pct'] < 5) & (holdings['value_score'] < 50))
    ].sort_values('value_score')
    
    print(f"\n{len(true_losers)} stocks that are underperforming:")
    if len(true_losers) > 0:
        display = true_losers[['symbol', 'company_name', 'profit_pct', 'value_score', 'category']]
        print(display.to_string(index=False))
    else:
        print("✅ No true losers! All holdings are performing well.")
    
    # Best NEW opportunities (undervalued + high potential)
    print("\n" + "="*80)
    print("🎯 BEST NEW OPPORTUNITIES - Deep Value Stocks")
    print("="*80)
    
    candidates = results_df[results_df['is_holding'] == False].copy()
    
    # Deep value candidates
    deep_value = candidates[
        (candidates['undervaluation_score'] > 70) |
        (candidates['pe_ratio'] < 15)
    ].sort_values('value_score', ascending=False)
    
    print(f"\nTop 15 DEEP VALUE stocks (buy low, sell high):")
    display = deep_value.head(15)[['symbol', 'company_name', 'value_score', 'undervaluation_score', 'pe_ratio', 'category']]
    print(display.to_string(index=False))
    
    # Momentum opportunities
    momentum_candidates = candidates[
        candidates['category'] == 'CORE_MOMENTUM'
    ].sort_values('value_score', ascending=False)
    
    print(f"\n\nTop 10 MOMENTUM stocks (ride the trend):")
    display = momentum_candidates.head(10)[['symbol', 'company_name', 'value_score', 'category_reason']]
    print(display.to_string(index=False))
    
    # Final recommendations
    print("\n" + "="*80)
    print("📋 FINAL RECOMMENDATIONS")
    print("="*80)
    
    print(f"""
KEEP (Quality Winners):
   - {len(quality_winners)} stocks with >20% profit
   - These are SUCCESS stories (e.g., HDFCBANK +48%)
   - Action: Hold core position, consider taking 30-50% profits if needed
   
SELL (True Losers):
   - {len(true_losers)} underperforming stocks
   - Action: Exit and redeploy to better opportunities
   
BUY (New Opportunities):
   - {len(deep_value.head(10))} deep value stocks (40% of CORE)
   - {len(momentum_candidates.head(5))} momentum stocks (30% of CORE)
   - Focus on undervalued with high growth potential
   
Portfolio Target:
   - Reduce from {len(holdings)} to 25 stocks
   - Keep quality winners + add deep value
   - Balance: 70% CORE / 20% HEDGING / 10% SPECULATIVE
    """)
    
    # Export
    output_file = 'value_investing_analysis.xlsx'
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        results_df.to_excel(writer, sheet_name='All_Stocks', index=False)
        holdings.to_excel(writer, sheet_name='Holdings', index=False)
        quality_winners.to_excel(writer, sheet_name='Quality_Winners', index=False)
        true_losers.to_excel(writer, sheet_name='Sell_Candidates', index=False)
        deep_value.to_excel(writer, sheet_name='Deep_Value_Buys', index=False)
        momentum_candidates.to_excel(writer, sheet_name='Momentum_Buys', index=False)
    
    print(f"\n💾 Analysis saved to: {output_file}")
    
    return results_df, quality_winners, true_losers, deep_value


if __name__ == '__main__':
    print("="*80)
    print("VALUE INVESTING PORTFOLIO ANALYZER")
    print("="*80)
    print("""
Strategy Alignment:
   ✅ 70% CORE (30% momentum + 40% deep value)
   ✅ 20% HEDGING (defensive)
   ✅ 10% SPECULATIVE (high risk/reward)
   
Philosophy:
   ✅ Buy low, sell high (not sell quality winners!)
   ✅ Undervalued → Fair/Overvalued exit
   ✅ Quality winners = SUCCESS (hold core position)
    """)
    print("\n")
    
    results_df, quality_winners, true_losers, deep_value = analyze_value_portfolio()
    
    print("\n" + "="*80)
    print("✅ CORRECTED APPROACH")
    print("="*80)
    print("""
Previous mistake: Suggested selling HDFCBANK because sentiment-based score was lower
Correct approach: HDFCBANK is a QUALITY WINNER (+48% profit!) - KEEP IT!

The score should answer: "Should I BUY MORE?" not "Should I SELL?"

Value investing focuses on:
1. Finding undervalued stocks (buy low)
2. Holding quality (let winners run)
3. Selling only when overvalued OR fundamentally broken
    """)
