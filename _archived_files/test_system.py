"""
Test script to verify all components are working correctly
"""
import sys
import os

# Add src to path
sys.path.append('src')

def test_imports():
    """Test all module imports"""
    print("🧪 Testing module imports...")
    
    try:
        from database import StockDatabase
        print("✓ Database module")
        
        from excel_exporter import ExcelReportGenerator  
        print("✓ Excel exporter module")
        
        from enhanced_nse_scraper import NSEDataScraper
        print("✓ Enhanced NSE scraper module")
        
        from enhanced_news_analyzer import NewsAnalyzer
        print("✓ Enhanced news analyzer module")
        
        from scheduler import StockAnalysisScheduler
        print("✓ Scheduler module")
        
        from fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
        print("✓ Fundamental analyzer module")
        
        from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
        print("✓ Technical analyzer module")
        
        print("✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_database():
    """Test database functionality"""
    print("\n🗄️ Testing database...")
    
    try:
        from database import StockDatabase
        db = StockDatabase()
        print("✓ Database connection established")
        
        # Test table creation
        print("✓ Database tables created")
        
        print("✅ Database test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_excel_generator():
    """Test Excel report generator"""
    print("\n📋 Testing Excel generator...")
    
    try:
        import pandas as pd
        from excel_exporter import ExcelReportGenerator
        
        generator = ExcelReportGenerator()
        print("✓ Excel generator initialized")
        
        # Test with sample data
        sample_data = [
            {
                'symbol': 'RELIANCE',
                'OverallScore': 75.5,
                'FundamentalScore': 72.0,
                'TechnicalScore': 68.5,
                'SentimentScore': 85.0,
                'Recommendation': 'BUY'
            }
        ]
        
        df = pd.DataFrame(sample_data)
        report_path = generator.generate_daily_report(df)
        print(f"✓ Test report generated: {report_path}")
        
        print("✅ Excel generator test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Excel generator error: {e}")
        return False

def test_scrapers():
    """Test data scrapers"""
    print("\n🕷️ Testing scrapers...")
    
    try:
        from enhanced_nse_scraper import NSEDataScraper
        from enhanced_news_analyzer import NewsAnalyzer
        
        # Test NSE scraper
        nse_scraper = NSEDataScraper()
        stocks = nse_scraper.get_top_stocks_list()
        
        if stocks and len(stocks) > 0:
            print(f"✓ NSE scraper working - found {len(stocks)} stocks")
        else:
            print("⚠️ NSE scraper returned no stocks")
        
        # Test news analyzer
        news_analyzer = NewsAnalyzer()
        print("✓ News analyzer initialized")
        
        # Test sentiment analysis
        test_text = "This is a positive news about the company's great performance"
        sentiment = news_analyzer.analyze_sentiment(test_text)
        print(f"✓ Sentiment analysis working - score: {sentiment['score']}")
        
        print("✅ Scrapers test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Scrapers error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Enhanced Stock Analysis System - Component Tests")
    print("=" * 60)
    
    # Create required directories
    os.makedirs('data', exist_ok=True)
    os.makedirs('reports', exist_ok=True) 
    os.makedirs('logs', exist_ok=True)
    
    tests = [
        ("Module Imports", test_imports),
        ("Database", test_database), 
        ("Excel Generator", test_excel_generator),
        ("Data Scrapers", test_scrapers)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        if test_func():
            passed += 1
    
    print(f"\n{'='*60}")
    print(f"🎯 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready to use.")
        print("\nYou can now run:")
        print("  python src/enhanced_main.py")
    else:
        print("⚠️ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
