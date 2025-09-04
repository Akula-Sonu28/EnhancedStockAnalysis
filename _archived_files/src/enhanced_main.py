"""
Enhanced Main Orchestration Script for Autonomous Stock Analyzer
"""
import pandas as pd
import logging
from datetime import datetime
import os
import sys

# Import all modules
from enhanced_nse_scraper import NSEDataScraper
from enhanced_news_analyzer import NewsAnalyzer
from fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from excel_exporter import ExcelReportGenerator
from database import StockDatabase
from scheduler import StockAnalysisScheduler

def setup_logging():
    """Setup comprehensive logging"""
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Setup logging
    log_filename = f"logs/analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    return log_filename

def run_full_analysis():
    """Run comprehensive stock analysis with all features"""
    print("🚀 Starting Enhanced NSE Stock Analysis...")
    log_file = setup_logging()
    
    try:
        # Initialize components
        logging.info("Initializing analysis components...")
        nse_scraper = NSEDataScraper()
        news_analyzer = NewsAnalyzer()
        excel_generator = ExcelReportGenerator()
        db = StockDatabase()
        
        print("✓ Components initialized")
        
        # Step 1: Get stock data
        print("\n📊 Fetching stock data...")
        stocks = nse_scraper.get_top_stocks_list()[:50]  # Top 50 for demo
        print(f"✓ Found {len(stocks)} stocks to analyze")
        logging.info(f"Found {len(stocks)} stocks to analyze")
        
        # Step 2: Analyze stocks
        print("\n🔍 Analyzing stocks...")
        analysis_results = []
        technical_data = []
        fundamental_data = []
        sentiment_data = []
        
        for idx, stock in enumerate(stocks, 1):
            symbol = stock['symbol']
            print(f"\nAnalyzing {symbol} ({idx}/{len(stocks)})...")
            
            try:
                # Get detailed stock info
                stock_info = nse_scraper.get_stock_info(symbol)
                
                # Fundamental Analysis
                print(f"  📈 Fundamental analysis...")
                fund_metrics = extract_fundamental_metrics(stock_info)
                fund_score = compute_fundamental_score(fund_metrics)
                fund_score_value = fund_score.get('score', 0) if isinstance(fund_score, dict) else 0
                
                # Technical Analysis
                print(f"  📉 Technical analysis...")
                ohlcv = get_ohlcv(symbol)
                tech_score = 0
                tech_indicators = {}
                
                if ohlcv is not None:
                    tech_indicators = calculate_indicators(ohlcv)
                    if tech_indicators:
                        tech_score, _ = compute_technical_score(tech_indicators)
                
                # Sentiment Analysis
                print(f"  📰 Sentiment analysis...")
                sentiment_result = news_analyzer.analyze_stock_sentiment(symbol)
                sentiment_score = sentiment_result['sentiment_score']
                
                # Calculate Overall Score
                # Convert sentiment score from -1 to 1 range to 0 to 100 range
                sentiment_score_normalized = (sentiment_score + 1) * 50
                overall_score = round((fund_score_value + tech_score + sentiment_score_normalized) / 3, 2)
                
                # Determine recommendation
                if overall_score > 70:
                    recommendation = 'BUY'
                elif overall_score >= 40:
                    recommendation = 'HOLD'
                else:
                    recommendation = 'SELL'
                
                # Combine results
                result = {
                    'symbol': symbol,
                    'companyName': stock.get('companyName', symbol),
                    'FundamentalScore': fund_score_value,
                    'TechnicalScore': tech_score,
                    'SentimentScore': sentiment_score_normalized,
                    'OverallScore': overall_score,
                    'Recommendation': recommendation,
                    'FundamentalRating': fund_score.get('rating', 'N/A') if isinstance(fund_score, dict) else 'N/A',
                    'SentimentLabel': sentiment_result['sentiment_label'],
                    'NewsCount': sentiment_result['news_count']
                }
                
                # Add detailed metrics
                if fund_metrics:
                    result.update(fund_metrics)
                if tech_indicators:
                    result.update(tech_indicators)
                
                analysis_results.append(result)
                
                # Separate data for different sheets
                if fund_metrics:
                    fund_data = {**result, **fund_metrics}
                    fundamental_data.append(fund_data)
                
                if tech_indicators:
                    tech_data = {**result, **tech_indicators}
                    technical_data.append(tech_data)
                
                # Add sentiment data
                if sentiment_result['headlines']:
                    for headline in sentiment_result['headlines']:
                        sentiment_data.append({
                            'symbol': symbol,
                            'headline': headline['headline'],
                            'source': headline['source'],
                            'sentiment_score': headline['sentiment_score'],
                            'sentiment_label': headline['sentiment_label'],
                            'SentimentScore': sentiment_score_normalized
                        })
                
                print(f"  ✓ Overall Score: {overall_score} ({recommendation})")
                logging.info(f"Completed analysis for {symbol}: {overall_score} ({recommendation})")
                
            except Exception as e:
                logging.error(f"Error analyzing {symbol}: {str(e)}")
                print(f"  ✗ Error analyzing {symbol}: {str(e)}")
                
                # Add basic entry even if analysis fails
                analysis_results.append({
                    'symbol': symbol,
                    'companyName': stock.get('companyName', symbol),
                    'FundamentalScore': 0,
                    'TechnicalScore': 0,
                    'SentimentScore': 50,  # Neutral
                    'OverallScore': 16.67,  # Average of 0, 0, 50
                    'Recommendation': 'HOLD',
                    'FundamentalRating': 'Error',
                    'SentimentLabel': 'Error',
                    'NewsCount': 0
                })
        
        # Step 3: Generate Reports
        if analysis_results:
            print(f"\n📋 Generating reports...")
            
            # Create DataFrames
            df_summary = pd.DataFrame(analysis_results)
            df_technical = pd.DataFrame(technical_data) if technical_data else None
            df_fundamental = pd.DataFrame(fundamental_data) if fundamental_data else None
            df_sentiment = pd.DataFrame(sentiment_data) if sentiment_data else None
            
            # Sort by overall score
            df_summary = df_summary.sort_values('OverallScore', ascending=False)
            
            # Store in database
            try:
                # Store analysis scores
                scores_data = []
                for _, row in df_summary.iterrows():
                    scores_data.append({
                        'symbol': row['symbol'],
                        'date': datetime.now().date(),
                        'fundamental_score': row['FundamentalScore'],
                        'technical_score': row['TechnicalScore'],
                        'sentiment_score': row['SentimentScore'],
                        'overall_score': row['OverallScore'],
                        'recommendation': row['Recommendation']
                    })
                
                df_scores = pd.DataFrame(scores_data)
                db.insert_scores(df_scores)
                print("✓ Data stored in database")
                
            except Exception as e:
                logging.error(f"Error storing data in database: {str(e)}")
                print(f"✗ Database storage failed: {str(e)}")
            
            # Generate Excel Report
            try:
                report_path = excel_generator.generate_daily_report(
                    summary_data=df_summary,
                    technical_data=df_technical,
                    fundamental_data=df_fundamental,
                    sentiment_data=df_sentiment
                )
                print(f"✓ Excel report generated: {report_path}")
                logging.info(f"Excel report generated: {report_path}")
                
            except Exception as e:
                logging.error(f"Error generating Excel report: {str(e)}")
                print(f"✗ Excel report generation failed: {str(e)}")
            
            # Display Top 10 Results
            print(f"\n🏆 Top 10 Stocks by Overall Score:")
            print("=" * 80)
            top_10 = df_summary.head(10)
            
            for idx, (_, row) in enumerate(top_10.iterrows(), 1):
                symbol = row['symbol']
                score = row['OverallScore']
                recommendation = row['Recommendation']
                fund_score = row['FundamentalScore']
                tech_score = row['TechnicalScore']
                sent_score = row['SentimentScore']
                
                print(f"{idx:2d}. {symbol:12s} | Score: {score:5.1f} | {recommendation:4s} | "
                      f"F:{fund_score:5.1f} T:{tech_score:5.1f} S:{sent_score:5.1f}")
            
            # Display Summary Statistics
            print(f"\n📊 Analysis Summary:")
            print(f"   Total Stocks Analyzed: {len(df_summary)}")
            print(f"   BUY Recommendations:   {len(df_summary[df_summary['Recommendation'] == 'BUY'])}")
            print(f"   HOLD Recommendations:  {len(df_summary[df_summary['Recommendation'] == 'HOLD'])}")
            print(f"   SELL Recommendations:  {len(df_summary[df_summary['Recommendation'] == 'SELL'])}")
            print(f"   Average Overall Score: {df_summary['OverallScore'].mean():.2f}")
            
            # Legacy Excel export (for compatibility)
            try:
                from data_exporter import export_data
                export_data(df_summary)
                print("✓ Legacy Excel export completed")
            except Exception as e:
                logging.warning(f"Legacy Excel export failed: {str(e)}")
            
            # JSON export
            try:
                from json_export import export_to_json
                json_file = export_to_json(analysis_results)
                print(f"✓ JSON export completed: {json_file}")
                logging.info(f"JSON export completed: {json_file}")
            except Exception as e:
                logging.error(f"JSON export failed: {str(e)}")
                print(f"✗ JSON export failed: {str(e)}")
            
        else:
            logging.error("No analysis results generated")
            print("✗ No analysis results generated")
        
        print(f"\n✅ Analysis completed successfully!")
        print(f"📄 Detailed logs saved to: {log_file}")
        
    except Exception as e:
        logging.error(f"Analysis failed: {str(e)}")
        print(f"❌ Analysis failed: {str(e)}")
    
    finally:
        logging.info("Analysis session completed")

def run_scheduler():
    """Run the automated scheduler"""
    print("🕒 Starting Automated Stock Analysis Scheduler...")
    
    scheduler = StockAnalysisScheduler()
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n⏹️  Scheduler stopped by user")
        scheduler.stop()
    except Exception as e:
        print(f"❌ Scheduler error: {str(e)}")
        scheduler.stop()

def main():
    """Main entry point"""
    print("🎯 Enhanced Stock Analysis System")
    print("=" * 50)
    print("Choose an option:")
    print("1. Run Full Analysis (One-time)")
    print("2. Start Automated Scheduler")
    print("3. Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-3): ").strip()
            
            if choice == '1':
                run_full_analysis()
                break
            elif choice == '2':
                run_scheduler()
                break
            elif choice == '3':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    # For backward compatibility, run full analysis if no arguments
    if len(sys.argv) == 1:
        run_full_analysis()
    else:
        main()
