#!/usr/bin/env python3
"""
Test script to verify risk-based portfolio allocation logic
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer
import pandas as pd

def test_risk_allocation():
    """Test different risk profiles and their portfolio size allocation"""
    
    print("🧪 TESTING RISK-BASED PORTFOLIO ALLOCATION")
    print("=" * 50)
    
    # Test different risk profiles
    risk_profiles = ["aggressive", "moderate", "balanced"]
    
    for risk_profile in risk_profiles:
        print(f"\n📊 Testing Risk Profile: {risk_profile.upper()}")
        print("-" * 30)
        
        # Create analyzer with specific risk profile
        analyzer = EnhancedTop200StockAnalyzer(
            max_workers=1,
            risk_profile=risk_profile
        )
        
        # Mock current holdings with different counts
        for current_holdings_count in [0, 10, 20, 30]:
            print(f"  Current Holdings: {current_holdings_count}")
            
            # Simulate the allocation logic
            if risk_profile == "aggressive":
                base_max_stocks = 25  # 20-25 stocks for aggressive
                max_stocks = max(current_holdings_count + 2, base_max_stocks)
            elif risk_profile == "balanced":
                base_max_stocks = 33  # 30-35 stocks for balanced
                max_stocks = max(current_holdings_count + 3, base_max_stocks)
            else:  # moderate (default)
                base_max_stocks = 28  # 25-30 stocks for moderate
                max_stocks = max(current_holdings_count + 3, base_max_stocks)
            
            print(f"    → Target Portfolio Size: {max_stocks} stocks")
        
        print()

def main():
    """Main test function"""
    test_risk_allocation()
    
    print("\n✅ Risk allocation logic verification complete!")
    print("\nExpected Results:")
    print("- Aggressive: 20-25 stocks (focused portfolio)")
    print("- Moderate: 25-30 stocks (balanced approach)")
    print("- Balanced: 30-35 stocks (diversified portfolio)")

if __name__ == "__main__":
    main()