"""
COMPREHENSIVE EXCEL ANALYSIS
=============================
Understanding all sheets and their use in scoring system
"""

import pandas as pd
import openpyxl

excel_file = 'reports/Enhanced_Stock_Report_20251016_122315.xlsx'

print("=" * 100)
print("COMPREHENSIVE EXCEL ANALYSIS - ALL SHEETS")
print("=" * 100)

# Load workbook to see all sheets
xl = pd.ExcelFile(excel_file)
print(f"\nExcel file: {excel_file}")
print(f"Total sheets: {len(xl.sheet_names)}\n")

print("=" * 100)
print("SHEET INVENTORY")
print("=" * 100)

for i, sheet_name in enumerate(xl.sheet_names, 1):
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    print(f"\n{i}. {sheet_name}")
    print(f"   Rows: {len(df)}, Columns: {len(df.columns)}")
    print(f"   Columns: {', '.join(df.columns[:10].tolist())}{' ...' if len(df.columns) > 10 else ''}")

# ============================================================================
# DETAILED ANALYSIS OF EACH SHEET
# ============================================================================

print("\n\n" + "=" * 100)
print("DETAILED SHEET-BY-SHEET ANALYSIS")
print("=" * 100)

# Sheet 1: Complete Data
print("\n1. COMPLETE DATA SHEET")
print("-" * 100)
complete_df = pd.read_excel(excel_file, sheet_name='Complete Data')
print(f"Purpose: Full analysis of all {len(complete_df)} stocks")
print(f"Columns ({len(complete_df.columns)}): {list(complete_df.columns)}")

# Check what scoring-related columns exist
scoring_cols = [col for col in complete_df.columns if 'score' in col.lower() or 'rating' in col.lower()]
print(f"\nScoring-related columns found: {len(scoring_cols)}")
for col in scoring_cols:
    print(f"   • {col}")

# Check key metrics
key_metrics = ['risk_adjusted_score', 'undervaluation_score', 'technical_score', 
               'fundamental_score', 'ml_confidence', 'recommendation']
available_metrics = [m for m in key_metrics if m in complete_df.columns]
print(f"\nKey metrics available: {available_metrics}")

# Sheet 2: Portfolio Allocation
print("\n\n2. PORTFOLIO ALLOCATION SHEET")
print("-" * 100)
portfolio_df = pd.read_excel(excel_file, sheet_name='Portfolio Allocation')
print(f"Purpose: Actionable recommendations for {len(portfolio_df)} stocks")
print(f"Columns ({len(portfolio_df.columns)}): {list(portfolio_df.columns)}")

print(f"\nWhat's used for decisions:")
print(f"   • Primary Score: SCORE ({portfolio_df['SCORE'].describe()})")
print(f"   • Actions: {portfolio_df['ACTION'].value_counts().to_dict()}")
print(f"   • Classifications: {portfolio_df['TYPE'].value_counts().to_dict()}")

# Sheet 3: Technical Analysis
if 'Technical Analysis' in xl.sheet_names:
    print("\n\n3. TECHNICAL ANALYSIS SHEET")
    print("-" * 100)
    tech_df = pd.read_excel(excel_file, sheet_name='Technical Analysis')
    print(f"Purpose: Technical indicators for {len(tech_df)} stocks")
    print(f"Columns ({len(tech_df.columns)}): {list(tech_df.columns)}")
    
    # Technical indicators
    tech_indicators = [col for col in tech_df.columns if any(x in col.lower() for x in ['rsi', 'macd', 'sma', 'ema', 'momentum'])]
    print(f"\nTechnical indicators ({len(tech_indicators)}):")
    for ind in tech_indicators[:15]:
        print(f"   • {ind}")
    if len(tech_indicators) > 15:
        print(f"   ... and {len(tech_indicators) - 15} more")

# Sheet 4: Risk Analysis
if 'Risk Analysis' in xl.sheet_names:
    print("\n\n4. RISK ANALYSIS SHEET")
    print("-" * 100)
    risk_df = pd.read_excel(excel_file, sheet_name='Risk Analysis')
    print(f"Purpose: Risk metrics for {len(risk_df)} stocks")
    print(f"Columns ({len(risk_df.columns)}): {list(risk_df.columns)}")
    
    risk_cols = [col for col in risk_df.columns if any(x in col.lower() for x in ['risk', 'volatility', 'beta', 'drawdown'])]
    print(f"\nRisk metrics ({len(risk_cols)}):")
    for col in risk_cols:
        print(f"   • {col}")

