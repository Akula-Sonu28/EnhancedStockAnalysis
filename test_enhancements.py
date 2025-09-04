#!/usr/bin/env python3
"""
Quick Test for Enhanced Stock Analysis
Test the enhancements and fix any remaining issues
"""

import sys
sys.path.append('src')
sys.path.append('.')

import pandas as pd
import numpy as np
from datetime import datetime

# Test if all imports work
try:
    from config import TECHNICAL_WEIGHTS, FUNDAMENTAL_WEIGHTS
    print("✅ Config imports working:", len(TECHNICAL_WEIGHTS), "technical weights")
    
    from src.technical_analyzer import calculate_indicators, compute_technical_score
    print("✅ Technical analyzer imports working")
    
    from enhanced_technical_analyzer import get_short_term_technical_analysis
    print("✅ Enhanced technical analyzer imports working")
    
    from src.enhanced_fundamental_analyzer import get_comprehensive_stock_data
    print("✅ Enhanced fundamental analyzer imports working")
    
    # Test if the main analyzer class can be imported
    from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer, generate_top_10_categories
    print("✅ Main analyzer class imports working")
    
    print("\n🎉 ALL IMPORTS SUCCESSFUL!")
    
    # Create sample data to test TOP 10 function
    sample_data = {
        'symbol': ['RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY'],
        'company_name': ['Reliance Industries', 'TCS Ltd', 'HDFC Bank', 'ICICI Bank', 'Infosys'],
        'fundamental_score': [75, 85, 80, 70, 78],
        'technical_score': [65, 70, 75, 60, 68],
        'undervaluation_score': [70, 60, 75, 80, 65],
        'current_price': [2500, 3200, 1600, 950, 1450],
        'pe_ratio': [12, 25, 18, 15, 22],
        'pb_ratio': [1.8, 3.2, 2.1, 1.5, 2.8],
        'roe': [15, 35, 18, 16, 22],
        'dividend_yield': [2.5, 1.2, 3.1, 2.8, 2.0],
        'revenue_growth': [8, 12, 15, 10, 14],
        'profit_growth': [10, 15, 12, 8, 16]
    }
    
    df = pd.DataFrame(sample_data)
    print("\n📊 Testing TOP 10 Categories with sample data:")
    generate_top_10_categories(df)
    
    print("\n✅ TOP 10 CATEGORIES TEST SUCCESSFUL!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
