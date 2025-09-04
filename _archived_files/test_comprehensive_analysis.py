#!/usr/bin/env python3
"""
Enhanced Comprehensive Stock Analyzer with Technical Analysis Integration
"""

import sys
sys.path.append('src')

from enhanced_fundamental_analyzer import get_comprehensive_stock_data
from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from excel_exporter import ExcelExporter
import pandas as pd
import yfinance as yf
from datetime import datetime
import logging

def get_comprehensive_stock_analysis(symbol):
    """Get complete fundamental + technical analysis for a stock"""
    print(f"🔍 COMPREHENSIVE ANALYSIS FOR {symbol}")
    print("=" * 60)
    
    # Get fundamental data
    print("📊 Fetching fundamental data...")
    fund_data = get_comprehensive_stock_data(symbol)
    
    if not fund_data:
        print("❌ Failed to fetch fundamental data")
        return None
    
    print(f"✅ Fundamental data: {len(fund_data)} fields")
    
    # Get technical data
    print("📈 Fetching technical data...")
    tech_data = get_technical_analysis(symbol)
    
    if tech_data:
        print(f"✅ Technical data: {len(tech_data)} indicators")
        # Merge technical data into fundamental data
        fund_data.update(tech_data)
    else:
        print("⚠️  Limited technical data available")
    
    # Calculate overall score if we have both fundamental and technical scores
    if 'fundamental_score' in fund_data and 'technical_score' in fund_data:
        # Weight: 40% fundamental, 40% technical, 20% reserved for sentiment
        fund_score = fund_data['fundamental_score']
        tech_score = fund_data['technical_score']
        
        # For now, use 50-50 weighting (can adjust based on preference)
        overall_score = (fund_score * 0.5) + (tech_score * 0.5)
        fund_data['overall_score'] = overall_score
        fund_data['recommendation'] = get_recommendation(overall_score)
    
    return fund_data

def get_technical_analysis(symbol):
    """Get comprehensive technical analysis for a stock"""
    try:
        # Add .NS suffix for NSE stocks if not present
        if not symbol.endswith('.NS'):
            ticker_symbol = f"{symbol}.NS"
        else:
            ticker_symbol = symbol
            
        # Get OHLCV data
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1y", interval="1d")
        
        if hist.empty:
            print(f"   ⚠️  No OHLCV data available for {symbol}")
            return None
            
        # Calculate technical indicators
        indicators = calculate_indicators(hist)
        
        if not indicators:
            print(f"   ⚠️  Could not calculate technical indicators for {symbol}")
            return None
            
        # Compute technical score
        tech_score, tech_analysis = compute_technical_score(indicators)
        
        # Prepare technical data with consistent naming
        tech_data = {
            'technical_score': tech_score,
            'technical_analysis': tech_analysis,
            'rsi': indicators.get('rsi14', 0),
            'macd': indicators.get('macd', 0),
            'macd_signal': indicators.get('macd_signal', 0),
            'macd_histogram': indicators.get('macd_hist', 0),
            'sma_20': indicators.get('sma20', 0),
            'sma_50': indicators.get('sma50', 0),
            'sma_100': indicators.get('sma100', 0),
            'sma_200': indicators.get('sma200', 0),
            'ema_12': indicators.get('ema12', 0),
            'ema_26': indicators.get('ema26', 0),
            'stoch_k': indicators.get('stoch_k', 0),
            'stoch_d': indicators.get('stoch_d', 0),
            'bb_upper': indicators.get('bb_upper', 0),
            'bb_lower': indicators.get('bb_lower', 0),
            'volatility_tech': indicators.get('volatility', 0),
            'volume_trend': indicators.get('volume_trend', 'Unknown'),
            'trend_direction': indicators.get('trend', 'Sideways'),
            'support_levels': str(indicators.get('support_levels', [])),
            'resistance_levels': str(indicators.get('resistance_levels', [])),
            '52w_high_tech': indicators.get('52W_High', 0),
            '52w_low_tech': indicators.get('52W_Low', 0),
            'daily_change': indicators.get('Daily_Change', 0),
            'weekly_change': indicators.get('Weekly_Change', 0)
        }
        
        return tech_data
        
    except Exception as e:
        print(f"   ❌ Technical analysis failed for {symbol}: {e}")
        return None

def get_recommendation(score):
    """Get recommendation based on overall score"""
    if score >= 70:
        return "🟢 BUY"
    elif score >= 40:
        return "🟡 HOLD"
    else:
        return "🔴 SELL"

