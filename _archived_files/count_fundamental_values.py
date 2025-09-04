#!/usr/bin/env python3
"""
Count Fundamental Values Retrieved
"""

import sys
sys.path.append('src')

from enhanced_fundamental_analyzer import get_comprehensive_stock_data
import pandas as pd

def count_fundamental_values():
    """Count the exact number of fundamental values retrieved"""
    print("🔍 COUNTING FUNDAMENTAL VALUES FOR RELIANCE")
    print("=" * 60)
    
    # Get comprehensive fundamental data
    fund_data = get_comprehensive_stock_data('RELIANCE')
    
    if not fund_data:
        print("❌ Failed to retrieve fundamental data")
        return
    
    # Count all fields
    total_fields = len(fund_data)
    
    # Count non-empty/non-zero fields
    non_empty_fields = 0
    zero_fields = 0
    empty_fields = 0
    
    print("📊 FUNDAMENTAL DATA BREAKDOWN:")
    print("-" * 40)
    
    # Categorize the data
    categories = {
        'Company Info': ['symbol', 'company_name', 'sector', 'industry', 'website', 'business_summary', 'employees', 'country'],
        'Market Data': ['current_price', 'market_cap', 'enterprise_value', 'shares_outstanding', 'float_shares', 'beta', '52_week_high', '52_week_low', 'avg_volume'],
        'Valuation Ratios': ['pe_ratio', 'forward_pe', 'pb_ratio', 'ps_ratio', 'peg_ratio', 'ev_ebitda', 'ev_revenue', 'price_to_book', 'price_to_sales'],
        'Financial Health': ['debt_to_equity', 'current_ratio', 'quick_ratio', 'total_cash', 'total_debt', 'cash_per_share'],
        'Profitability': ['roe', 'roa', 'roic', 'gross_margin', 'operating_margin', 'net_margin', 'ebitda_margin'],
        'Growth Metrics': ['revenue_growth', 'earnings_growth', 'quarterly_revenue_growth', 'quarterly_earnings_growth'],
        'Per Share Data': ['eps', 'forward_eps', 'book_value', 'revenue_per_share', 'cashflow_per_share'],
        'Dividends': ['dividend_yield', 'payout_ratio', 'dividend_rate'],
        'Ownership': ['insider_ownership', 'institutional_ownership'],
        'Price Performance': ['price_change_1d', 'price_change_1w', 'price_change_1m', 'price_change_3m', 'price_change_6m', 'price_change_1y'],
        'Volume & Volatility': ['volume', 'avg_volume', 'volatility'],
        'Analysis Results': ['fundamental_score', 'fundamental_rating', 'fundamental_analysis']
    }
    
    # Count by category
    for category, fields in categories.items():
        category_count = 0
        category_non_empty = 0
        
        print(f"\n📋 {category}:")
        for field in fields:
            if field in fund_data:
                category_count += 1
                value = fund_data[field]
                
                if pd.notna(value) and value != 0 and value != '':
                    category_non_empty += 1
                    print(f"   ✅ {field:<25}: {value}")
                else:
                    print(f"   ⚪ {field:<25}: {value} (empty/zero)")
        
        print(f"   📊 Category Total: {category_count} fields | Non-empty: {category_non_empty}")
    
    # Overall count
    for key, value in fund_data.items():
        if pd.notna(value) and value != 0 and value != '':
            non_empty_fields += 1
        elif value == 0:
            zero_fields += 1
        else:
            empty_fields += 1
    
    print(f"\n📊 OVERALL FUNDAMENTAL DATA SUMMARY:")
    print("=" * 50)
    print(f"📈 Total fields retrieved     : {total_fields}")
    print(f"✅ Non-empty fields          : {non_empty_fields}")
    print(f"⚪ Zero/empty fields         : {zero_fields + empty_fields}")
    print(f"📊 Data completeness         : {(non_empty_fields/total_fields)*100:.1f}%")
    
    print(f"\n🏆 FUNDAMENTAL VALUE CATEGORIES:")
    print("-" * 35)
    for category, fields in categories.items():
        available = sum(1 for field in fields if field in fund_data)
        filled = sum(1 for field in fields if field in fund_data and pd.notna(fund_data[field]) and fund_data[field] != 0 and fund_data[field] != '')
        print(f"   {category:<20}: {filled}/{available} fields")
    
    return total_fields, non_empty_fields

if __name__ == "__main__":
    total, non_empty = count_fundamental_values()
    
    print(f"\n🎯 FINAL COUNT:")
    print(f"📊 Total Fundamental Values: {total}")
    print(f"✅ Meaningful Values: {non_empty}")
