"""
SCORING SYSTEM ANALYSIS & IMPROVEMENT PLAN
==========================================

Let's analyze the current scoring system and identify improvement opportunities.
"""

import pandas as pd

# Load the latest Excel to understand current scores
df = pd.read_excel('reports/Enhanced_Stock_Report_20251016_122315.xlsx', sheet_name='Portfolio Allocation')

print("=" * 100)
print("CURRENT SCORING SYSTEM ANALYSIS")
print("=" * 100)

holdings = df[df['HOLDING?']].copy()

print("\n1. SCORE DISTRIBUTION ANALYSIS")
print("-" * 100)
print(f"\nScore statistics for {len(holdings)} holdings:")
print(f"   Mean: {holdings['SCORE'].mean():.1f}")
print(f"   Median: {holdings['SCORE'].median():.1f}")
print(f"   Min: {holdings['SCORE'].min():.1f}")
print(f"   Max: {holdings['SCORE'].max():.1f}")
print(f"   Std Dev: {holdings['SCORE'].std():.1f}")

# Score ranges
print(f"\nScore distribution:")
print(f"   90-100 (Excellent): {len(holdings[holdings['SCORE'] >= 90])} stocks")
print(f"   80-89 (Very Good): {len(holdings[(holdings['SCORE'] >= 80) & (holdings['SCORE'] < 90)])} stocks")
print(f"   70-79 (Good): {len(holdings[(holdings['SCORE'] >= 70) & (holdings['SCORE'] < 80)])} stocks")
print(f"   60-69 (Average): {len(holdings[(holdings['SCORE'] >= 60) & (holdings['SCORE'] < 70)])} stocks")
print(f"   Below 60 (Poor): {len(holdings[holdings['SCORE'] < 60])} stocks")

print("\n2. SCORE vs ACTUAL PERFORMANCE")
print("-" * 100)

# Correlation between score and profit
print("\nDo high scores = high profits?")
high_score = holdings[holdings['SCORE'] >= 85]
low_score = holdings[holdings['SCORE'] < 70]

print(f"\nHigh score stocks (≥85):")
print(f"   Count: {len(high_score)}")
print(f"   Avg profit: {high_score['PROFIT_%'].mean():.2f}%")
print(f"   Profitable: {len(high_score[high_score['PROFIT_%'] > 0])}/{len(high_score)}")

print(f"\nLow score stocks (<70):")
print(f"   Count: {len(low_score)}")
print(f"   Avg profit: {low_score['PROFIT_%'].mean():.2f}%")
print(f"   Profitable: {len(low_score[low_score['PROFIT_%'] > 0])}/{len(low_score)}")

# Paradox: Low score but high profit?
paradox = holdings[(holdings['SCORE'] < 70) & (holdings['PROFIT_%'] > 20)]
if len(paradox) > 0:
    print(f"\n⚠️ PARADOX: {len(paradox)} stocks with LOW score but HIGH profit:")
    for _, row in paradox.iterrows():
        print(f"   {row['symbol']}: Score {row['SCORE']:.1f} but Profit {row['PROFIT_%']:.2f}%")

# Anti-paradox: High score but loss?
anti_paradox = holdings[(holdings['SCORE'] >= 80) & (holdings['PROFIT_%'] < -5)]
if len(anti_paradox) > 0:
    print(f"\n⚠️ ANTI-PARADOX: {len(anti_paradox)} stocks with HIGH score but LOSS:")
    for _, row in anti_paradox.iterrows():
        print(f"   {row['symbol']}: Score {row['SCORE']:.1f} but Profit {row['PROFIT_%']:.2f}%")

print("\n3. CURRENT ACTIONS vs SCORES")
print("-" * 100)

# What actions are recommended for different score ranges?
actions = df.groupby(['ACTION', pd.cut(df['SCORE'], bins=[0, 60, 70, 80, 90, 100])]).size().unstack(fill_value=0)
print("\nAction distribution by score range:")
print(actions)

print("\n4. KEY SCORING ISSUES IDENTIFIED")
print("-" * 100)

issues = []

# Issue 1: HDFCBANK paradox
hdfcbank = holdings[holdings['symbol'] == 'HDFCBANK'].iloc[0] if 'HDFCBANK' in holdings['symbol'].values else None
if hdfcbank is not None:
    issues.append(f"Issue 1: HDFCBANK has score {hdfcbank['SCORE']:.1f} (low) but profit {hdfcbank['PROFIT_%']:.2f}% (excellent)")
    issues.append("   → Technical score dominating, ignoring long-term quality")

# Issue 2: Score spread too narrow
score_range = holdings['SCORE'].max() - holdings['SCORE'].min()
if score_range < 40:
    issues.append(f"Issue 2: Score range only {score_range:.1f} points (too narrow)")
    issues.append("   → Can't differentiate between great and average stocks")

# Issue 3: No penalty for losses
loss_makers = holdings[holdings['PROFIT_%'] < -5]
high_score_losers = loss_makers[loss_makers['SCORE'] > 75]
if len(high_score_losers) > 0:
    issues.append(f"Issue 3: {len(high_score_losers)} stocks with 75+ score but >5% loss")
    issues.append("   → Not penalizing for actual losses")

# Issue 4: Current performance not weighted enough
if holdings['SCORE'].corr(holdings['PROFIT_%']) < 0.3:
    corr = holdings['SCORE'].corr(holdings['PROFIT_%'])
    issues.append(f"Issue 4: Weak correlation (r={corr:.2f}) between score and actual profit")
    issues.append("   → Score not reflecting real-world performance")