def display_comprehensive_analysis(data):
    """Display comprehensive analysis results"""
    if not data:
        print("❌ No data to display")
        return
        
    print(f"\n📈 FUNDAMENTAL ANALYSIS FOR {data.get('symbol', 'UNKNOWN')}:")
    print("-" * 50)
    
    # Key fundamental metrics
    fund_metrics = [
        ('Company Name', 'company_name'),
        ('Sector', 'sector'),
        ('Industry', 'industry'),
        ('Current Price', 'current_price'),
        ('Market Cap', 'market_cap'),
        ('PE Ratio', 'pe_ratio'),
        ('PB Ratio', 'pb_ratio'),
        ('ROE (%)', 'roe'),
        ('Debt/Equity', 'debt_to_equity'),
        ('Revenue Growth (%)', 'revenue_growth'),
        ('Earnings Growth (%)', 'earnings_growth'),
        ('Net Margin (%)', 'net_margin'),
        ('Dividend Yield (%)', 'dividend_yield'),
        ('Beta', 'beta'),
        ('52W High', '52_week_high'),
        ('52W Low', '52_week_low'),
        ('Book Value', 'book_value'),
        ('EPS', 'eps'),
        ('Fundamental Score', 'fundamental_score'),
        ('Fundamental Rating', 'fundamental_rating')
    ]
    
    for display_name, key in fund_metrics:
        value = data.get(key, 'N/A')
        if isinstance(value, (int, float)) and value != 0:
            if 'Price' in display_name or 'Market Cap' in display_name:
                print(f"   {display_name:<20}: ₹{value:,.2f}" if 'Price' in display_name else f"   {display_name:<20}: ₹{value:,.0f}")
            elif '%' in display_name:
                print(f"   {display_name:<20}: {value:.2f}%")
            else:
                print(f"   {display_name:<20}: {value}")
        elif value not in [0, 'N/A', None]:
            print(f"   {display_name:<20}: {value}")
    
    print(f"\n📈 TECHNICAL ANALYSIS FOR {data.get('symbol', 'UNKNOWN')}:")
    print("-" * 50)
    
    # Key technical metrics
    tech_metrics = [
        ('RSI (14)', 'rsi'),
        ('MACD', 'macd'),
        ('MACD Signal', 'macd_signal'),
        ('SMA 20', 'sma_20'),
        ('SMA 50', 'sma_50'),
        ('SMA 200', 'sma_200'),
        ('EMA 12', 'ema_12'),
        ('EMA 26', 'ema_26'),
        ('Stochastic %K', 'stoch_k'),
        ('Stochastic %D', 'stoch_d'),
        ('Trend Direction', 'trend_direction'),
        ('Volume Trend', 'volume_trend'),
        ('Daily Change (%)', 'daily_change'),
        ('Weekly Change (%)', 'weekly_change'),
        ('Technical Score', 'technical_score'),
        ('Technical Analysis', 'technical_analysis')
    ]
    
    for display_name, key in tech_metrics:
        value = data.get(key, 'N/A')
        if isinstance(value, (int, float)) and value != 0:
            if 'SMA' in display_name or 'EMA' in display_name:
                print(f"   {display_name:<20}: ₹{value:.2f}")
            elif '%' in display_name or 'Change' in display_name:
                print(f"   {display_name:<20}: {value:.2f}%")
            else:
                print(f"   {display_name:<20}: {value:.2f}")
        elif value not in [0, 'N/A', None]:
            print(f"   {display_name:<20}: {value}")
    
    # Overall analysis
    if 'overall_score' in data:
        print(f"\n🎯 COMBINED ANALYSIS FOR {data.get('symbol', 'UNKNOWN')}:")
        print("-" * 50)
        print(f"   Fundamental Score   : {data.get('fundamental_score', 0):.2f}/100")
        print(f"   Technical Score     : {data.get('technical_score', 0):.2f}/100")
        print(f"   ─────────────────────────────")
        print(f"   Overall Score       : {data.get('overall_score', 0):.2f}/100")
        print(f"   Recommendation      : {data.get('recommendation', 'N/A')}")

def test_comprehensive_analysis():
    """Test comprehensive analysis with RELIANCE"""
    print("🔧 TESTING COMPREHENSIVE ANALYSIS (FUNDAMENTAL + TECHNICAL)")
    print("=" * 80)
    
    # Analyze RELIANCE
    comprehensive_data = get_comprehensive_stock_analysis('RELIANCE')
    
    if comprehensive_data:
        # Display results
        display_comprehensive_analysis(comprehensive_data)
        
        # Generate Excel report
        print(f"\n📊 GENERATING COMPREHENSIVE EXCEL REPORT:")
        print("-" * 50)
        
        try:
            df = pd.DataFrame([comprehensive_data])
            excel_exporter = ExcelExporter()
            filename = excel_exporter.generate_daily_report(df)
            print(f"✅ Excel report generated: {filename}")
            
            # Summary
            total_fields = len(comprehensive_data)
            non_zero_fields = sum(1 for v in comprehensive_data.values() if pd.notna(v) and v != 0 and v != '')
            
            print(f"\n✅ COMPREHENSIVE ANALYSIS COMPLETE!")
            print(f"📊 Total data fields: {total_fields}")
            print(f"📈 Non-zero fields: {non_zero_fields}")
            print(f"🎯 Final Recommendation: {comprehensive_data.get('recommendation', 'N/A')}")
            print(f"📊 Overall Score: {comprehensive_data.get('overall_score', 0):.2f}/100")
            
            return True
            
        except Exception as e:
            print(f"❌ Excel generation failed: {e}")
            return False
    else:
        print("❌ Comprehensive analysis failed")
        return False

if __name__ == "__main__":
    success = test_comprehensive_analysis()
    
    if success:
        print("\n🎉 COMPREHENSIVE ANALYSIS TEST PASSED!")
        print("📊 Both fundamental and technical data are now included")
    else:
        print("\n❌ COMPREHENSIVE ANALYSIS TEST FAILED!")
        print("🔧 Check fundamental and technical data collection")
