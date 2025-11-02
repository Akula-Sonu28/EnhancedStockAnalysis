"""
VALUE-FOCUSED SCORING FORMULA
==============================

YOUR STRATEGY:
70% CORE:
   - 40% Undervalued stocks (buy low, sell high)
   - 30% Momentum + Value (moving up but still cheap)
   
20% OPPORTUNISTIC:
   - Hedging/defensive plays
   - Low market correlation
   
10% SPECULATIVE:
   - High risk/high reward
   - Momentum or turnaround plays

This formula focuses on:
1. Finding UNDERVALUED stocks (not overpriced blue chips!)
2. Identifying VALUE + MOMENTUM combinations
3. Setting clear EXIT points (when fairly valued)
"""

import pandas as pd
import numpy as np
import glob
import os

def calculate_value_focused_score(stock_data):
    """
    Scoring optimized for VALUE investing + Buy Low/Sell High
    
    Components:
    1. UNDERVALUATION (40%) - Primary factor!
    2. GROWTH POTENTIAL (25%) - Can it go higher?
    3. MOMENTUM (20%) - Is it moving up?
    4. QUALITY (10%) - Financial health
    5. RISK (5%) - Downside protection
    """
    
    # 1. UNDERVALUATION (40%) - MOST IMPORTANT!
    pe_ratio = stock_data.get('pe_ratio', 25)
    pb_ratio = stock_data.get('pb_ratio', 3)
    undervaluation_score = stock_data.get('undervaluation_score', 50)
    current_price = stock_data.get('current_price', 0)
    week_52_low = stock_data.get('52_week_low', current_price)
    week_52_high = stock_data.get('52_week_high', current_price)
    
    # Price position in 52-week range (lower is better for buying!)
    if week_52_high > week_52_low:
        price_position = (current_price - week_52_low) / (week_52_high - week_52_low)
    else:
        price_position = 0.5
    
    # Undervaluation scoring
    valuation_points = 0
    
    # PE ratio (lower is better)
    if pe_ratio < 10:
        valuation_points += 15  # Very undervalued
    elif pe_ratio < 15:
        valuation_points += 12  # Undervalued
    elif pe_ratio < 20:
        valuation_points += 8   # Fair value
    elif pe_ratio < 30:
        valuation_points += 3   # Slightly expensive
    else:
        valuation_points += 0   # Overvalued - avoid!
    
    # PB ratio (lower is better)
    if pb_ratio < 1.0:
        valuation_points += 10  # Trading below book value!
    elif pb_ratio < 2.0:
        valuation_points += 7
    elif pb_ratio < 3.0:
        valuation_points += 4
    else:
        valuation_points += 0
    
    # Price position (prefer stocks near 52-week low)
    if price_position < 0.3:
        valuation_points += 10  # Near lows - buy opportunity!
    elif price_position < 0.5:
        valuation_points += 6
    elif price_position < 0.7:
        valuation_points += 2
    else:
        valuation_points += 0   # Near highs - wait!
    
    # System undervaluation score
    valuation_points += (undervaluation_score - 50) / 10  # -5 to +5
    
    undervaluation_total = min(40, valuation_points)
    
    # 2. GROWTH POTENTIAL (25%)
    revenue_growth = stock_data.get('revenue_growth', 0)
    earnings_growth = stock_data.get('earnings_growth', 0)
    roe = stock_data.get('roe', 0)
    
    growth_points = 0
    
    # Revenue growth
    if revenue_growth > 20:
        growth_points += 10
    elif revenue_growth > 10:
        growth_points += 7
    elif revenue_growth > 5:
        growth_points += 4
    elif revenue_growth > 0:
        growth_points += 2
    
    # Earnings growth
    if earnings_growth > 20:
        growth_points += 8
    elif earnings_growth > 10:
        growth_points += 5
    elif earnings_growth > 0:
        growth_points += 2
    
    # ROE (profitability)
    if roe > 20:
        growth_points += 7
    elif roe > 15:
        growth_points += 5
    elif roe > 10:
        growth_points += 3
    
    growth_total = min(25, growth_points)
    
    # 3. MOMENTUM (20%)
    price_change_1m = stock_data.get('price_change_1m', 0)
    price_change_3m = stock_data.get('price_change_3m', 0)
    rsi = stock_data.get('real_rsi', 50)
    volume_trend = stock_data.get('volume_composite_score', 50)
    
    momentum_points = 0
    
    # Recent momentum (want to see upward movement)
    if 5 < price_change_1m < 15:
        momentum_points += 8  # Sweet spot - moving up but not overheated
    elif price_change_1m > 15:
        momentum_points += 5  # Strong but might be overbought
    elif price_change_1m > 0:
        momentum_points += 3  # Positive momentum
    
    # 3-month trend
    if 10 < price_change_3m < 30:
        momentum_points += 6
    elif price_change_3m > 30:
        momentum_points += 3
    elif price_change_3m > 0:
        momentum_points += 2
    
    # RSI (prefer 40-60 range for value buys)
    if 40 <= rsi <= 60:
        momentum_points += 4  # Not oversold, not overbought
    elif 30 <= rsi < 40:
        momentum_points += 6  # Oversold - buying opportunity!
    elif rsi < 30:
        momentum_points += 3  # Very oversold - could bounce
    
    # Volume
    momentum_points += (volume_trend - 50) / 25  # -2 to +2
    
    momentum_total = min(20, momentum_points)
    
    # 4. QUALITY (10%)
    debt_to_equity = stock_data.get('debt_to_equity', 100)
    current_ratio = stock_data.get('current_ratio', 1)
    operating_margin = stock_data.get('operating_margin', 0)
    
    quality_points = 0
    
    # Debt levels (lower is better)
    if debt_to_equity < 0.5:
        quality_points += 4
    elif debt_to_equity < 1.0:
        quality_points += 3
    elif debt_to_equity < 2.0:
        quality_points += 1
    
    # Liquidity
    if current_ratio > 2.0:
        quality_points += 3
    elif current_ratio > 1.5:
        quality_points += 2
    elif current_ratio > 1.0:
        quality_points += 1
    
    # Profitability
    if operating_margin > 20:
        quality_points += 3
    elif operating_margin > 10:
        quality_points += 2
    elif operating_margin > 5:
        quality_points += 1
    
    quality_total = min(10, quality_points)
    
    # 5. RISK ADJUSTMENT (5%)
    volatility = stock_data.get('volatility_6m', 30)
    max_drawdown = stock_data.get('max_drawdown_6m', 0)
    beta = stock_data.get('beta', 1)
    
    risk_points = 5  # Start with full points
    
    # Penalize high volatility
    if volatility > 50:
        risk_points -= 3
    elif volatility > 40:
        risk_points -= 2
    elif volatility > 35:
        risk_points -= 1
    
    # Penalize large drawdowns
    if max_drawdown < -30:
        risk_points -= 2
    elif max_drawdown < -20:
        risk_points -= 1
    
    risk_total = max(0, risk_points)
    
    # TOTAL SCORE
    total_score = undervaluation_total + growth_total + momentum_total + quality_total + risk_total
    
    # CLASSIFICATION LOGIC
    # CORE 70%: High value + decent momentum
    # OPPORTUNISTIC 20%: Defensive/low beta
    # SPECULATIVE 10%: High momentum OR high volatility
    
    if beta < 0.7 and volatility < 30:
        classification = 'OPPORTUNISTIC'  # Hedging/defensive
    elif volatility > 45 or (momentum_total > 15 and undervaluation_total < 20):
        classification = 'SPECULATIVE'  # High risk/momentum
    else:
        classification = 'CORE'  # Value plays
    
    # EXIT STRATEGY: When to sell
    exit_signal = None
    exit_reason = None
    
    # Check if stock has become fairly valued or overvalued
    if pe_ratio > 25 and price_position > 0.7:
        exit_signal = 'CONSIDER_SELL'
        exit_reason = 'Fair valued + near 52-week high'
    elif pb_ratio > 4 and price_position > 0.8:
        exit_signal = 'CONSIDER_SELL'
        exit_reason = 'Overvalued on P/B ratio'
    elif price_change_3m > 50 and undervaluation_total < 15:
        exit_signal = 'BOOK_PROFITS'
        exit_reason = 'Strong gains + no longer undervalued'
    
    return {
        'value_score': round(total_score, 1),
        'undervaluation_points': round(undervaluation_total, 1),
        'growth_points': round(growth_total, 1),
        'momentum_points': round(momentum_total, 1),
        'quality_points': round(quality_total, 1),
        'risk_points': round(risk_total, 1),
        'classification': classification,
        'exit_signal': exit_signal,
        'exit_reason': exit_reason,
        'pe_ratio': pe_ratio,
        'pb_ratio': pb_ratio,
        'price_position_52w': round(price_position * 100, 1)
    }


