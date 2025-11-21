import pandas as pd

# Load the latest report
df = pd.read_excel('reports/Enhanced_Stock_Report_20251016_182700.xlsx', sheet_name='Portfolio Allocation')

print("="*80)
print("CURRENT PORTFOLIO ALLOCATION COLUMNS (AFTER FILTERING):")
print("="*80)
print(f"\nTotal: {len(df.columns)} columns\n")
for i, col in enumerate(df.columns, 1):
    print(f"{i:2d}. {col}")

# Now check what the essential_cols list should have filtered to
print("\n" + "="*80)
print("EXPECTED COLUMNS BASED ON essential_cols:")
print("="*80)

expected_cols = [
    # TIER 1: CRITICAL - Decision Making
    'action_recommendation', 'profit_booking_timing', 'investment_amount', 
    'suggested_quantity', 'current_quantity', 'current_value', 'current_profit_pct',
    'profit_booking_pct', 'risk_adjusted_score', 'improved_overall_score',
    
    # TIER 2: IMPORTANT - Analysis
    'pe_ratio', 'roe', 'debt_to_equity', 'risk_category', 'current_price',
    '52_week_high', '52_week_low', 'enhanced_price_change_20d',
    
    # TIER 3: NICE TO HAVE
    'sector', 'stock_classification', 'holdings_rank', 'portfolio_weight',
    'exit_reason', 'is_current_holding', 'support_level', 'resistance_level',
    'enhanced_rsi_14', 'volatility', 'improved_fundamental_quality',
    'improved_momentum_technical', 'undervaluation_score'
]

print(f"\nExpected: {len(expected_cols)} columns")
print(f"Actual:   {len(df.columns)} columns")
print(f"Missing:  {len(expected_cols) - len(df.columns)} columns")

print("\n" + "="*80)
print("DIAGNOSIS:")
print("="*80)
print("""
The issue is that essential_cols list has 33 columns defined,
but only 8 are making it to the Excel file.

This means the line:
    existing_cols = [col for col in essential_cols if col in alloc_df.columns]

Is filtering out most columns because they don't exist in alloc_df.

The problem is likely that allocation_data dictionary is NOT being populated
with these fields for existing holdings (lines 4090-4150).
""")