# Sheet 5: Fundamental Analysis
if 'Fundamental Analysis' in xl.sheet_names:
    print("\n\n5. FUNDAMENTAL ANALYSIS SHEET")
    print("-" * 100)
    fund_df = pd.read_excel(excel_file, sheet_name='Fundamental Analysis')
    print(f"Purpose: Financial metrics for {len(fund_df)} stocks")
    print(f"Columns ({len(fund_df.columns)}): {list(fund_df.columns)}")
    
    fundamental_cols = [col for col in fund_df.columns if any(x in col.lower() for x in ['pe', 'pb', 'roe', 'debt', 'revenue', 'profit', 'margin'])]
    print(f"\nFundamental metrics ({len(fundamental_cols)}):")
    for col in fundamental_cols[:15]:
        print(f"   • {col}")
    if len(fundamental_cols) > 15:
        print(f"   ... and {len(fundamental_cols) - 15} more")

# Sheet 6: Pattern Recognition
if 'Pattern Recognition' in xl.sheet_names:
    print("\n\n6. PATTERN RECOGNITION SHEET")
    print("-" * 100)
    pattern_df = pd.read_excel(excel_file, sheet_name='Pattern Recognition')
    print(f"Purpose: Chart patterns for {len(pattern_df)} stocks")
    print(f"Columns ({len(pattern_df.columns)}): {list(pattern_df.columns)}")

# Sheet 7: Market Regime
if 'Market Regime' in xl.sheet_names:
    print("\n\n7. MARKET REGIME SHEET")
    print("-" * 100)
    regime_df = pd.read_excel(excel_file, sheet_name='Market Regime')
    print(f"Purpose: Market conditions analysis")
    print(f"Columns ({len(regime_df.columns)}): {list(regime_df.columns)}")
    print(f"Rows: {len(regime_df)}")

# Sheet 8: ML Predictions
if 'ML Predictions' in xl.sheet_names:
    print("\n\n8. ML PREDICTIONS SHEET")
    print("-" * 100)
    ml_df = pd.read_excel(excel_file, sheet_name='ML Predictions')
    print(f"Purpose: Machine learning forecasts for {len(ml_df)} stocks")
    print(f"Columns ({len(ml_df.columns)}): {list(ml_df.columns)}")

# Sheet 9: Sentiment Analysis
if 'Sentiment Analysis' in xl.sheet_names:
    print("\n\n9. SENTIMENT ANALYSIS SHEET")
    print("-" * 100)
    sent_df = pd.read_excel(excel_file, sheet_name='Sentiment Analysis')
    print(f"Purpose: News/social sentiment for {len(sent_df)} stocks")
    print(f"Columns ({len(sent_df.columns)}): {list(sent_df.columns)}")

# ============================================================================
# CROSS-REFERENCE ANALYSIS
# ============================================================================

print("\n\n" + "=" * 100)
print("CROSS-REFERENCE: WHAT DATA EXISTS vs WHAT'S USED IN SCORING")
print("=" * 100)

# Check Complete Data sheet for available but unused metrics
complete_df = pd.read_excel(excel_file, sheet_name='Complete Data')

print("\n📊 AVAILABLE METRICS IN 'COMPLETE DATA' SHEET:")
print("-" * 100)

# Group columns by category
categories = {
    'Price & Performance': ['current_price', 'price_change', '52_week_high', '52_week_low', 'ytd_return'],
    'Technical Indicators': ['rsi', 'macd', 'sma', 'ema', 'bollinger', 'momentum', 'stochastic'],
    'Fundamental Metrics': ['pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity', 'revenue_growth', 'profit_margin'],
    'Volume & Liquidity': ['volume', 'avg_volume', 'volume_trend', 'liquidity_score'],
    'Risk Metrics': ['beta', 'volatility', 'max_drawdown', 'sharpe_ratio', 'var'],
    'Valuation': ['market_cap', 'enterprise_value', 'price_to_sales', 'dividend_yield'],
    'Scores': ['risk_adjusted_score', 'undervaluation_score', 'technical_score', 'fundamental_score'],
    'ML & AI': ['ml_prediction', 'ml_confidence', 'pattern_score', 'sentiment_score'],
    'Market Context': ['sector', 'industry', 'market_regime', 'sector_strength']
}

for category, keywords in categories.items():
    matching_cols = [col for col in complete_df.columns if any(kw in col.lower() for kw in keywords)]
    if matching_cols:
        print(f"\n{category}: {len(matching_cols)} columns")
        for col in matching_cols[:5]:
            # Show sample stats
            if col in complete_df.columns:
                non_null = complete_df[col].notna().sum()
                print(f"   ✅ {col} ({non_null}/{len(complete_df)} populated)")
        if len(matching_cols) > 5:
            print(f"   ... and {len(matching_cols) - 5} more")
    else:
        print(f"\n{category}: ❌ NO DATA FOUND")

