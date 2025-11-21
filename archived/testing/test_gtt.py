"""
Test GTT Functionality
======================

Test script to validate GTT order generation with sample data.
This ensures the GTT module works correctly before using with real portfolio.
"""

import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append('.')

from gtt.generator import GTTOrderGenerator
from gtt.config import GTTConfig
from gtt.analyzer import GTTAnalyzer

def create_sample_holdings():
    """Create sample holdings data for testing"""
    holdings_data = {
        'symbol': ['RECLTD', 'BANKBARODA', 'PNB', 'MAHABANK', 'INDIANB', 'CANBK', 'BANKINDIA'],
        'quantity': [40, 80, 150, 400, 27, 150, 150],
        'current_price': [364.4, 232.34, 102.9, 51.89, 663.15, 106.02, 111.66],
        'invested_amount': [14576, 18587, 15435, 20756, 17905, 15903, 16749]
    }
    
    return pd.DataFrame(holdings_data)

def create_sample_enhanced_data():
    """Create sample Enhanced Stock Report data"""
    enhanced_data = {
        'symbol': ['RECLTD', 'BANKBARODA', 'PNB', 'MAHABANK', 'INDIANB', 'CANBK', 'BANKINDIA'],
        'current_price': [364.4, 232.34, 102.9, 51.89, 663.15, 106.02, 111.66],
        'fundamental_rating': ['Average', 'Good', 'Below Average', 'Poor', 'Average', 'Below Average', 'Average'],
        'final_recommendation': ['🟡 HOLD', '🟢 BUY', '🔴 SELL', '🔴 SELL', '🟡 HOLD', '🟡 HOLD', '🟡 HOLD'],
        'risk_category': ['MODERATE', 'LOW', 'HIGH', 'HIGH', 'MODERATE', 'MODERATE', 'MODERATE'],
        '52_week_high': [450.0, 280.0, 130.0, 65.0, 800.0, 140.0, 145.0],
        '52_week_low': [280.0, 180.0, 80.0, 35.0, 500.0, 85.0, 90.0]
    }
    
    return pd.DataFrame(enhanced_data)

def test_gtt_generation():
    """Test GTT order generation"""
    
    print("🧪 TESTING GTT FUNCTIONALITY")
    print("=" * 50)
    
    try:
        # Step 1: Create sample data
        print("📊 Creating sample data...")
        holdings = create_sample_holdings()
        enhanced_data = create_sample_enhanced_data()
        
        print(f"✅ Sample holdings: {len(holdings)} stocks")
        print(f"✅ Sample enhanced data: {len(enhanced_data)} stocks")
        
        # Step 2: Initialize GTT components
        print("\n🔧 Initializing GTT components...")
        config = GTTConfig()
        generator = GTTOrderGenerator(holdings, enhanced_data, config)
        
        print("✅ GTT Generator initialized")
        
        # Step 3: Generate GTT orders
        print("\n🎯 Generating GTT orders...")
        gtt_orders = generator.generate_gtt_orders()
        
        if gtt_orders.empty:
            print("❌ No GTT orders generated!")
            return False
        
        print(f"✅ Generated {len(gtt_orders)} GTT orders")
        
        # Step 4: Display results
        print("\n📋 GTT Orders Preview:")
        generator.print_orders_preview()
        
        # Step 5: Test export functionality
        print("\n📁 Testing Excel export...")
        excel_path = generator.export_to_excel("test_gtt_orders.xlsx")
        
        if os.path.exists(excel_path):
            print(f"✅ Excel file created: {excel_path}")
        else:
            print("❌ Excel export failed!")
            return False
        
        # Step 6: Validate order format
        print("\n🔍 Validating order format...")
        expected_columns = ['type', 'status', 'tradingsymbol', 'exchange', 
                           'trigger_values', 'transaction_type', 'quantity', 'last_price']
        
        missing_columns = [col for col in expected_columns if col not in gtt_orders.columns]
        if missing_columns:
            print(f"❌ Missing columns: {missing_columns}")
            return False
        
        print("✅ All required columns present")
        
        # Step 7: Validate trigger values format
        print("\n🎯 Validating trigger values...")
        for index, row in gtt_orders.head(3).iterrows():
            trigger_values = row['trigger_values']
            if '/' not in trigger_values:
                print(f"❌ Invalid trigger format: {trigger_values}")
                return False
            
            # Try to parse trigger values
            try:
                parts = trigger_values.split('/')
                float(parts[0])
                float(parts[1])
            except:
                print(f"❌ Cannot parse trigger values: {trigger_values}")
                return False
        
        print("✅ Trigger values format is valid")
        
        # Step 8: Show summary
        summary = generator.get_orders_summary()
        print(f"\n📊 SUMMARY:")
        print(f"   ├─ Total Orders: {summary['total_orders']}")
        print(f"   ├─ Buy Orders: {summary['buy_orders']}")
        print(f"   ├─ Sell Orders: {summary['sell_orders']}")
        print(f"   └─ Unique Stocks: {summary['unique_stocks']}")
        
        print("\n✅ ALL TESTS PASSED! GTT functionality is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        print(f"📋 Error details: {traceback.format_exc()}")
        return False

def test_individual_components():
    """Test individual GTT components"""
    
    print("\n🔧 TESTING INDIVIDUAL COMPONENTS")
    print("=" * 40)
    
    try:
        # Test GTTConfig
        print("Testing GTTConfig...")
        config = GTTConfig()
        
        support = config.get_support_level(100.0)
        resistance = config.get_resistance_level(100.0)
        
        if support < 100.0 < resistance:
            print(f"✅ Support/Resistance calculation: {support:.2f}/{resistance:.2f}")
        else:
            print(f"❌ Invalid support/resistance: {support:.2f}/{resistance:.2f}")
            return False
        
        # Test quantity calculation
        sell_qty1, sell_qty2 = config.calculate_sell_quantities(100)
        buy_qty1, buy_qty2 = config.calculate_buy_quantities()
        
        print(f"✅ Sell quantities: {sell_qty1}/{sell_qty2}")
        print(f"✅ Buy quantities: {buy_qty1}/{buy_qty2}")
        
        # Test GTTAnalyzer
        print("\nTesting GTTAnalyzer...")
        enhanced_data = create_sample_enhanced_data()
        analyzer = GTTAnalyzer(enhanced_data)
        
        levels = analyzer.calculate_technical_levels('RECLTD', 364.4)
        print(f"✅ Technical levels for RECLTD: {levels}")
        
        context = analyzer.get_stock_recommendation_context('RECLTD')
        print(f"✅ Recommendation context: {context}")
        
        print("\n✅ All component tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Component test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 GTT MODULE TESTING")
    print("=" * 60)
    print(f"📅 Test Date: {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    print("=" * 60)
    
    # Test individual components first
    component_test = test_individual_components()
    
    if component_test:
        # Test full functionality
        full_test = test_gtt_generation()
        
        if full_test:
            print("\n🎉 ALL GTT TESTS COMPLETED SUCCESSFULLY!")
            print("\nYou can now use GTT functionality with confidence:")
            print("   python portfolio_analysis.py --gtt")
            print("   python portfolio_analysis.py --excel --gtt")
        else:
            print("\n❌ GTT testing failed. Please check the errors above.")
    else:
        print("\n❌ Component testing failed. Please fix the issues first.")