for i, issue in enumerate(issues, 1):
    print(f"\n{issue}")

print("\n\n5. PROPOSED SCORING IMPROVEMENTS")
print("=" * 100)

print("""
🎯 IMPROVEMENT #1: HYBRID SCORING MODEL
--------------------------------------
Current: Technical score dominates (70%+)
Problem: Ignores fundamental quality and actual performance

NEW FORMULA:
risk_adjusted_score = (
    fundamental_quality * 0.30 +    # P/E, ROE, debt ratios (30%)
    technical_momentum * 0.25 +     # RSI, MACD, trend (25%)
    actual_performance * 0.25 +     # Current profit %, consistency (25%)
    market_conditions * 0.20        # Sector strength, market regime (20%)
)

Benefits:
✅ Balances technical with fundamental quality
✅ Rewards actual profits, not just potential
✅ Adapts to market conditions


🎯 IMPROVEMENT #2: PERFORMANCE-BASED ADJUSTMENTS
-----------------------------------------------
Current: Static score doesn't change with performance
Problem: Holding losers with high scores, selling winners with low scores

NEW LOGIC:
- If profit > 20%: Boost score by +10 points (proven winner)
- If profit 10-20%: Boost score by +5 points (performing well)
- If loss > 5%: Penalize score by -10 points (actual underperformer)
- If near breakeven: No adjustment (neutral)

Benefits:
✅ HDFCBANK +48.9% would get +10 boost → becomes top tier
✅ Loss-makers get penalized regardless of technical score
✅ Aligns score with reality


🎯 IMPROVEMENT #3: QUALITY vs MOMENTUM SEPARATION
------------------------------------------------
Current: Single score mixes everything
Problem: Can't distinguish between "hold long-term" and "trade short-term"

NEW APPROACH:
Two separate scores:
1. QUALITY SCORE (0-100): Fundamentals, business strength, long-term
2. MOMENTUM SCORE (0-100): Technical indicators, short-term movement

Decision matrix:
- High Quality + High Momentum = STRONG BUY
- High Quality + Low Momentum = HOLD (long-term)
- Low Quality + High Momentum = TRADE (short-term)
- Low Quality + Low Momentum = SELL

Benefits:
✅ HDFCBANK: High quality + low momentum = HOLD (correct!)
✅ Can identify momentum trades vs long-term holds
✅ Better exit strategy decisions


🎯 IMPROVEMENT #4: SECTOR-RELATIVE SCORING
------------------------------------------
Current: Absolute scores across all stocks
Problem: Banks vs Tech vs Pharma have different characteristics

NEW LOGIC:
- Calculate sector average and percentile rank
- Adjust score based on sector performance
- Financial Services 87% → penalize concentration

sector_adjusted_score = base_score * sector_multiplier
Where:
- sector_multiplier = 1.0 + (sector_rank - 50) / 100
- Underweight sectors: 1.1-1.2x bonus
- Overweight sectors: 0.8-0.9x penalty

Benefits:
✅ Encourages diversification
✅ Finds best stocks in underweight sectors
✅ Reduces concentration risk


🎯 IMPROVEMENT #5: TIME-DECAY FACTOR
------------------------------------
Current: Score is point-in-time
Problem: Doesn't account for holding period

NEW LOGIC:
For existing holdings:
- Holding >2 years with profit: "Mature position" → consider profit booking
- Holding >1 year breakeven: "Dead money" → strong sell candidate
- Holding <6 months loss: "Early stage" → give more time

time_factor = holding_period_months / 24  # 0 to 1+ range
adjusted_priority = base_priority * (1 + time_factor * performance)

Benefits:
✅ Identifies dead money positions faster
✅ Rewards consistent long-term winners
✅ More patient with recent additions


🎯 IMPROVEMENT #6: CONFIDENCE INTERVALS
--------------------------------------
Current: Single score number
Problem: No indication of reliability

NEW OUTPUT:
score: 85 ± 12 (confidence: 73%)
- High confidence (±5): Plenty of data, clear signals
- Low confidence (±20): Missing data, mixed signals

Benefits:
✅ Transparent about data quality
✅ Can filter by confidence level
✅ Better risk management
""")

print("\n\n6. IMPLEMENTATION PRIORITY")
print("=" * 100)
print("""
PHASE 1 (Immediate - High Impact):
✅ Improvement #2: Performance-based adjustments
   → Quick win, fixes HDFCBANK paradox
   → Code: Add profit boost/penalty to risk_adjusted_score

✅ Improvement #4: Sector-relative scoring
   → Addresses concentration issue
   → Code: Add sector_multiplier to scoring

PHASE 2 (Short-term - Medium Impact):
✅ Improvement #1: Hybrid scoring model
   → Rebalance weight distribution
   → Code: Adjust weights in CorrectedScoringEngine

PHASE 3 (Long-term - Structural):
✅ Improvement #3: Quality vs Momentum separation
   → Requires two-score system
   → Code: New columns in Excel

✅ Improvement #5: Time-decay factor
   → Needs holding period tracking
   → Code: Use portfolio history

✅ Improvement #6: Confidence intervals
   → Statistical framework
   → Code: Uncertainty quantification
""")

print("\n\nRECOMMENDATION: Start with Phase 1 improvements for immediate impact!")