def analyze_with_value_strategy():
    """
    Analyze all stocks using VALUE-FOCUSED scoring
    """
    
    # Load latest Excel
    excel_files = glob.glob('reports/Enhanced_Stock_Report_*.xlsx')
    if not excel_files:
        print("❌ No Excel files found")
        return
    
    latest_excel = max(excel_files, key=os.path.getctime)
    print(f"📊 Analyzing: {latest_excel}\n")
    
    # Load data
    df = pd.read_excel(latest_excel, sheet_name='Complete Data')
    portfolio_df = pd.read_excel(latest_excel, sheet_name='Portfolio Allocation')
    
    current_holdings = set(portfolio_df['symbol'].tolist())
    
    print(f"✅ Loaded {len(df)} stocks from Complete Data")
    print(f"✅ Current holdings: {len(current_holdings)}\n")
    
    print("="*80)
    print("VALUE-FOCUSED SCORING - Buy Low, Sell High Strategy")
    print("="*80)
    
    results = []
    
    for idx, row in df.iterrows():
        stock_data = {
            'symbol': row['symbol'],
            'company_name': row['company_name'],
            'sector': row['sector'],
            'current_price': row.get('current_price', 0),
            '52_week_low': row.get('52_week_low', 0),
            '52_week_high': row.get('52_week_high', 0),
            'pe_ratio': row.get('pe_ratio', 25),
            'pb_ratio': row.get('pb_ratio', 3),
            'undervaluation_score': row.get('undervaluation_score', 50),
            'revenue_growth': row.get('revenue_growth', 0),
            'earnings_growth': row.get('earnings_growth', 0),
            'roe': row.get('roe', 0),
            'price_change_1m': row.get('price_change_1m', 0),
            'price_change_3m': row.get('price_change_3m', 0),
            'real_rsi': row.get('real_rsi', 50),
            'volume_composite_score': row.get('volume_composite_score', 50),
            'debt_to_equity': row.get('debt_to_equity', 1),
            'current_ratio': row.get('current_ratio', 1),
            'operating_margin': row.get('operating_margin', 0),
            'volatility_6m': row.get('volatility_6m', 30),
            'max_drawdown_6m': row.get('max_drawdown_6m', 0),
            'beta': row.get('beta', 1),
            'old_score': row.get('risk_adjusted_score', 50),
            'is_holding': row['symbol'] in current_holdings
        }
        
        # Calculate value score
        value_result = calculate_value_focused_score(stock_data)
        
        # Merge results
        stock_data.update(value_result)
        
        results.append(stock_data)
    
    results_df = pd.DataFrame(results)
    
    # Sort by value score
    results_df = results_df.sort_values('value_score', ascending=False)
    
    print(f"\n📊 SCORING COMPLETE")
    print(f"   Mean Score: {results_df['value_score'].mean():.1f}")
    print(f"   Median Score: {results_df['value_score'].median():.1f}")
    
    # Separate by classification
    core_stocks = results_df[results_df['classification'] == 'CORE']
    opportunistic_stocks = results_df[results_df['classification'] == 'OPPORTUNISTIC']
    speculative_stocks = results_df[results_df['classification'] == 'SPECULATIVE']
    
    print(f"\n📊 CLASSIFICATION:")
    print(f"   CORE (Value plays):      {len(core_stocks)} stocks ({len(core_stocks)/len(results_df)*100:.1f}%)")
    print(f"   OPPORTUNISTIC (Hedging): {len(opportunistic_stocks)} stocks ({len(opportunistic_stocks)/len(results_df)*100:.1f}%)")
    print(f"   SPECULATIVE (High risk): {len(speculative_stocks)} stocks ({len(speculative_stocks)/len(results_df)*100:.1f}%)")
    
    print("\n" + "="*80)
    print("🏆 TOP 20 VALUE OPPORTUNITIES (CORE 70% - Buy Low)")
    print("="*80)
    
    top_value = core_stocks.head(20)
    display = top_value[['symbol', 'company_name', 'value_score', 'pe_ratio', 'pb_ratio', 'price_position_52w', 'is_holding']]
    print(display.to_string(index=False))
    
    print("\n💡 Focus: Low P/E, Low P/B, Near 52-week lows + Growth potential")
    
    print("\n" + "="*80)
    print("🛡️ TOP 10 HEDGING PLAYS (OPPORTUNISTIC 20%)")
    print("="*80)
    
    top_hedging = opportunistic_stocks.head(10)
    if len(top_hedging) > 0:
        display = top_hedging[['symbol', 'company_name', 'value_score', 'beta', 'volatility_6m', 'is_holding']]
        print(display.to_string(index=False))
        print("\n💡 Focus: Low beta, low volatility, defensive sectors")
    else:
        print("No clear hedging candidates in current dataset")
    
    print("\n" + "="*80)
    print("🚀 TOP 10 HIGH RISK/HIGH REWARD (SPECULATIVE 10%)")
    print("="*80)
    
    top_speculative = speculative_stocks.head(10)
    if len(top_speculative) > 0:
        display = top_speculative[['symbol', 'company_name', 'value_score', 'momentum_points', 'volatility_6m', 'is_holding']]
        print(display.to_string(index=False))
        print("\n💡 Focus: High momentum, high volatility, turnaround plays")
    else:
        print("No clear speculative candidates in current dataset")
    
    # Current holdings analysis
    print("\n" + "="*80)
    print("📋 YOUR CURRENT HOLDINGS ANALYSIS")
    print("="*80)
    
    holdings = results_df[results_df['is_holding'] == True].copy()
    holdings = holdings.sort_values('value_score', ascending=False)
    
    # Check for exit signals
    exit_candidates = holdings[holdings['exit_signal'].notna()]
    
    if len(exit_candidates) > 0:
        print(f"\n⚠️ EXIT SIGNALS: {len(exit_candidates)} stocks")
        print("\nConsider selling these (no longer undervalued):")
        display = exit_candidates[['symbol', 'company_name', 'value_score', 'exit_reason', 'pe_ratio', 'pb_ratio']]
        print(display.to_string(index=False))
    else:
        print("\n✅ No exit signals - all holdings still have value potential")
    
    # Holdings classification
    print(f"\n📊 HOLDINGS CLASSIFICATION:")
    holdings_by_class = holdings.groupby('classification').size()
    for cls in ['CORE', 'OPPORTUNISTIC', 'SPECULATIVE']:
        count = holdings_by_class.get(cls, 0)
        pct = (count / len(holdings)) * 100
        print(f"   {cls}: {count} stocks ({pct:.1f}%)")
    
    print(f"\n🎯 TARGET ALLOCATION:")
    print(f"   CORE (70%):          Should be ~{int(len(holdings)*0.70)} stocks")
    print(f"   OPPORTUNISTIC (20%): Should be ~{int(len(holdings)*0.20)} stocks")
    print(f"   SPECULATIVE (10%):   Should be ~{int(len(holdings)*0.10)} stocks")
    
    # Deep undervalued analysis
    print("\n" + "="*80)
    print("💎 DEEP VALUE OPPORTUNITIES (Not in portfolio)")
    print("="*80)
    
    new_value_plays = core_stocks[
        (core_stocks['is_holding'] == False) &
        (core_stocks['undervaluation_points'] > 25) &
        (core_stocks['pe_ratio'] < 15)
    ].head(15)
    
    if len(new_value_plays) > 0:
        print(f"\n🎯 {len(new_value_plays)} DEEP VALUE stocks to consider:")
        display = new_value_plays[['symbol', 'company_name', 'value_score', 'pe_ratio', 'pb_ratio', 'price_position_52w', 'growth_points']]
        print(display.to_string(index=False))
        print("\n💡 These are UNDERVALUED with growth potential - perfect for your 40% value bucket")
    else:
        print("No obvious deep value plays found")
    
    # Value + Momentum plays
    print("\n" + "="*80)
    print("📈 VALUE + MOMENTUM PLAYS (Not in portfolio)")
    print("="*80)
    
    value_momentum = core_stocks[
        (core_stocks['is_holding'] == False) &
        (core_stocks['undervaluation_points'] > 20) &
        (core_stocks['momentum_points'] > 12) &
        (core_stocks['price_change_3m'] > 0)
    ].head(15)
    
    if len(value_momentum) > 0:
        print(f"\n🎯 {len(value_momentum)} VALUE + MOMENTUM stocks:")
        display = value_momentum[['symbol', 'company_name', 'value_score', 'undervaluation_points', 'momentum_points', 'price_change_3m']]
        print(display.to_string(index=False))
        print("\n💡 These are UNDERVALUED but already moving up - perfect for your 30% momentum bucket")
    else:
        print("No obvious value+momentum plays found")
    
    # Export results
    output_file = 'value_strategy_analysis.xlsx'
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        results_df.to_excel(writer, sheet_name='All_Stocks', index=False)
        core_stocks.to_excel(writer, sheet_name='Core_70pct', index=False)
        opportunistic_stocks.to_excel(writer, sheet_name='Opportunistic_20pct', index=False)
        speculative_stocks.to_excel(writer, sheet_name='Speculative_10pct', index=False)
        holdings.to_excel(writer, sheet_name='Current_Holdings', index=False)
        if len(exit_candidates) > 0:
            exit_candidates.to_excel(writer, sheet_name='Exit_Signals', index=False)
        if len(new_value_plays) > 0:
            new_value_plays.to_excel(writer, sheet_name='Deep_Value_Buys', index=False)
        if len(value_momentum) > 0:
            value_momentum.to_excel(writer, sheet_name='Value_Momentum_Buys', index=False)
    
    print(f"\n💾 Analysis saved to: {output_file}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY - VALUE STRATEGY")
    print("="*80)
    
    print(f"""
✅ SCORING FORMULA OPTIMIZED FOR VALUE INVESTING!

Weights:
   40% Undervaluation (P/E, P/B, 52-week position)
   25% Growth Potential (Revenue, Earnings, ROE)
   20% Momentum (Price trends, RSI, Volume)
   10% Quality (Debt, Liquidity, Margins)
   5%  Risk Adjustment (Volatility, Drawdown)

Strategy Buckets:
   🎯 CORE 70%:
      - 40% Deep value (low P/E, near 52-week lows)
      - 30% Value + Momentum (undervalued but moving)
   
   🛡️ OPPORTUNISTIC 20%:
      - Hedging plays (low beta, defensive)
   
   🚀 SPECULATIVE 10%:
      - High momentum or high volatility plays

Exit Strategy:
   ✅ Sell when P/E > 25 AND near 52-week highs
   ✅ Sell when P/B > 4 AND overvalued
   ✅ Book profits when gains > 50% AND no longer undervalued

Current: {len(holdings)} holdings
Target: 20-25 stocks total
    """)
    
    return results_df, holdings


if __name__ == '__main__':
    print("="*80)
    print("VALUE-FOCUSED PORTFOLIO ANALYSIS")
    print("="*80)
    print("""
YOUR STRATEGY: Buy Low, Sell High

70% CORE:
   40% - Deep value stocks (low P/E, P/B)
   30% - Value + momentum (undervalued but moving up)

20% OPPORTUNISTIC:
   - Hedging plays (defensive, low beta)

10% SPECULATIVE:
   - High risk/high reward (momentum or turnaround)

NOT interested in:
   ❌ Overpriced blue chips
   ❌ Stocks near 52-week highs
   ❌ High P/E without growth
    """)
    print("\n")
    
    results_df, holdings = analyze_with_value_strategy()
    
    print("\n" + "="*80)
    print("🎯 NEXT STEPS")
    print("="*80)
    print("""
1. Review Deep Value opportunities (40% bucket)
2. Review Value + Momentum plays (30% bucket)
3. Check exit signals for current holdings
4. Rebalance to 70/20/10 allocation
5. Target 20-25 total positions
    """)
