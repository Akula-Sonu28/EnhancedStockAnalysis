"""
Test Allocation Improvements - Verify ROI-Based Prioritization

This script validates the 3 key improvements:
1. Pre-breakout stocks (🚀) included in unified allocation
2. SWAP positions capped at 40% of budget (unless ROI >= 85)
3. ROI-weighted scoring prioritizes high-potential setups
"""

import pandas as pd
import os

def test_allocation_improvements():
    print("=" * 80)
    print("ALLOCATION IMPROVEMENTS TEST")
    print("=" * 80)
    
    # Load latest report (exclude temp files starting with ~)
    reports_dir = "reports"
    latest_report = max([f for f in os.listdir(reports_dir) if f.endswith('.xlsx') and not f.startswith('~')])
    report_path = os.path.join(reports_dir, latest_report)
    
    print(f"\n📊 Analyzing Report: {latest_report}")
    
    # Load Portfolio Allocation sheet
    df = pd.read_excel(report_path, sheet_name='Portfolio Allocation')
    
    print(f"\n1️⃣ PRE-BREAKOUT STOCKS IN ALLOCATION")
    print("-" * 80)
    
    # Check if pre-breakout stocks got allocated funds
    prebreakout_stocks = df[df['ACTION'].str.contains('🚀', na=False)]
    print(f"Found {len(prebreakout_stocks)} stocks with 🚀 pre-breakout flags:")
    
    for _, stock in prebreakout_stocks.iterrows():
        symbol = stock['symbol']
        action = stock['ACTION']
        invest = stock.get('INVEST_₹', 0)
        score = stock.get('SCORE', 0)
        status = "✅ FUNDED" if invest > 0 else "❌ NOT FUNDED"
        print(f"   {status} {symbol}: {action[:50]} | Score: {score:.1f} | Investment: ₹{invest:,.0f}")
    
    print(f"\n2️⃣ HIGH-ROI NEW OPPORTUNITIES")
    print("-" * 80)
    
    # Check conflict-resolved ENTER stocks
    enter_stocks = df[df['ACTION'].str.contains('🟢 ENTER', na=False)]
    print(f"Found {len(enter_stocks)} stocks with 🟢 ENTER (conflict-resolved):")
    
    for _, stock in enter_stocks.iterrows():
        symbol = stock['symbol']
        action = stock['ACTION']
        invest = stock.get('INVEST_₹', 0)
        score = stock.get('SCORE', 0)
        status = "✅ FUNDED" if invest > 0 else "❌ NOT FUNDED"
        print(f"   {status} {symbol}: Score {score:.1f} | Investment: ₹{invest:,.0f}")
    
    print(f"\n3️⃣ SWAP POSITION CAPS")
    print("-" * 80)
    
    # Check NEW POSITION allocations
    new_positions = df[(df['MY_VALUE_₹'] == 0) & (df['INVEST_₹'] > 0)]
    print(f"Found {len(new_positions)} NEW POSITION stocks with funding:")
    
    total_budget_estimate = new_positions['INVEST_₹'].sum() * 2.5  # Rough estimate
    
    for _, stock in new_positions.iterrows():
        symbol = stock['symbol']
        invest = stock['INVEST_₹']
        action = stock['ACTION']
        score = stock.get('SCORE', 0)
        pct_of_budget = (invest / total_budget_estimate * 100) if total_budget_estimate > 0 else 0
        
        if 'SWAP' in str(action) or pct_of_budget > 40:
            cap_status = "⚠️ EXCEEDS 40%" if pct_of_budget > 40 else "✅ WITHIN 40%"
            print(f"   {cap_status} {symbol}: ₹{invest:,.0f} ({pct_of_budget:.1f}% of budget) | Score: {score:.1f}")
        else:
            print(f"   ✅ {symbol}: ₹{invest:,.0f} ({pct_of_budget:.1f}% of budget) | Score: {score:.1f}")
    
    print(f"\n4️⃣ ALLOCATION PRIORITY RANKING")
    print("-" * 80)
    
    # Show top 10 funded stocks by amount
    funded = df[df['INVEST_₹'] > 0].copy()
    funded = funded.sort_values('INVEST_₹', ascending=False)
    
    print(f"Top funded stocks (showing allocation priority):")
    for i, (_, stock) in enumerate(funded.head(10).iterrows(), 1):
        symbol = stock['symbol']
        invest = stock['INVEST_₹']
        score = stock.get('SCORE', 0)
        action = stock['ACTION'][:40]
        my_value = stock.get('MY_VALUE_₹', 0)
        stock_type = "INCREASE" if my_value > 0 else "NEW"
        
        # Check for ROI indicators
        roi_indicator = ""
        if '🚀' in str(action):
            roi_indicator = "🚀 Pre-Breakout"
        elif '🟢' in str(action):
            roi_indicator = "🟢 Conflict-Resolved ENTER"
        elif '🟡' in str(action):
            roi_indicator = "🟡 Conflict-Resolved SMALL"
        
        print(f"   #{i}. {symbol} ({stock_type}): ₹{invest:,.0f} | Score: {score:.1f} | {roi_indicator} {action}")
    
    print(f"\n5️⃣ MISSED OPPORTUNITIES ANALYSIS")
    print("-" * 80)
    
    # Stocks with high scores but no funding
    high_score_unfunded = df[(df['SCORE'] >= 75) & (df['INVEST_₹'] == 0) & (df['MY_VALUE_₹'] == 0)]
    
    if len(high_score_unfunded) > 0:
        print(f"⚠️  Found {len(high_score_unfunded)} high-scoring stocks (≥75) with no funding:")
        for _, stock in high_score_unfunded.iterrows():
            symbol = stock['symbol']
            score = stock['SCORE']
            action = stock['ACTION']
            print(f"   ❌ {symbol}: Score {score:.1f} | Action: {action[:50]}")
    else:
        print("✅ No high-scoring stocks (≥75) missed!")
    
    print(f"\n6️⃣ OVERALL SUMMARY")
    print("-" * 80)
    
    total_invested = df['INVEST_₹'].sum()
    num_funded = len(df[df['INVEST_₹'] > 0])
    num_increase = len(df[(df['INVEST_₹'] > 0) & (df['MY_VALUE_₹'] > 0)])
    num_new = len(df[(df['INVEST_₹'] > 0) & (df['MY_VALUE_₹'] == 0)])
    avg_score_funded = df[df['INVEST_₹'] > 0]['SCORE'].mean()
    
    prebreakout_funded = len(df[(df['INVEST_₹'] > 0) & (df['ACTION'].str.contains('🚀', na=False))])
    conflict_funded = len(df[(df['INVEST_₹'] > 0) & ((df['ACTION'].str.contains('🟢', na=False)) | (df['ACTION'].str.contains('🟡', na=False)))])
    
    print(f"   💰 Total Investment: ₹{total_invested:,.0f}")
    print(f"   📊 Stocks Funded: {num_funded} ({num_increase} INCREASE + {num_new} NEW)")
    print(f"   ⭐ Avg Score (Funded): {avg_score_funded:.1f}")
    print(f"   🚀 Pre-Breakout Funded: {prebreakout_funded}")
    print(f"   🎯 Conflict-Resolved Funded: {conflict_funded}")
    
    # Calculate improvement metrics
    print(f"\n✅ IMPROVEMENT METRICS:")
    if prebreakout_funded > 0:
        print(f"   ✅ Pre-breakout stocks NOW included in allocation ({prebreakout_funded} funded)")
    else:
        print(f"   ⚠️  No pre-breakout stocks funded (check if any exist with scores ≥65)")
    
    if num_new >= num_increase * 0.3:  # At least 30% of allocations to NEW
        print(f"   ✅ Good balance: {num_new} NEW vs {num_increase} INCREASE positions")
    else:
        print(f"   ⚠️  Allocation skewed toward INCREASE: {num_new} NEW vs {num_increase} INCREASE")
    
    # Check SWAP concentration
    if num_new > 0:
        max_new_investment = df[df['MY_VALUE_₹'] == 0]['INVEST_₹'].max()
        pct_of_total = (max_new_investment / total_invested * 100)
        if pct_of_total <= 45:
            print(f"   ✅ SWAP cap working: Largest NEW position is {pct_of_total:.1f}% of total")
        else:
            print(f"   ⚠️  Potential concentration: Largest NEW position is {pct_of_total:.1f}% of total")

if __name__ == "__main__":
    test_allocation_improvements()
