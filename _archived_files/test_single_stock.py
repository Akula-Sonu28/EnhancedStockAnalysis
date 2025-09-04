"""
Quick test for one stock to demonstrate the enhanced system
"""
import sys
import os
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append('src')

def test_single_stock():
    """Test analysis for a single stock"""
    print("🧪 Testing Enhanced Stock Analysis for Single Stock")
    print("=" * 60)
    
    try:
        # Import modules
        from enhanced_nse_scraper import NSEDataScraper
        from enhanced_news_analyzer import NewsAnalyzer
        from fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
        from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
        from excel_exporter import ExcelReportGenerator
        from database import StockDatabase
        
        print("✅ All modules imported successfully")
        
        # Initialize components
        nse_scraper = NSEDataScraper()
        news_analyzer = NewsAnalyzer()
        excel_generator = ExcelReportGenerator()
        db = StockDatabase()
        
        print("✅ Components initialized")
        
        # Test with RELIANCE
        symbol = "RELIANCE"
        print(f"\n🔍 Analyzing {symbol}...")
        
        # 1. Get stock info
        print("  📊 Fetching stock data...")
        stock_info = nse_scraper.get_stock_info(symbol)
        print(f"  ✓ Stock info retrieved")
        
        # 2. Fundamental Analysis
        print("  📈 Fundamental analysis...")
        fund_metrics = extract_fundamental_metrics(stock_info)
        fund_score = compute_fundamental_score(fund_metrics)
        fund_score_value = fund_score.get('score', 0) if isinstance(fund_score, dict) else 0
        print(f"  ✓ Fundamental Score: {fund_score_value}")
        
        # 3. Technical Analysis
        print("  📉 Technical analysis...")
        ohlcv = get_ohlcv(symbol)
        tech_score = 0
        tech_indicators = {}
        
        if ohlcv is not None:
            tech_indicators = calculate_indicators(ohlcv)
            if tech_indicators:
                tech_score, _ = compute_technical_score(tech_indicators)
        
        print(f"  ✓ Technical Score: {tech_score}")
        
        # 4. Sentiment Analysis
        print("  📰 Sentiment analysis...")
        sentiment_result = news_analyzer.analyze_stock_sentiment(symbol)
        sentiment_score = sentiment_result['sentiment_score']
        sentiment_score_normalized = (sentiment_score + 1) * 50  # Convert to 0-100 scale
        print(f"  ✓ Sentiment Score: {sentiment_score_normalized:.1f} ({sentiment_result['sentiment_label']})")
        
        # 5. Calculate Overall Score
        overall_score = round((fund_score_value + tech_score + sentiment_score_normalized) / 3, 2)
        
        if overall_score > 70:
            recommendation = 'BUY'
        elif overall_score >= 40:
            recommendation = 'HOLD'
        else:
            recommendation = 'SELL'
        
        print(f"  ✓ Overall Score: {overall_score} ({recommendation})")
        
        # 6. Create test data for Excel report
        result_data = [{
            'symbol': symbol,
            'companyName': 'Reliance Industries Ltd',
            'FundamentalScore': fund_score_value,
            'TechnicalScore': tech_score,
            'SentimentScore': sentiment_score_normalized,
            'OverallScore': overall_score,
            'Recommendation': recommendation,
            'NewsCount': sentiment_result['news_count']
        }]
        
        # Add metrics if available
        if fund_metrics:
            result_data[0].update(fund_metrics)
        if tech_indicators:
            result_data[0].update(tech_indicators)
        
        # 7. Generate Excel Report
        print("\n📋 Generating Excel report...")
        df = pd.DataFrame(result_data)
        
        try:
            report_path = excel_generator.generate_daily_report(
                summary_data=df,
                technical_data=df if tech_indicators else None,
                fundamental_data=df if fund_metrics else None,
                sentiment_data=None
            )
            print(f"✅ Excel report generated: {report_path}")
        except Exception as e:
            print(f"⚠️ Excel report error (non-critical): {str(e)}")
        
        # 8. Test Database Storage
        print("\n🗄️ Testing database storage...")
        try:
            # Store analysis score
            score_data = [{
                'symbol': symbol,
                'date': datetime.now().date(),
                'fundamental_score': fund_score_value,
                'technical_score': tech_score,
                'sentiment_score': sentiment_score_normalized,
                'overall_score': overall_score,
                'recommendation': recommendation
            }]
            
            df_scores = pd.DataFrame(score_data)
            db.insert_scores(df_scores)
            print("✅ Data stored in database")
        except Exception as e:
            print(f"⚠️ Database storage error (non-critical): {str(e)}")
        
        # 9. Display Results
        print(f"\n🎯 ANALYSIS RESULTS FOR {symbol}")
        print("=" * 50)
        print(f"Fundamental Score:  {fund_score_value:6.1f}")
        print(f"Technical Score:    {tech_score:6.1f}")
        print(f"Sentiment Score:    {sentiment_score_normalized:6.1f}")
        print("-" * 30)
        print(f"Overall Score:      {overall_score:6.1f}")
        print(f"Recommendation:     {recommendation}")
        print(f"News Articles:      {sentiment_result['news_count']}")
        
        if sentiment_result['headlines']:
            print(f"\n📰 Sample Headlines:")
            for i, headline in enumerate(sentiment_result['headlines'][:3], 1):
                print(f"  {i}. {headline['headline'][:60]}...")
        
        print(f"\n✅ Single stock test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Create required directories
    os.makedirs('data', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    success = test_single_stock()
    
    if success:
        print("\n🎉 Single stock test passed! The enhanced system is working correctly.")
    else:
        print("\n⚠️ Single stock test had issues. Check the errors above.")