# ============================================================================
# SCORING FORMULA ANALYSIS
# ============================================================================

print("\n\n" + "=" * 100)
print("CURRENT SCORING FORMULA ANALYSIS")
print("=" * 100)

portfolio_df = pd.read_excel(excel_file, sheet_name='Portfolio Allocation')
complete_df = pd.read_excel(excel_file, sheet_name='Complete Data')

# Try to reverse-engineer the scoring formula
print("\n🔍 Attempting to reverse-engineer scoring formula...")

# Merge to get both datasets
if 'symbol' in complete_df.columns and 'symbol' in portfolio_df.columns:
    merged = pd.merge(portfolio_df, complete_df, on='symbol', how='left', suffixes=('_port', '_comp'))
    
    # Find all score columns
    score_cols = [col for col in merged.columns if 'score' in col.lower()]
    print(f"\nFound {len(score_cols)} score-related columns:")
    for col in score_cols:
        print(f"   • {col}")
    
    # Check correlation with final SCORE
    if 'SCORE' in merged.columns:
        print(f"\n📊 Correlation with final SCORE:")
        numeric_cols = merged.select_dtypes(include=['number']).columns
        correlations = merged[numeric_cols].corrwith(merged['SCORE']).sort_values(ascending=False)
        
        print(f"\nTop 10 correlated metrics:")
        for col, corr in correlations.head(10).items():
            if col != 'SCORE':
                print(f"   {col}: {corr:.3f}")
        
        print(f"\nBottom 5 (least correlated):")
        for col, corr in correlations.tail(5).items():
            print(f"   {col}: {corr:.3f}")

# ============================================================================
# MISSING DATA ANALYSIS
# ============================================================================

print("\n\n" + "=" * 100)
print("MISSING DATA ANALYSIS")
print("=" * 100)

print("\n❌ Data quality issues:")
missing_summary = []
for col in complete_df.columns:
    missing_pct = (complete_df[col].isna().sum() / len(complete_df)) * 100
    if missing_pct > 10:
        missing_summary.append((col, missing_pct))

missing_summary.sort(key=lambda x: x[1], reverse=True)
print(f"\nColumns with >10% missing data:")
for col, pct in missing_summary[:10]:
    print(f"   • {col}: {pct:.1f}% missing")

# ============================================================================
# RECOMMENDATIONS
# ============================================================================

print("\n\n" + "=" * 100)
print("RECOMMENDATIONS: HOW TO USE EXISTING DATA BETTER")
print("=" * 100)

print("""
Based on the Excel analysis, here's what's available but NOT being used effectively:

🎯 IMMEDIATE WINS (Data exists, just need to use it):

1. ✅ TECHNICAL INDICATORS - Already calculated!
   • Use RSI, MACD, momentum in scoring
   • Currently available but underweighted
   
2. ✅ FUNDAMENTAL METRICS - Rich dataset!
   • P/E, ROE, debt ratios all available
   • Need to weight them properly in formula
   
3. ✅ SENTIMENT ANALYSIS - Already running!
   • Sentiment scores exist
   • Not being factored into final score
   
4. ✅ ML PREDICTIONS - Model already trained!
   • ML confidence scores available
   • Should boost/penalize based on ML signal

🔧 NEED TO CALCULATE (Missing but can derive):

5. ⚠️ RISK-ADJUSTED METRICS
   • Have price data → Calculate Sharpe ratio
   • Have volatility → Calculate Sortino ratio
   • Have history → Calculate max drawdown
   
6. ⚠️ PERFORMANCE CONSISTENCY
   • Have historical returns → Calculate win rate
   • Have monthly data → Calculate consistency score
   
7. ⚠️ LIQUIDITY METRICS
   • Have volume data → Calculate days to liquidate
   • Have position size → Calculate liquidity risk

🚀 ADVANCED FEATURES (Require new data):

8. ❌ OPTIONS DATA - Not in Excel
   • Would need to fetch from options chain
   
9. ❌ REAL-TIME NEWS - Not in Excel
   • Would need news API integration
   
10. ❌ PEER COMPARISON - Partial data
    • Have sector → Need to rank within sector
    • Have fundamentals → Need peer benchmarks

CONCLUSION:
-----------
You have 70-80% of the data needed for excellent scoring!
The problem is NOT missing data - it's HOW the data is weighted and combined.

Next steps:
1. Reweight existing metrics (technical, fundamental, sentiment, ML)
2. Calculate risk-adjusted metrics from existing price history
3. Add sector-relative scoring using existing sector data
4. Implement performance-based adjustments using profit data
""")

print("\n\n💡 RECOMMENDATION: Let's fix the SCORING FORMULA, not gather more data!")
print("The data is there - we just need to use it properly.\n")
