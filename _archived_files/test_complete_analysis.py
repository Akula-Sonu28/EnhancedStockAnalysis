#!/usr/bin/env python3
"""
Complete Stock Analysis: Fundamental + Enhanced Short-term Technical Analysis
"""

import sys
sys.path.append('src')

from enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis, display_short_term_analysis
from excel_exporter import ExcelExporter
import pandas as pd
from datetime import datetime

def get_complete_stock_analysis(symbol, technical_period_days=90):
    """Get complete fundamental + enhanced technical analysis"""
    print(f"🎯 COMPLETE STOCK ANALYSIS FOR {symbol}")
    print("=" * 70)
    
    # 1. Get fundamental data
    print("📊 FUNDAMENTAL ANALYSIS:")
    print("-" * 30)
    fund_data = get_comprehensive_stock_data(symbol)
    
    if not fund_data:
        print("❌ Failed to fetch fundamental data")
        return None
    
    print(f"✅ Fundamental: {len(fund_data)} data points")
    
    # 2. Get enhanced technical analysis (short-term focus)
    print(f"\n📈 ENHANCED TECHNICAL ANALYSIS ({technical_period_days} days):")
    print("-" * 50)
    tech_data = get_short_term_technical_analysis(symbol, technical_period_days)
    
    if not tech_data:
        print("❌ Failed to fetch technical data")
        # Continue with fundamental only
        combined_data = fund_data
    else:
        print(f"✅ Technical: {len(tech_data)} indicators & patterns")
        
        # 3. Combine data
        combined_data = fund_data.copy()
        
        # Add technical data with prefix to avoid conflicts
        for key, value in tech_data.items():
            if key not in combined_data:  # Avoid overwriting fundamental data
                combined_data[f"tech_{key}"] = value
            else:
                combined_data[f"tech_{key}"] = value
    
    # 4. Calculate enhanced overall score
    print(f"\n🎯 SCORING & RECOMMENDATIONS:")
    print("-" * 35)
    
    fund_score = combined_data.get('fundamental_score', 50)
    tech_score = tech_data.get('short_term_score', 50) if tech_data else 50
    
    # Weighted scoring: 60% fundamental (long-term), 40% technical (short-term)
    overall_score = (fund_score * 0.6) + (tech_score * 0.4)
    
    combined_data.update({
        'fundamental_score_weighted': fund_score,
        'technical_score_weighted': tech_score,
        'overall_score': overall_score,
        'investment_horizon': 'Mixed (Fundamental: Long-term, Technical: Short-term)',
        'final_recommendation': get_mixed_recommendation(fund_score, tech_score, overall_score)
    })
    
    print(f"   📈 Fundamental Score : {fund_score:.1f}/100")
    print(f"   📊 Technical Score   : {tech_score:.1f}/100")
    print(f"   🎯 Overall Score     : {overall_score:.1f}/100")
    print(f"   🎯 Recommendation    : {combined_data['final_recommendation']}")
    
    return combined_data, tech_data

def get_mixed_recommendation(fund_score, tech_score, overall_score):
    """Get recommendation considering both fundamental and technical signals"""
    
    # Strong signals (either very good or very bad)
    if fund_score >= 70 and tech_score >= 70:
        return "🟢 STRONG BUY (Both signals positive)"
    elif fund_score <= 30 and tech_score <= 30:
        return "🔴 STRONG SELL (Both signals negative)"
    
    # Mixed signals - use overall score with context
    elif fund_score >= 60 and tech_score <= 40:
        return "🟡 LONG-TERM BUY / SHORT-TERM CAUTION (Good fundamentals, weak technicals)"
    elif fund_score <= 40 and tech_score >= 60:
        return "🟠 SHORT-TERM BUY / LONG-TERM CAUTION (Weak fundamentals, good technicals)"
    
    # Standard overall score interpretation
    elif overall_score >= 70:
        return "🟢 BUY"
    elif overall_score >= 60:
        return "🟢 WEAK BUY"
    elif overall_score >= 55:
        return "🟡 HOLD (Slight positive bias)"
    elif overall_score >= 45:
        return "🟡 HOLD"
    elif overall_score >= 40:
        return "🟠 WEAK SELL"
    elif overall_score >= 30:
        return "🔴 SELL"
    else:
        return "🔴 STRONG SELL"

