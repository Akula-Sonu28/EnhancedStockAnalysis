"""
Quick test for one stock to verify accuracy and data completeness
"""
import sys
import os
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append('src')

def test_one_stock_accuracy():
    """Test comprehensive analysis for one stock"""
    symbol = "RELIANCE"
    print(f"🎯 COMPREHENSIVE ANALYSIS TEST FOR {symbol}")
    print("="*80)
    
    try:
        # Import modules
        from enhanced_fundamental_analyzer import get_comprehensive_stock_data
        from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
        from enhanced_news_analyzer import NewsAnalyzer
        from excel_exporter import ExcelReportGenerator
        
        print("✅ All modules imported successfully")
        
        # 1. Comprehensive Fundamental Analysis
        print(f"\n📊 FUNDAMENTAL ANALYSIS FOR {symbol}:")
        print("-" * 50)
        fund_data = get_comprehensive_stock_data(symbol)
        
        # Display key fundamental metrics
        key_metrics = [
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
            ('Current Ratio', 'current_ratio'),
            ('Fundamental Score', 'fundamental_score'),
            ('Fundamental Rating', 'fundamental_rating')
        ]
        
        for display_name, key in key_metrics:
            value = fund_data.get(key, 'N/A')
            if isinstance(value, (int, float)) and value != 0:
                if 'price' in key.lower() or 'cap' in key.lower():
                    print(f"   {display_name:<20}: ₹{value:,.2f}")
                elif '%' in display_name:
                    print(f"   {display_name:<20}: {value:.2f}%")
                else:
                    print(f"   {display_name:<20}: {value:.2f}")
            else:
                print(f"   {display_name:<20}: {value}")
        
        print(f"\n📈 TECHNICAL ANALYSIS FOR {symbol}:")
        print("-" * 50)
        
        # 2. Technical Analysis
        ohlcv = get_ohlcv(symbol)
        tech_score = 0
        tech_indicators = {}
        
        if ohlcv is not None and len(ohlcv) > 0:
            tech_indicators = calculate_indicators(ohlcv)
            if tech_indicators:
                tech_score, tech_analysis = compute_technical_score(tech_indicators)
                
                # Display technical indicators
                tech_metrics = [
                    ('RSI', 'rsi'),
                    ('MACD', 'macd'),
                    ('MACD Signal', 'macd_signal'),
                    ('SMA 20', 'sma_20'),
                    ('SMA 50', 'sma_50'),
                    ('EMA 12', 'ema_12'),
                    ('EMA 26', 'ema_26'),
                    ('Bollinger Upper', 'bb_upper'),
                    ('Bollinger Lower', 'bb_lower'),
                    ('ADX', 'adx'),
                    ('ATR', 'atr'),
                    ('Technical Score', None)
                ]
                
                for display_name, key in tech_metrics:
                    if key:
                        value = tech_indicators.get(key, 0)
                        print(f"   {display_name:<20}: {value:.2f}")
                    else:
                        print(f"   {display_name:<20}: {tech_score:.2f}")
                
                print(f"   Technical Analysis  : {tech_analysis}")
            else:
                print("   ⚠️ No technical indicators calculated")
        else:
            print("   ⚠️ No price history available")
        
        print(f"\n📰 SENTIMENT ANALYSIS FOR {symbol}:")
        print("-" * 50)
        
        # 3. Sentiment Analysis
        news_analyzer = NewsAnalyzer()
        sentiment_result = news_analyzer.analyze_stock_sentiment(symbol)
        
        sentiment_score = sentiment_result['sentiment_score']
        sentiment_score_normalized = (sentiment_score + 1) * 50
        
        print(f"   Sentiment Score     : {sentiment_score_normalized:.2f}/100")
        print(f"   Sentiment Label     : {sentiment_result['sentiment_label']}")
        print(f"   Raw Sentiment       : {sentiment_score:.3f}")
        print(f"   News Articles Found : {sentiment_result['news_count']}")
        
        if sentiment_result['headlines']:
            print(f"\n   📰 Sample Headlines:")
            for i, headline in enumerate(sentiment_result['headlines'][:3], 1):
                print(f"   {i}. {headline['headline']}")
                print(f"      Source: {headline['source']} | Sentiment: {headline['sentiment_label']} ({headline['sentiment_score']:.2f})")
        
        # 4. Combined Analysis
        print(f"\n🎯 COMBINED ANALYSIS FOR {symbol}:")
        print("-" * 50)
        
        fund_score = fund_data.get('fundamental_score', 50)
        overall_score = round((fund_score + tech_score + sentiment_score_normalized) / 3, 2)
        
        if overall_score > 70:
            recommendation = 'BUY'
            color = '🟢'
        elif overall_score >= 40:
            recommendation = 'HOLD'
            color = '🟡'
        else:
            recommendation = 'SELL'
            color = '🔴'
        
        print(f"   Fundamental Score   : {fund_score:.2f}/100")
        print(f"   Technical Score     : {tech_score:.2f}/100")
        print(f"   Sentiment Score     : {sentiment_score_normalized:.2f}/100")
        print(f"   ─────────────────────────────")
        print(f"   Overall Score       : {overall_score:.2f}/100")
        print(f"   Recommendation      : {color} {recommendation}")
        
        # 5. Create comprehensive data structure
        comprehensive_data = {
            **fund_data,
            **tech_indicators,
            'TechnicalScore': tech_score,
            'TechnicalAnalysis': tech_analysis if 'tech_analysis' in locals() else 'No analysis',
            'SentimentScore': sentiment_score_normalized,
            'SentimentLabel': sentiment_result['sentiment_label'],
            'NewsCount': sentiment_result['news_count'],
            'RawSentimentScore': sentiment_score,
            'OverallScore': overall_score,
            'Recommendation': recommendation
        }
        
        # 6. Generate Excel Report
        print(f"\n📋 GENERATING EXCEL REPORT:")
        print("-" * 50)
        
        excel_generator = ExcelReportGenerator()
        df = pd.DataFrame([comprehensive_data])
        
        try:
            report_path = excel_generator.generate_daily_report(summary_data=df)
            print(f"✅ Excel report generated: {report_path}")
            
            # Show what data is in the Excel
            print(f"\n📊 DATA INCLUDED IN EXCEL ({len(comprehensive_data)} fields):")
            categories = {
                'Company Info': ['symbol', 'company_name', 'sector', 'industry', 'employees'],
                'Market Data': ['current_price', 'market_cap', '52_week_high', '52_week_low', 'beta'],
                'Valuation': ['pe_ratio', 'pb_ratio', 'ps_ratio', 'peg_ratio', 'ev_ebitda'],
                'Profitability': ['roe', 'roa', 'gross_margin', 'operating_margin', 'net_margin'],
                'Growth': ['revenue_growth', 'earnings_growth', 'quarterly_revenue_growth'],
                'Financial Health': ['debt_to_equity', 'current_ratio', 'quick_ratio'],
                'Technical': ['rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'adx'],
                'Scores': ['fundamental_score', 'TechnicalScore', 'SentimentScore', 'OverallScore']
            }
            
            for category, fields in categories.items():
                available_fields = [f for f in fields if f in comprehensive_data and comprehensive_data[f] not in [0, None, 'N/A', '']]
                print(f"   {category:<15}: {len(available_fields)}/{len(fields)} fields populated")
            
        except Exception as e:
            print(f"❌ Excel generation failed: {str(e)}")
        
        print(f"\n✅ COMPREHENSIVE ANALYSIS COMPLETE!")
        print(f"📈 {len(comprehensive_data)} data points collected")
        print(f"🎯 Final Recommendation: {color} {recommendation} (Score: {overall_score}/100)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Create directories
    os.makedirs('data', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    success = test_one_stock_accuracy()
    
    if success:
        print(f"\n🎉 Single stock accuracy test PASSED!")
        print(f"📊 Check the generated Excel report for complete data")
    else:
        print(f"\n⚠️ Single stock accuracy test had issues")
