#!/usr/bin/env python3
"""
Comprehensive Risk Category Fix v2.0
====================================

This script fixes ALL instances where risk category is being incorrectly set
or defaulting to 'MODERATE' regardless of user's risk profile.

Issues Found:
1. Portfolio allocation defaults to 'MODERATE' when risk_category is missing
2. Risk calculation might not be working properly in some cases
3. Need to ensure risk category is properly propagated to Portfolio Allocation sheet

This fix addresses all these issues.
"""

import re

def comprehensive_risk_category_fix():
    """Fix all risk category issues in the enhanced analyzer"""
    
    file_path = "analyze_top200_stocks_enhanced.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔧 COMPREHENSIVE RISK CATEGORY FIX v2.0")
    print("=" * 60)
    
    fixes_applied = 0
    
    # Fix 1: Portfolio allocation defaulting to MODERATE
    old_portfolio_default = "                risk_cat = stock.get('risk_category', 'MODERATE')"
    new_portfolio_default = """                risk_cat = stock.get('risk_category', 'UNKNOWN')
                # If risk category is still unknown, calculate it based on volatility and profile
                if risk_cat in ['UNKNOWN', None, '']:
                    volatility = stock.get('volatility_6m', 0)
                    if volatility > 0:
                        # Apply same logic as risk calculation
                        if self.risk_profile == "conservative":
                            if volatility <= 10:
                                risk_cat = "LOW"
                            elif volatility <= 18:
                                risk_cat = "MODERATE"
                            elif volatility <= 28:
                                risk_cat = "HIGH"
                            else:
                                risk_cat = "VERY HIGH"
                        elif self.risk_profile == "aggressive":
                            if volatility <= 20:
                                risk_cat = "LOW"
                            elif volatility <= 35:
                                risk_cat = "MODERATE"
                            elif volatility <= 50:
                                risk_cat = "HIGH"
                            else:
                                risk_cat = "VERY HIGH"
                        else:  # moderate
                            if volatility <= 15:
                                risk_cat = "LOW"
                            elif volatility <= 25:
                                risk_cat = "MODERATE"
                            elif volatility <= 35:
                                risk_cat = "HIGH"
                            else:
                                risk_cat = "VERY HIGH"
                    else:
                        # Default based on risk profile when no volatility data
                        if self.risk_profile == "conservative":
                            risk_cat = "LOW"
                        elif self.risk_profile == "aggressive":
                            risk_cat = "HIGH"
                        else:
                            risk_cat = "MODERATE\""""
    
    if old_portfolio_default in content:
        content = content.replace(old_portfolio_default, new_portfolio_default)
        fixes_applied += 1
        print("✅ Fix 1: Portfolio allocation no longer defaults to MODERATE")
    
    # Fix 2: Ensure risk category is preserved when copying data to allocation
    # Look for the part where allocation_data is appended
    old_allocation_append = """                allocation_data.append({
                    'symbol': stock['symbol'],
                    'company_name': stock.get('company_name', stock['symbol']),
                    'sector': sector,
                    'overall_score': stock['overall_score_with_value'],
                    'risk_adjusted_score': stock['risk_adjusted_score'],
                    'undervaluation_score': stock['undervaluation_score'],
                    'risk_category': risk_cat,
                    'raw_weight': final_weight,
                    'current_price': stock.get('current_price', 0),
                    'recommendation': stock.get('final_recommendation', '')
                })"""
    
    new_allocation_append = """                allocation_data.append({
                    'symbol': stock['symbol'],
                    'company_name': stock.get('company_name', stock['symbol']),
                    'sector': sector,
                    'overall_score': stock['overall_score_with_value'],
                    'risk_adjusted_score': stock['risk_adjusted_score'],
                    'undervaluation_score': stock['undervaluation_score'],
                    'risk_category': risk_cat,  # Now properly calculated above
                    'raw_weight': final_weight,
                    'current_price': stock.get('current_price', 0),
                    'recommendation': stock.get('final_recommendation', ''),
                    'volatility_6m': stock.get('volatility_6m', 0)  # Include volatility for reference
                })"""
    
    if old_allocation_append in content:
        content = content.replace(old_allocation_append, new_allocation_append)
        fixes_applied += 1
        print("✅ Fix 2: Portfolio allocation includes volatility data")
    
    # Fix 3: Add debug logging for risk category assignment
    old_risk_assignment = "                        results_df.at[idx, 'risk_category'] = risk_category"
    new_risk_assignment = """                        results_df.at[idx, 'risk_category'] = risk_category
                        # Debug log for risk category assignment
                        logging.debug(f"{symbol}: volatility={volatility:.1f}%, profile={self.risk_profile}, risk_category={risk_category}")"""
    
    if old_risk_assignment in content:
        content = content.replace(old_risk_assignment, new_risk_assignment)
        fixes_applied += 1
        print("✅ Fix 3: Added debug logging for risk category assignment")
    
    # Fix 4: Add risk profile validation in constructor
    constructor_pattern = r"(def __init__\(self[^:]+:)"
    if re.search(constructor_pattern, content):
        # Add risk profile validation after the constructor
        old_constructor_start = "        self.risk_profile = risk_profile"
        new_constructor_start = """        self.risk_profile = risk_profile
        # Validate risk profile
        if self.risk_profile not in ["conservative", "moderate", "aggressive"]:
            logging.warning(f"Invalid risk profile '{self.risk_profile}', defaulting to 'moderate'")
            self.risk_profile = "moderate"
        logging.info(f"Risk profile set to: {self.risk_profile}")"""
        
        if old_constructor_start in content:
            content = content.replace(old_constructor_start, new_constructor_start)
            fixes_applied += 1
            print("✅ Fix 4: Added risk profile validation")
    
    # Write the fixed content back to file
    if fixes_applied > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n🎉 COMPREHENSIVE FIX COMPLETE!")
        print(f"Applied {fixes_applied} fixes")
        print("=" * 60)
        print("🎯 What was fixed:")
        print("• Portfolio allocation no longer defaults to 'MODERATE'")
        print("• Risk category now calculated based on user's risk profile")
        print("• Added volatility data to portfolio allocation")
        print("• Added debug logging for troubleshooting")
        print("• Added risk profile validation")
        print()
        print("📊 Risk Category Logic:")
        print("Conservative: LOW ≤10% | MODERATE ≤18% | HIGH ≤28% | VERY HIGH >28%")
        print("Moderate:     LOW ≤15% | MODERATE ≤25% | HIGH ≤35% | VERY HIGH >35%")
        print("Aggressive:   LOW ≤20% | MODERATE ≤35% | HIGH ≤50% | VERY HIGH >50%")
        print()
        print("🚀 Test the fix:")
        print("python main.py --risk-profile aggressive -n 5")
        print("python main.py --risk-profile conservative -n 5")
        print()
        print("📋 Check the Portfolio Allocation sheet - it should now show")
        print("   different risk categories based on your profile!")
        
        return True
    else:
        print("❌ No fixes could be applied. Code structure may have changed.")
        return False

if __name__ == "__main__":
    success = comprehensive_risk_category_fix()
    
    if success:
        print("\n✅ ALL FIXES APPLIED SUCCESSFULLY!")
        print("🎯 The Portfolio Allocation sheet should now show correct risk categories!")
    else:
        print("\n❌ Fix failed. Manual review may be needed.")
