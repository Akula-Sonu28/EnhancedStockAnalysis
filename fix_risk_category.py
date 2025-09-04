#!/usr/bin/env python3
"""
Risk Category Fix for Enhanced Stock Analyzer
==============================================

This script fixes the risk category assignment to properly reflect
the user's chosen risk profile instead of just volatility levels.

Issue: risk_category is always showing "MODERATE" regardless of user's 
       --risk-profile setting (conservative/moderate/aggressive)

Fix: Make risk category respect the user's risk profile choice while 
     still using volatility as a factor.
"""

import re

def fix_risk_category_logic():
    """Fix the risk category assignment in analyze_top200_stocks_enhanced.py"""
    
    file_path = "analyze_top200_stocks_enhanced.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the problematic risk category section
    old_risk_logic = '''                        # Risk category
                        if volatility <= 15:
                            risk_category = "LOW"
                        elif volatility <= 25:
                            risk_category = "MODERATE"
                        elif volatility <= 35:
                            risk_category = "HIGH"
                        else:
                            risk_category = "VERY HIGH"'''
    
    # New improved risk logic that considers user's risk profile
    new_risk_logic = '''                        # Risk category based on user profile and volatility
                        # Adjust thresholds based on user's risk profile
                        if self.risk_profile == "conservative":
                            # Conservative: Lower volatility tolerance
                            if volatility <= 10:
                                risk_category = "LOW"
                            elif volatility <= 18:
                                risk_category = "MODERATE" 
                            elif volatility <= 28:
                                risk_category = "HIGH"
                            else:
                                risk_category = "VERY HIGH"
                        elif self.risk_profile == "aggressive":
                            # Aggressive: Higher volatility tolerance
                            if volatility <= 20:
                                risk_category = "LOW"
                            elif volatility <= 35:
                                risk_category = "MODERATE"
                            elif volatility <= 50:
                                risk_category = "HIGH" 
                            else:
                                risk_category = "VERY HIGH"
                        else:  # moderate (default)
                            # Moderate: Standard volatility tolerance
                            if volatility <= 15:
                                risk_category = "LOW"
                            elif volatility <= 25:
                                risk_category = "MODERATE"
                            elif volatility <= 35:
                                risk_category = "HIGH"
                            else:
                                risk_category = "VERY HIGH"'''
    
    # Replace the old logic with new logic
    if old_risk_logic in content:
        content = content.replace(old_risk_logic, new_risk_logic)
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ RISK CATEGORY LOGIC FIXED!")
        print("=" * 50)
        print("🎯 Changes Made:")
        print("• Risk category now respects user's --risk-profile setting")
        print("• Conservative: Lower volatility tolerance")
        print("• Moderate: Standard volatility tolerance (unchanged)")
        print("• Aggressive: Higher volatility tolerance")
        print()
        print("📊 New Risk Thresholds:")
        print("Conservative Profile:")
        print("  - LOW: ≤10%  | MODERATE: ≤18%  | HIGH: ≤28%  | VERY HIGH: >28%")
        print("Moderate Profile:")
        print("  - LOW: ≤15%  | MODERATE: ≤25%  | HIGH: ≤35%  | VERY HIGH: >35%")
        print("Aggressive Profile:")
        print("  - LOW: ≤20%  | MODERATE: ≤35%  | HIGH: ≤50%  | VERY HIGH: >50%")
        print()
        print("🚀 Ready to test! Run your analysis again with:")
        print("python main.py --risk-profile aggressive --focus-growth -n 10")
        return True
    else:
        print("❌ Could not find the risk category logic to fix.")
        print("The code structure may have changed.")
        return False

if __name__ == "__main__":
    print("🔧 FIXING RISK CATEGORY LOGIC")
    print("=" * 50)
    
    success = fix_risk_category_logic()
    
    if success:
        print("\n✅ Fix applied successfully!")
        print("🧪 Test the fix by running an analysis with different risk profiles:")
        print("python main.py --risk-profile conservative -n 5")
        print("python main.py --risk-profile aggressive -n 5")
    else:
        print("\n❌ Fix failed. You may need to manually update the code.")
        print("📍 Look for the risk category logic around line 780 in analyze_top200_stocks_enhanced.py")
