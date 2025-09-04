#!/usr/bin/env python3
"""
Test Excel generation with comprehensive data
"""

import os
import sys
sys.path.append('src')

from enhanced_fundamental_analyzer import get_comprehensive_stock_data
from excel_exporter import ExcelExporter
import pandas as pd
from datetime import datetime

def test_comprehensive_excel():
    """Test comprehensive Excel generation with all data fields"""
    print("🔧 TESTING COMPREHENSIVE EXCEL GENERATION")
    print("=" * 80)
    
    # Get comprehensive data for RELIANCE
    print("📊 Fetching comprehensive data for RELIANCE...")
    stock_data = get_comprehensive_stock_data('RELIANCE')
    
    if not stock_data:
        print("❌ Failed to fetch stock data")
        return False
    
    print(f"✅ Data fetched successfully!")
    print(f"📈 Total data fields: {len(stock_data)}")
    
    # Print available data fields
    print("\n📋 AVAILABLE DATA FIELDS:")
    non_zero_count = 0
    for i, (key, value) in enumerate(stock_data.items(), 1):
        if pd.notna(value) and value != 0:
            print(f"{i:2d}. {key}: {value}")
            non_zero_count += 1
    
    print(f"\n📊 Non-zero data fields: {non_zero_count}")
    
    # Convert to DataFrame
    df = pd.DataFrame([stock_data])
    
    # Create Excel exporter
    excel_exporter = ExcelExporter()
    
    # Generate Excel report
    print(f"\n📊 Generating comprehensive Excel report...")
    try:
        filename = excel_exporter.generate_daily_report(df)
        print(f"✅ Excel report generated: {filename}")
        
        # Check file size
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"📁 File size: {file_size:,} bytes")
            
            if file_size > 10000:  # Expect larger file with comprehensive data
                print("🎉 SUCCESS: Comprehensive data appears to be included!")
                return True
            else:
                print("⚠️  WARNING: File size suggests limited data")
                return False
        else:
            print("❌ Excel file was not created")
            return False
            
    except Exception as e:
        print(f"❌ Excel generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_comprehensive_excel()
    
    if success:
        print("\n🎉 COMPREHENSIVE EXCEL TEST PASSED!")
        print("📊 All comprehensive data should now be visible in Excel")
    else:
        print("\n❌ COMPREHENSIVE EXCEL TEST FAILED!")
        print("🔧 Check data collection and Excel generation")
