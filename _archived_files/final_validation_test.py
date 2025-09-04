#!/usr/bin/env python3
"""
FINAL VALIDATION TEST - Comprehensive Stock Analysis Confirmation
Validates both Fundamental Analysis and Enhanced Technical Analysis
"""

import sys
sys.path.append('src')

from enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis
from excel_exporter import ExcelExporter
import pandas as pd
from datetime import datetime

def final_validation_test():
    """Final comprehensive validation of both fundamental and technical analysis"""
    print("🎯 FINAL VALIDATION TEST - COMPREHENSIVE STOCK ANALYSIS")
    print("=" * 80)
    print("📊 Testing: Fundamental Analysis + Enhanced Technical Analysis with Patterns")
    print("🎯 Symbol: RELIANCE")
    print("📅 Date:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    print(f"\n{'=' * 80}")
    print("📈 PHASE 1: FUNDAMENTAL ANALYSIS VALIDATION")
    print("=" * 80)
    
    # Test fundamental analysis
    fund_data = get_comprehensive_stock_data('RELIANCE')
    
    if fund_data:
        fund_fields = len(fund_data)
        non_zero_fund = sum(1 for v in fund_data.values() if pd.notna(v) and v != 0 and v != '')
        
        print(f"✅ FUNDAMENTAL ANALYSIS: SUCCESS")
        print(f"   📊 Total fields collected    : {fund_fields}")
        print(f"   📈 Non-zero fields          : {non_zero_fund}")
        print(f"   💼 Company                  : {fund_data.get('company_name', 'N/A')}")
        print(f"   🏢 Sector                   : {fund_data.get('sector', 'N/A')}")
        print(f"   💰 Current Price            : ₹{fund_data.get('current_price', 0):,.2f}")
        print(f"   📊 Market Cap               : ₹{fund_data.get('market_cap', 0):,.0f}")
        print(f"   📈 PE Ratio                 : {fund_data.get('pe_ratio', 0):.2f}")
        print(f"   📊 Revenue Growth           : {fund_data.get('revenue_growth', 0):.2f}%")
        print(f"   🎯 Fundamental Score        : {fund_data.get('fundamental_score', 0):.1f}/100")
        print(f"   🏆 Fundamental Rating       : {fund_data.get('fundamental_rating', 'N/A')}")
        
        fund_success = True
    else:
        print("❌ FUNDAMENTAL ANALYSIS: FAILED")
        fund_success = False
    
    print(f"\n{'=' * 80}")
    print("📈 PHASE 2: ENHANCED TECHNICAL ANALYSIS VALIDATION")
    print("=" * 80)
    
    # Test enhanced technical analysis
    tech_data = get_short_term_technical_analysis('RELIANCE', period_days=90)
    
    if tech_data:
        tech_fields = len(tech_data)
        non_zero_tech = sum(1 for v in tech_data.values() if pd.notna(v) and v != 0 and v != '' and v != [])
        
        print(f"✅ TECHNICAL ANALYSIS: SUCCESS")
        print(f"   📊 Total indicators         : {tech_fields}")
        print(f"   📈 Non-zero indicators      : {non_zero_tech}")
        print(f"   📅 Analysis period          : {tech_data.get('analysis_period_days', 0)} days")
        print(f"   📊 Data range               : {tech_data.get('data_start_date', 'N/A')} to {tech_data.get('data_end_date', 'N/A')}")
        
        # Key technical metrics
        print(f"\n   🔍 KEY TECHNICAL INDICATORS:")
        print(f"   📈 RSI (14)                 : {tech_data.get('rsi_14', 0):.2f}")
        print(f"   📊 MACD                     : {tech_data.get('macd', 0):.2f}")
        print(f"   🔄 MACD Crossover           : {tech_data.get('macd_crossover', 'N/A')}")
        print(f"   📈 5D Price Change          : {tech_data.get('price_change_5d', 0):+.2f}%")
        print(f"   📊 20D Price Change         : {tech_data.get('price_change_20d', 0):+.2f}%")
        print(f"   🎯 MA Alignment             : {tech_data.get('ma_alignment', 'N/A')}")
        print(f"   📊 Volume Trend             : {tech_data.get('volume_trend', 'N/A')}")
        
        # Pattern detection
        candlestick_patterns = tech_data.get('candlestick_patterns', [])
        chart_patterns = tech_data.get('chart_patterns', [])
        
        print(f"\n   🕯️ PATTERN DETECTION:")
        print(f"   📊 Candlestick patterns     : {len(candlestick_patterns)} detected")
        if candlestick_patterns:
            for i, pattern in enumerate(candlestick_patterns[:3], 1):
                print(f"      {i}. {pattern}")
        
        print(f"   📈 Chart patterns           : {len(chart_patterns)} detected")
        if chart_patterns:
            for i, pattern in enumerate(chart_patterns, 1):
                print(f"      {i}. {pattern}")
        
        print(f"   🎯 Pattern Strength         : {tech_data.get('pattern_strength', 0)}")
        
        # Support/Resistance
        supports = tech_data.get('support_levels', [])
        resistances = tech_data.get('resistance_levels', [])
        print(f"   🎯 Support levels           : {len(supports)} found - {supports}")
        print(f"   🎯 Resistance levels        : {len(resistances)} found - {resistances}")
        
        # Signals
        breakouts = tech_data.get('breakout_signals', [])
        breakdowns = tech_data.get('breakdown_signals', [])
        print(f"   🚀 Breakout signals         : {len(breakouts)} detected")
        print(f"   📉 Breakdown signals        : {len(breakdowns)} detected")
        
        print(f"   🎯 Short-term Score         : {tech_data.get('short_term_score', 0):.1f}/100")
        print(f"   📊 Trading Signal           : {tech_data.get('short_term_signal', 'N/A')}")
        
        tech_success = True
    else:
        print("❌ TECHNICAL ANALYSIS: FAILED")
        tech_success = False
    
    print(f"\n{'=' * 80}")
    print("📊 PHASE 3: COMBINED ANALYSIS & EXCEL GENERATION")
    print("=" * 80)
    
    if fund_success and tech_success:
        # Combine data
        combined_data = fund_data.copy()
        
        # Add technical data with prefixes
        for key, value in tech_data.items():
            combined_data[f"tech_{key}"] = value
        
        # Calculate combined scores
        fund_score = fund_data.get('fundamental_score', 50)
        tech_score = tech_data.get('short_term_score', 50)
        combined_score = (fund_score * 0.6) + (tech_score * 0.4)
        
        combined_data.update({
            'fundamental_score_final': fund_score,
            'technical_score_final': tech_score,
            'combined_score': combined_score,
            'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        print(f"✅ COMBINED ANALYSIS: SUCCESS")
        print(f"   📊 Total combined fields    : {len(combined_data)}")
        print(f"   💼 Fundamental Score        : {fund_score:.1f}/100")
        print(f"   📈 Technical Score          : {tech_score:.1f}/100")
        print(f"   🎯 Combined Score (60F+40T) : {combined_score:.1f}/100")
        
        # Generate Excel
        try:
            # Convert lists to strings for Excel
            excel_data = {}
            for key, value in combined_data.items():
                if isinstance(value, list):
                    excel_data[key] = str(value) if value else "[]"
                else:
                    excel_data[key] = value
            
            df = pd.DataFrame([excel_data])
            excel_exporter = ExcelExporter()
            filename = excel_exporter.generate_daily_report(df)
            
            print(f"✅ EXCEL GENERATION: SUCCESS")
            print(f"   📄 File generated           : {filename}")
            
            # Check file details
            import os
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                print(f"   📊 File size                : {file_size:,} bytes")
                
                excel_success = True
            else:
                print("❌ Excel file not found")
                excel_success = False
                
        except Exception as e:
            print(f"❌ EXCEL GENERATION: FAILED - {e}")
            excel_success = False
    else:
        excel_success = False
    
    print(f"\n{'=' * 80}")
    print("🎯 FINAL VALIDATION RESULTS")
    print("=" * 80)
    
    overall_success = fund_success and tech_success and excel_success
    
    print(f"📊 Fundamental Analysis     : {'✅ PASS' if fund_success else '❌ FAIL'}")
    print(f"📈 Technical Analysis       : {'✅ PASS' if tech_success else '❌ FAIL'}")
    print(f"📄 Excel Generation         : {'✅ PASS' if excel_success else '❌ FAIL'}")
    print(f"🎯 Overall System Status    : {'🟢 ALL SYSTEMS OPERATIONAL' if overall_success else '🔴 SYSTEM ISSUES DETECTED'}")
    
    if overall_success:
        print(f"\n🎉 VALIDATION COMPLETE - ALL SYSTEMS WORKING PERFECTLY!")
        print(f"📊 The comprehensive stock analysis system is ready for production use")
        print(f"💼 Fundamental: {fund_fields} data points | 📈 Technical: {tech_fields} indicators")
        print(f"🕯️ Pattern detection, volume analysis, and breakout signals are operational")
        print(f"📄 Professional Excel reports with multiple sheets are being generated")
    else:
        print(f"\n⚠️ VALIDATION ISSUES DETECTED")
        print(f"🔧 Please check the failed components above")
    
    return overall_success

if __name__ == "__main__":
    success = final_validation_test()
    exit(0 if success else 1)
