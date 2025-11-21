#!/usr/bin/env python3
"""
Test integration of corrected merged portfolio with analyze_top200_stocks_enhanced.py
"""

import pandas as pd
import glob
import os

print("\n" + "="*80)
print("TESTING PORTFOLIO INTEGRATION WITH ANALYSIS SCRIPT")
print("="*80)

# Check what merged portfolio file will be loaded
merged_files = glob.glob('reports/merged_portfolio_*.xlsx')
if merged_files:
    latest_merged = max(merged_files, key=os.path.getmtime)
    print(f"\n📁 Latest merged portfolio file: {latest_merged}")
    print(f"   Modified: {pd.Timestamp(os.path.getmtime(latest_merged), unit='s')}")
    
    # Load and check key quantities
    df = pd.read_excel(latest_merged)
    print(f"\n📊 Portfolio loaded: {len(df)} stocks")
    
    # Check key stocks
    print("\n" + "="*80)
    print("KEY STOCK QUANTITIES (Should match corrected values)")
    print("="*80)
    
    test_stocks = {
        'HDFCBANK': 31,     # Should be 31 (was 36, sold 5)
        'BAJAJHLDNG': 2,    # Should be 2 (was 1, bought 1)
        'CANBK': 289,       # Should be 289 (was 320, sold 31)
        'AXISBANK': 26,     # Should be 26 (was 28, sold 2)
    }
    
    all_correct = True
    for stock, expected_qty in test_stocks.items():
        if stock in df['Instrument'].values:
            actual_qty = int(df[df['Instrument']==stock]['Qty.'].values[0])
            status = "✅ CORRECT" if actual_qty == expected_qty else "❌ WRONG"
            print(f"{stock:12} : {actual_qty:4} shares  (Expected: {expected_qty:4})  {status}")
            if actual_qty != expected_qty:
                all_correct = False
        else:
            print(f"{stock:12} : NOT FOUND in portfolio")
            all_correct = False
    
    print("="*80)
    
    if all_correct:
        print("\n✅ SUCCESS! All quantities are CORRECT!")
        print("   The analysis script will use the corrected merged portfolio.")
        print("\n🚀 You can safely run: python analyze_top200_stocks_enhanced.py")
    else:
        print("\n❌ WARNING! Some quantities are WRONG!")
        print("   Run: python quick_portfolio_merge.py")
        print("   Then retry the analysis.")
    
    print("="*80)
    
else:
    print("\n❌ No merged portfolio files found!")
    print("   Run: python quick_portfolio_merge.py")
    print("="*80)
