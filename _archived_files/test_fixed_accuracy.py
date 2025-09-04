"""
Fixed accuracy test with proper column handling
"""
import sys
import os
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append('src')

def test_fixed_accuracy():
    """Test with fixed column names"""
    symbol = "RELIANCE"
    print(f"🎯 FIXED ACCURACY TEST FOR {symbol}")
    print("="*80)
    
    try:
        from enhanced_fundamental_analyzer import get_comprehensive_stock_data
        from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
        from enhanced_news_analyzer import NewsAnalyzer
        from excel_exporter import ExcelReportGenerator
        
        # Get all data
        fund_data = get_comprehensive_stock_data(symbol)
        
        ohlcv = get_ohlcv(symbol)
        tech_score = 0
        tech_indicators = {}
        
        if ohlcv is not None and len(ohlcv) > 0:
            tech_indicators = calculate_indicators(ohlcv)
            if tech_indicators:
                tech_score, tech_analysis = compute_technical_score(tech_indicators)
        
        news_analyzer = NewsAnalyzer()
        sentiment_result = news_analyzer.analyze_stock_sentiment(symbol)
        sentiment_score = sentiment_result['sentiment_score']
        sentiment_score_normalized = (sentiment_score + 1) * 50
        
        # Create comprehensive data with consistent column names
        comprehensive_data = {
            **fund_data,
            **tech_indicators,
            'TechnicalScore': tech_score,
            'SentimentScore': sentiment_score_normalized,
            'SentimentLabel': sentiment_result['sentiment_label'],
            'NewsCount': sentiment_result['news_count'],
            'OverallScore': round((fund_data.get('fundamental_score', 50) + tech_score + sentiment_score_normalized) / 3, 2),
            'Recommendation': 'BUY' if round((fund_data.get('fundamental_score', 50) + tech_score + sentiment_score_normalized) / 3, 2) > 70 else 'HOLD' if round((fund_data.get('fundamental_score', 50) + tech_score + sentiment_score_normalized) / 3, 2) >= 40 else 'SELL'
        }
        
        # Create DataFrame
        df = pd.DataFrame([comprehensive_data])
        
        print(f"📊 DATA SUMMARY:")
        print(f"   Total Fields: {len(comprehensive_data)}")
        print(f"   Non-zero Fields: {sum(1 for v in comprehensive_data.values() if v not in [0, None, '', 'N/A'])}")
        
        # Show key metrics
        print(f"\n📈 KEY METRICS:")
        print(f"   Current Price: ₹{comprehensive_data.get('current_price', 0):,.2f}")
        print(f"   Market Cap: ₹{comprehensive_data.get('market_cap', 0):,.0f}")
        print(f"   PE Ratio: {comprehensive_data.get('pe_ratio', 0):.2f}")
        print(f"   ROE: {comprehensive_data.get('roe', 0):.2f}%")
        print(f"   Fundamental Score: {comprehensive_data.get('fundamental_score', 0):.1f}")
        print(f"   Technical Score: {comprehensive_data.get('TechnicalScore', 0):.1f}")
        print(f"   Sentiment Score: {comprehensive_data.get('SentimentScore', 0):.1f}")
        print(f"   Overall Score: {comprehensive_data.get('OverallScore', 0):.1f}")
        print(f"   Recommendation: {comprehensive_data.get('Recommendation', 'N/A')}")
        
        # Generate Excel
        print(f"\n📋 GENERATING EXCEL REPORT:")
        excel_generator = ExcelReportGenerator()
        
        try:
            report_path = excel_generator.generate_daily_report(summary_data=df)
            print(f"✅ Excel report generated successfully: {report_path}")
            
            # Verify file exists
            if os.path.exists(report_path):
                file_size = os.path.getsize(report_path)
                print(f"✅ File verified: {file_size:,} bytes")
            else:
                print(f"❌ File not found at: {report_path}")
            
        except Exception as e:
            print(f"❌ Excel generation error: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print(f"\n🎉 ACCURACY TEST COMPLETED!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    os.makedirs('data', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    test_fixed_accuracy()