def display_complete_analysis(combined_data, tech_data=None):
    """Display complete analysis summary"""
    if not combined_data:
        print("❌ No analysis data available")
        return
    
    symbol = combined_data.get('symbol', 'UNKNOWN')
    
    print(f"\n📋 COMPLETE ANALYSIS SUMMARY FOR {symbol}")
    print("=" * 70)
    
    # Key fundamental metrics
    print("\n💼 KEY FUNDAMENTAL METRICS:")
    print("-" * 35)
    fund_keys = [
        ('Company', 'company_name'),
        ('Sector', 'sector'),
        ('Current Price', 'current_price'),
        ('Market Cap', 'market_cap'),
        ('PE Ratio', 'pe_ratio'),
        ('Revenue Growth', 'revenue_growth'),
        ('Fundamental Score', 'fundamental_score_weighted')
    ]
    
    for name, key in fund_keys:
        if key in combined_data:
            value = combined_data[key]
            if isinstance(value, (int, float)):
                if 'Price' in name:
                    print(f"   {name:<18}: ₹{value:,.2f}")
                elif 'Market Cap' in name:
                    print(f"   {name:<18}: ₹{value:,.0f}")
                elif '%' in name or 'Growth' in name:
                    print(f"   {name:<18}: {value:.2f}%")
                else:
                    print(f"   {name:<18}: {value:.2f}")
            else:
                print(f"   {name:<18}: {value}")
    
    # Key technical signals
    print("\n📈 KEY TECHNICAL SIGNALS:")
    print("-" * 30)
    if tech_data:
        tech_keys = [
            ('Short-term Score', 'short_term_score'),
            ('Trading Signal', 'short_term_signal'),
            ('5D Price Change', 'price_change_5d'),
            ('20D Price Change', 'price_change_20d'),
            ('RSI (14)', 'rsi_14'),
            ('MACD Crossover', 'macd_crossover'),
            ('MA Alignment', 'ma_alignment'),
            ('Volume Trend', 'volume_trend')
        ]
        
        for name, key in tech_keys:
            if key in tech_data:
                value = tech_data[key]
                if isinstance(value, (int, float)):
                    if 'Change' in name:
                        emoji = "📈" if value > 0 else "📉" if value < 0 else "➡️"
                        print(f"   {name:<18}: {emoji} {value:+.2f}%")
                    else:
                        print(f"   {name:<18}: {value:.2f}")
                else:
                    print(f"   {name:<18}: {value}")
    else:
        print("   Technical analysis not available")
    
    # Pattern summary
    if tech_data:
        patterns = tech_data.get('candlestick_patterns', [])
        chart_patterns = tech_data.get('chart_patterns', [])
        
        if patterns or chart_patterns:
            print("\n🕯️ DETECTED PATTERNS:")
            print("-" * 25)
            
            if patterns:
                print("   Candlestick Patterns:")
                for pattern in patterns[:3]:  # Show top 3
                    print(f"     • {pattern}")
            
            if chart_patterns:
                print("   Chart Patterns:")
                for pattern in chart_patterns:
                    print(f"     • {pattern}")
    
    # Final recommendation
    print(f"\n🎯 FINAL INVESTMENT RECOMMENDATION:")
    print("=" * 45)
    print(f"   Overall Score     : {combined_data.get('overall_score', 0):.1f}/100")
    print(f"   Recommendation    : {combined_data.get('final_recommendation', 'N/A')}")
    print(f"   Investment Horizon: {combined_data.get('investment_horizon', 'N/A')}")

def test_complete_analysis():
    """Test complete analysis with RELIANCE"""
    print("🔧 TESTING COMPLETE STOCK ANALYSIS")
    print("=" * 60)
    
    symbol = "RELIANCE"
    
    # Get complete analysis
    complete_data, tech_data = get_complete_stock_analysis(symbol, technical_period_days=90)
    
    if complete_data:
        # Display summary
        display_complete_analysis(complete_data, tech_data)
        
        # Display detailed technical analysis
        if tech_data:
            display_short_term_analysis(tech_data)
        
        # Generate Excel report
        print(f"\n📊 GENERATING EXCEL REPORT:")
        print("-" * 35)
        
        try:
            # Flatten data for Excel
            excel_data = complete_data.copy()
            
            # Convert lists to strings for Excel compatibility
            for key, value in excel_data.items():
                if isinstance(value, list):
                    excel_data[key] = str(value)
            
            df = pd.DataFrame([excel_data])
            excel_exporter = ExcelExporter()
            filename = excel_exporter.generate_daily_report(df)
            
            print(f"✅ Complete analysis report: {filename}")
            
            # Final summary
            total_fields = len(excel_data)
            non_zero_fields = sum(1 for v in excel_data.values() if pd.notna(v) and v != 0 and v != '')
            
            print(f"\n🎉 COMPLETE ANALYSIS SUMMARY:")
            print("=" * 40)
            print(f"📊 Total data fields      : {total_fields}")
            print(f"📈 Non-zero fields        : {non_zero_fields}")
            print(f"💼 Fundamental score      : {complete_data.get('fundamental_score_weighted', 0):.1f}/100")
            print(f"📈 Technical score        : {complete_data.get('technical_score_weighted', 0):.1f}/100")
            print(f"🎯 Overall score          : {complete_data.get('overall_score', 0):.1f}/100")
            print(f"🎯 Final recommendation   : {complete_data.get('final_recommendation', 'N/A')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Excel generation failed: {e}")
            return False
    else:
        print("❌ Complete analysis failed")
        return False

if __name__ == "__main__":
    success = test_complete_analysis()
    
    if success:
        print("\n🎉 COMPLETE ANALYSIS TEST PASSED!")
        print("📊 Both fundamental and enhanced technical data with patterns are now integrated")
    else:
        print("\n❌ COMPLETE ANALYSIS TEST FAILED!")
        print("🔧 Check fundamental and technical data collection")
