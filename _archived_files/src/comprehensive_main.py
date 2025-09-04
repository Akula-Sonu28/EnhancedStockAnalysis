"""
Improved Main Script with Comprehensive Data Collection
"""
import pandas as pd
import logging
from datetime import datetime
import os
import sys

# Import all modules
from enhanced_nse_scraper import NSEDataScraper
from enhanced_news_analyzer import NewsAnalyzer
from enhanced_fundamental_analyzer import get_comprehensive_stock_data
from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from excel_exporter import ExcelReportGenerator
from database import StockDatabase

def setup_logging():
    """Setup comprehensive logging"""
    os.makedirs('logs', exist_ok=True)
    log_filename = f"logs/comprehensive_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    return log_filename

def run_comprehensive_analysis(num_stocks=20):
    """Run comprehensive analysis with complete data collection"""
    print("🚀 Starting Comprehensive Stock Analysis...")
    log_file = setup_logging()
    
    try:
        # Initialize components
        logging.info("Initializing analysis components...")
        nse_scraper = NSEDataScraper()
        news_analyzer = NewsAnalyzer()
        excel_generator = ExcelReportGenerator()
        db = StockDatabase()
        
        print("✅ Components initialized")
        
        # Get stock list
        print(f"\n📊 Fetching top {num_stocks} stocks...")
        stocks = nse_scraper.get_top_stocks_list()[:num_stocks]
        print(f"✅ Found {len(stocks)} stocks to analyze")
        
        # Analyze each stock comprehensively
        print(f"\n🔍 Performing comprehensive analysis...")
        results = []
        
        for idx, stock in enumerate(stocks, 1):
            symbol = stock['symbol']
            print(f"\n{'='*60}")
            print(f"Analyzing {symbol} ({idx}/{len(stocks)})...")
            print(f"{'='*60}")
            
            try:
                # 1. Get comprehensive fundamental data
                print("📊 Collecting comprehensive fundamental data...")
                fund_data = get_comprehensive_stock_data(symbol)
                print(f"✅ Fundamental data collected: {len(fund_data)} metrics")
                
                # 2. Technical Analysis
                print("📈 Performing technical analysis...")
                ohlcv = get_ohlcv(symbol)
                tech_score = 0
                tech_indicators = {}
                
                if ohlcv is not None and len(ohlcv) > 0:
                    tech_indicators = calculate_indicators(ohlcv)
                    if tech_indicators:
                        tech_score, tech_analysis = compute_technical_score(tech_indicators)
                        print(f"✅ Technical analysis complete: Score {tech_score}")
                    else:
                        tech_analysis = "No technical indicators calculated"
                        print("⚠️ Technical indicators calculation failed")
                else:
                    tech_analysis = "No price history available"
                    print("⚠️ No price history available")
                
                # 3. Sentiment Analysis
                print("📰 Analyzing news sentiment...")
                sentiment_result = news_analyzer.analyze_stock_sentiment(symbol)
                sentiment_score = sentiment_result['sentiment_score']
                sentiment_score_normalized = (sentiment_score + 1) * 50  # Convert to 0-100
                print(f"✅ Sentiment analysis complete: {sentiment_result['sentiment_label']} ({sentiment_score_normalized:.1f})")
                
                # 4. Combine all data
                combined_data = {
                    **fund_data,  # All fundamental data
                    **tech_indicators,  # All technical indicators
                    'TechnicalScore': tech_score,
                    'TechnicalAnalysis': tech_analysis,
                    'SentimentScore': sentiment_score_normalized,
                    'SentimentLabel': sentiment_result['sentiment_label'],
                    'NewsCount': sentiment_result['news_count'],
                    'RawSentimentScore': sentiment_score
                }
                
                # 5. Calculate overall score
                fund_score = combined_data.get('fundamental_score', 50)
                overall_score = round((fund_score + tech_score + sentiment_score_normalized) / 3, 2)
                
                # Determine recommendation
                if overall_score > 70:
                    recommendation = 'BUY'
                elif overall_score >= 40:
                    recommendation = 'HOLD'
                else:
                    recommendation = 'SELL'
                
                combined_data.update({
                    'OverallScore': overall_score,
                    'Recommendation': recommendation
                })
                
                results.append(combined_data)
                
                # Display summary
                print(f"\n📊 ANALYSIS SUMMARY FOR {symbol}:")
                print(f"   Company: {combined_data.get('company_name', symbol)}")
                print(f"   Sector: {combined_data.get('sector', 'Unknown')}")
                print(f"   Current Price: ₹{combined_data.get('current_price', 0):,.2f}")
                print(f"   Market Cap: ₹{combined_data.get('market_cap', 0):,.0f}")
                print(f"   PE Ratio: {combined_data.get('pe_ratio', 0):.2f}")
                print(f"   ROE: {combined_data.get('roe', 0):.2f}%")
                print(f"   Fundamental Score: {fund_score:.1f}")
                print(f"   Technical Score: {tech_score:.1f}")
                print(f"   Sentiment Score: {sentiment_score_normalized:.1f}")
                print(f"   Overall Score: {overall_score:.1f}")
                print(f"   Recommendation: {recommendation}")
                
                logging.info(f"Completed comprehensive analysis for {symbol}: {overall_score} ({recommendation})")
                
            except Exception as e:
                logging.error(f"Error analyzing {symbol}: {str(e)}")
                print(f"❌ Error analyzing {symbol}: {str(e)}")
                
                # Add minimal data to avoid gaps
                results.append({
                    'symbol': symbol,
                    'company_name': symbol,
                    'sector': 'Unknown',
                    'fundamental_score': 0,
                    'TechnicalScore': 0,
                    'SentimentScore': 50,
                    'OverallScore': 16.67,
                    'Recommendation': 'HOLD',
                    'current_price': 0,
                    'market_cap': 0,
                    'pe_ratio': 0,
                    'roe': 0
                })
        
        # Generate comprehensive reports
        if results:
            print(f"\n📋 Generating comprehensive reports...")
            
            # Create DataFrame
            df = pd.DataFrame(results)
            df = df.sort_values('OverallScore', ascending=False)
            
            # Store in database
            try:
                scores_data = []
                for _, row in df.iterrows():
                    scores_data.append({
                        'symbol': row['symbol'],
                        'date': datetime.now().date(),
                        'fundamental_score': row.get('fundamental_score', 0),
                        'technical_score': row.get('TechnicalScore', 0),
                        'sentiment_score': row.get('SentimentScore', 50),
                        'overall_score': row.get('OverallScore', 0),
                        'recommendation': row.get('Recommendation', 'HOLD')
                    })
                
                df_scores = pd.DataFrame(scores_data)
                db.insert_scores(df_scores)
                print("✅ Data stored in database")
                
            except Exception as e:
                logging.error(f"Database storage error: {str(e)}")
                print(f"⚠️ Database storage failed: {str(e)}")
            
            # Generate Excel report
            try:
                report_path = excel_generator.generate_daily_report(
                    summary_data=df
                )
                print(f"✅ Comprehensive Excel report generated: {report_path}")
                
            except Exception as e:
                logging.error(f"Excel generation error: {str(e)}")
                print(f"⚠️ Excel generation failed: {str(e)}")
            
            # Display top performers
            print(f"\n🏆 TOP 10 PERFORMERS:")
            print("="*100)
            print(f"{'Rank':<4} {'Symbol':<12} {'Company':<25} {'Score':<6} {'Rec':<4} {'Sector':<15} {'Price':<10}")
            print("="*100)
            
            top_10 = df.head(10)
            for idx, (_, row) in enumerate(top_10.iterrows(), 1):
                symbol = row['symbol']
                company = str(row.get('company_name', symbol))[:23]
                score = row.get('OverallScore', 0)
                rec = row.get('Recommendation', 'HOLD')
                sector = str(row.get('sector', 'Unknown'))[:13]
                price = row.get('current_price', 0)
                
                print(f"{idx:<4} {symbol:<12} {company:<25} {score:<6.1f} {rec:<4} {sector:<15} ₹{price:<9.2f}")
            
            # Summary statistics
            print(f"\n📊 ANALYSIS SUMMARY:")
            print(f"   Total Stocks Analyzed: {len(df)}")
            print(f"   BUY Recommendations:   {len(df[df['Recommendation'] == 'BUY'])}")
            print(f"   HOLD Recommendations:  {len(df[df['Recommendation'] == 'HOLD'])}")
            print(f"   SELL Recommendations:  {len(df[df['Recommendation'] == 'SELL'])}")
            print(f"   Average Overall Score: {df['OverallScore'].mean():.2f}")
            print(f"   Highest Score:         {df['OverallScore'].max():.2f}")
            print(f"   Lowest Score:          {df['OverallScore'].min():.2f}")
            
            print(f"\n✅ Comprehensive analysis completed successfully!")
            print(f"📄 Detailed logs: {log_file}")
            print(f"📊 Excel report: reports/Stock_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx")
            print(f"🗄️ Database: data/stock_analysis.db")
            
        else:
            print("❌ No analysis results generated")
            
    except Exception as e:
        logging.error(f"Analysis failed: {str(e)}")
        print(f"❌ Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Create required directories
    os.makedirs('data', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Run comprehensive analysis
    num_stocks = 20  # Adjust number of stocks as needed
    run_comprehensive_analysis(num_stocks)
