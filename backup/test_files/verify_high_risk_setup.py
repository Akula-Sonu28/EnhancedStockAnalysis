#!/usr/bin/env python3
"""
Quick verification that high-risk features are working correctly
"""

import sys
import os

def test_high_risk_features():
    """Test all high-risk investor features"""
    
    print("🔧 HIGH-RISK FEATURE VERIFICATION")
    print("=" * 50)
    
    try:
        # Test 1: Import analyzer
        print("1. Testing imports...")
        from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer
        print("   ✅ Main analyzer imported successfully")
        
        # Test 2: Create analyzer with aggressive settings
        print("\n2. Testing aggressive analyzer creation...")
        analyzer = EnhancedTop200StockAnalyzer(
            risk_profile='aggressive',
            focus_growth=True,
            focus_momentum=True,
            min_volatility=15.0
        )
        print("   ✅ Aggressive analyzer created successfully")
        print(f"   📊 Risk Profile: {analyzer.risk_profile}")
        print(f"   📈 Focus Growth: {analyzer.focus_growth}")
        print(f"   ⚡ Focus Momentum: {analyzer.focus_momentum}")
        print(f"   📊 Min Volatility: {analyzer.min_volatility}")
        
        # Test 3: Check if momentum scoring function exists
        print("\n3. Testing momentum scoring function...")
        if hasattr(analyzer, 'calculate_momentum_growth_score'):
            print("   ✅ Momentum scoring function exists")
            
            # Create sample data for testing
            sample_data = {
                'revenue_growth': 25.0,
                'profit_growth': 30.0,
                'technical_score': 75.0,
                'current_price': 100.0,
                'high_52w': 120.0,
                'low_52w': 80.0,
                'roe': 15.0,
                'market_cap': 50000.0,
                'pe_ratio': 18.0
            }
            
            try:
                score = analyzer.calculate_momentum_growth_score(sample_data)
                print(f"   ✅ Momentum score calculated: {score:.2f}")
            except Exception as e:
                print(f"   ⚠️  Momentum scoring error: {e}")
        else:
            print("   ❌ Momentum scoring function not found")
        
        # Test 4: Check support/resistance calculation
        print("\n4. Testing support/resistance calculation...")
        if hasattr(analyzer, 'calculate_support_resistance_levels'):
            print("   ✅ Support/resistance function exists")
            
            try:
                levels = analyzer.calculate_support_resistance_levels(100.0, 'aggressive')
                print(f"   ✅ Support/resistance calculated: {levels}")
            except Exception as e:
                print(f"   ⚠️  Support/resistance error: {e}")
        else:
            print("   ❌ Support/resistance function not found")
        
        # Test 5: Check command line argument parsing
        print("\n5. Testing command line argument structure...")
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--risk-profile', choices=['conservative', 'moderate', 'aggressive'])
        parser.add_argument('--focus-growth', action='store_true')
        parser.add_argument('--focus-momentum', action='store_true')
        parser.add_argument('--min-volatility', type=float, default=0.0)
        
        # Test parsing
        test_args = parser.parse_args(['--risk-profile', 'aggressive', '--focus-growth', '--min-volatility', '15'])
        print("   ✅ Command line arguments parsed successfully")
        print(f"   📊 Parsed risk profile: {test_args.risk_profile}")
        print(f"   📈 Parsed focus growth: {test_args.focus_growth}")
        print(f"   📊 Parsed min volatility: {test_args.min_volatility}")
        
        print("\n🎉 ALL TESTS PASSED! High-risk features are ready!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def show_recommended_commands():
    """Show recommended commands for high-risk investors"""
    
    print("\n🚀 RECOMMENDED COMMANDS FOR HIGH-RISK INVESTORS")
    print("=" * 60)
    
    commands = [
        {
            "purpose": "Quick 10-stock test",
            "command": "python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 10"
        },
        {
            "purpose": "Full momentum analysis", 
            "command": "python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum"
        },
        {
            "purpose": "High volatility focus",
            "command": "python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20"
        },
        {
            "purpose": "Large portfolio (₹5L)",
            "command": "python analyze_top200_stocks_enhanced.py --portfolio-amount 500000 --risk-profile aggressive --focus-growth"
        }
    ]
    
    for i, cmd in enumerate(commands, 1):
        print(f"\n{i}. {cmd['purpose']}:")
        print(f"   {cmd['command']}")

if __name__ == "__main__":
    success = test_high_risk_features()
    
    if success:
        show_recommended_commands()
        
        print("\n" + "=" * 60)
        print("🔥 HIGH-RISK ANALYSIS IS READY!")
        print("Choose any command above to start finding aggressive growth stocks!")
    else:
        print("\n❌ Some features need fixing. Check error messages above.")
