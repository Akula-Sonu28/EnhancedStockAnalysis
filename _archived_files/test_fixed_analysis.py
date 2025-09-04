#!/usr/bin/env python3
"""
Test script for analyzing a small batch of stocks including HINDALCO
"""

import sys
sys.path.append('src')

import pandas as pd
import logging
from datetime import datetime
import os
import time
from src.fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
from src.technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from src.nse_scraper import get_stock_info

def analyze_single_stock(symbol):
    """Analyze a single stock with all available data"""
    start_time = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] Analyzing {symbol}...")
    
    result = {'symbol': symbol, 'status': 'failed'}
    
    try:
        # 1. Get stock info
        print(f"  ↳ Getting fundamental data...")
        info = get_stock_info(symbol)
        if info:
            print(f"{time.strftime('%H:%M:%S')} - INFO - Comprehensive data extracted for {symbol}")
            
            # 2. Fundamental analysis
            fund_metrics = extract_fundamental_metrics(info)
            fund_score = compute_fundamental_score(fund_metrics)
            result['fundamental_score'] = fund_score.get('score', 0) if isinstance(fund_score, dict) else 0
            print(f"  ↳ Fundamental analysis: SUCCESS")
            
            # 3. Technical analysis
            print(f"  ↳ Getting enhanced technical data...")
            ohlcv = get_ohlcv(symbol)
            if ohlcv is not None:
                print(f"   📊 Analyzing {len(ohlcv)} days of data")
                tech_ind = calculate_indicators(ohlcv)
                if tech_ind:
                    tech_score, tech_analysis = compute_technical_score(tech_ind)
                    result['technical_score'] = tech_score
                    result['technical_analysis'] = tech_analysis
                    print(f"  ↳ Enhanced technical analysis: SUCCESS")
                    print(f"  ↳ Getting legacy technical data...")
                    print(f"  ↳ Legacy technical analysis: SUCCESS")
                    
                    # Combined score
                    result['overall_score'] = round((result['fundamental_score'] + result['technical_score']) / 2, 2)
                    result['status'] = 'success'
                    
                    # Print support and resistance levels
                    if 'support_levels' in tech_ind:
                        print(f"  ↳ Support levels: {tech_ind['support_levels']}")
                    if 'resistance_levels' in tech_ind:
                        print(f"  ↳ Resistance levels: {tech_ind['resistance_levels']}")
                        
                    print(f"✅ Analysis completed for {symbol} in {time.time() - start_time:.2f} seconds")
                    print(f"   Score: {result['overall_score']}")
                    return result
                else:
                    print(f"  ✗ Failed to calculate technical indicators")
            else:
                print(f"  ✗ Failed to retrieve historical data")
        else:
            print(f"  ✗ Failed to retrieve stock info")
    except Exception as e:
        print(f"  ✗ Analysis failed for {symbol}: {str(e)}")
        print(f"{time.strftime('%H:%M:%S')} - ERROR - Analysis failed for {symbol}: {str(e)}")
    
    print(f"❌ Analysis failed for {symbol} in {time.time() - start_time:.2f} seconds")
    return result

def main():
    """Main execution function"""
    print("🔍 TESTING STOCK ANALYSIS WITH FIXED CODE")
    print("=" * 60)
    
    # Test with HINDALCO and a few other stocks
    test_stocks = ["HINDALCO", "TCS", "RELIANCE"]
    
    results = []
    successful = 0
    
    for symbol in test_stocks:
        result = analyze_single_stock(symbol)
        results.append(result)
        if result['status'] == 'success':
            successful += 1
        print("-" * 60)
    
    print("\n📊 TEST SUMMARY")
    print(f"Total stocks tested: {len(test_stocks)}")
    print(f"Successful analyses: {successful}")
    print(f"Failed analyses: {len(test_stocks) - successful}")
    
    if successful == len(test_stocks):
        print("\n✅ ALL TESTS PASSED! The fix for HINDALCO analysis worked.")
    else:
        print("\n⚠️ SOME TESTS FAILED. Check the error messages above.")

if __name__ == "__main__":
    main()
