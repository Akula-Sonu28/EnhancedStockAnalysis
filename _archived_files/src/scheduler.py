"""
Scheduler for automated stock analysis
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from datetime import datetime, time
import os
import sys

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from enhanced_nse_scraper import NSEDataScraper
from enhanced_news_analyzer import NewsAnalyzer
from fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from excel_exporter import ExcelReportGenerator
from database import StockDatabase
import pandas as pd

class StockAnalysisScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.nse_scraper = NSEDataScraper()
        self.news_analyzer = NewsAnalyzer()
        self.excel_generator = ExcelReportGenerator()
        self.db = StockDatabase()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/scheduler.log'),
                logging.StreamHandler()
            ]
        )
        
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
    
    def setup_jobs(self):
        """Setup all scheduled jobs"""
        
        # Daily price scraper - runs at 6 PM on weekdays
        self.scheduler.add_job(
            func=self.daily_price_scraper,
            trigger="cron",
            day_of_week='mon-fri',
            hour=18,
            minute=0,
            id='daily_price_scraper'
        )
        
        # Daily news scraper - runs at 8 AM on weekdays
        self.scheduler.add_job(
            func=self.daily_news_scraper,
            trigger="cron", 
            day_of_week='mon-fri',
            hour=8,
            minute=0,
            id='daily_news_scraper'
        )
        
        # Full analysis and report generation - runs at 7 PM on weekdays
        self.scheduler.add_job(
            func=self.daily_analysis_and_report,
            trigger="cron",
            day_of_week='mon-fri', 
            hour=19,
            minute=0,
            id='daily_analysis_report'
        )
        
        # Weekly fundamental data update - runs on Sunday at 10 AM
        self.scheduler.add_job(
            func=self.weekly_fundamental_update,
            trigger="cron",
            day_of_week='sun',
            hour=10,
            minute=0,
            id='weekly_fundamental_update'
        )
        
        logging.info("All jobs scheduled successfully")
    
    def daily_price_scraper(self):
        """Download and store daily price data"""
        try:
            logging.info("Starting daily price scraper...")
            
            # Download today's Bhavcopy
            bhavcopy_data = self.nse_scraper.download_bhavcopy()
            
            if bhavcopy_data is not None:
                # Process and store in database
                price_data = []
                for _, row in bhavcopy_data.iterrows():
                    if row['SERIES'] == 'EQ':  # Only equity stocks
                        price_data.append({
                            'symbol': row['SYMBOL'],
                            'date': datetime.now().date(),
                            'open': row['OPEN'],
                            'high': row['HIGH'], 
                            'low': row['LOW'],
                            'close': row['CLOSE'],
                            'volume': row['TOTTRDQTY'],
                            'adj_close': row['CLOSE']  # Simplified
                        })
                
                if price_data:
                    df = pd.DataFrame(price_data)
                    self.db.insert_prices(df)
                    logging.info(f"Stored price data for {len(price_data)} stocks")
                else:
                    logging.warning("No price data to store")
            else:
                logging.error("Failed to download Bhavcopy data")
                
        except Exception as e:
            logging.error(f"Error in daily price scraper: {str(e)}")
    
    def daily_news_scraper(self):
        """Scrape and analyze daily news"""
        try:
            logging.info("Starting daily news scraper...")
            
            # Get list of top stocks
            stocks = self.nse_scraper.get_top_stocks_list()[:50]  # Top 50 stocks
            symbols = [stock['symbol'] for stock in stocks]
            
            # Analyze sentiment
            sentiment_results = self.news_analyzer.get_market_sentiment(symbols)
            
            # Store in database
            news_data = []
            for result in sentiment_results:
                if result['headlines']:
                    for headline_data in result['headlines']:
                        news_data.append({
                            'symbol': result['symbol'],
                            'date': datetime.now().date(),
                            'headline': headline_data['headline'],
                            'source': headline_data['source'],
                            'sentiment_score': headline_data['sentiment_score'],
                            'sentiment_label': headline_data['sentiment_label'],
                            'url': headline_data.get('url', '')
                        })
            
            if news_data:
                df = pd.DataFrame(news_data)
                self.db.insert_news(df)
                logging.info(f"Stored news sentiment data for {len(news_data)} articles")
            else:
                logging.warning("No news data to store")
                
        except Exception as e:
            logging.error(f"Error in daily news scraper: {str(e)}")
    
    def daily_analysis_and_report(self):
        """Perform full analysis and generate Excel report"""
        try:
            logging.info("Starting daily analysis and report generation...")
            
            # Get list of stocks to analyze
            stocks = self.nse_scraper.get_top_stocks_list()[:100]  # Top 100 stocks
            
            analysis_results = []
            technical_data = []
            fundamental_data = []
            
            for stock in stocks:
                symbol = stock['symbol']
                
                try:
                    logging.info(f"Analyzing {symbol}...")
                    
                    # Get stock info
                    stock_info = self.nse_scraper.get_stock_info(symbol)
                    
                    # Fundamental analysis
                    fund_metrics = extract_fundamental_metrics(stock_info)
                    fund_score = compute_fundamental_score(fund_metrics)
                    fund_score_value = fund_score.get('score', 0) if isinstance(fund_score, dict) else 0
                    
                    # Technical analysis
                    ohlcv = get_ohlcv(symbol)
                    tech_score = 0
                    tech_indicators = {}
                    
                    if ohlcv is not None:
                        tech_indicators = calculate_indicators(ohlcv)
                        if tech_indicators:
                            tech_score, _ = compute_technical_score(tech_indicators)
                    
                    # Get sentiment from database (latest)
                    sentiment_score = 0
                    try:
                        # This would require a database query - simplified for now
                        sentiment_score = 0  # Placeholder
                    except:
                        pass
                    
                    # Calculate overall score
                    overall_score = round((fund_score_value + tech_score + sentiment_score) / 3, 2)
                    
                    # Store analysis results
                    result = {
                        'symbol': symbol,
                        'FundamentalScore': fund_score_value,
                        'TechnicalScore': tech_score,
                        'SentimentScore': sentiment_score,
                        'OverallScore': overall_score
                    }
                    
                    # Add metrics
                    if fund_metrics:
                        result.update(fund_metrics)
                    if tech_indicators:
                        result.update(tech_indicators)
                    
                    analysis_results.append(result)
                    
                    # Separate data for different sheets
                    if fund_metrics:
                        fundamental_data.append({**result, **fund_metrics})
                    if tech_indicators:
                        technical_data.append({**result, **tech_indicators})
                
                except Exception as e:
                    logging.error(f"Error analyzing {symbol}: {str(e)}")
                    continue
            
            if analysis_results:
                # Store scores in database
                scores_data = []
                for result in analysis_results:
                    scores_data.append({
                        'symbol': result['symbol'],
                        'date': datetime.now().date(),
                        'fundamental_score': result['FundamentalScore'],
                        'technical_score': result['TechnicalScore'],
                        'sentiment_score': result['SentimentScore'],
                        'overall_score': result['OverallScore'],
                        'recommendation': self._get_recommendation(result['OverallScore'])
                    })
                
                df_scores = pd.DataFrame(scores_data)
                self.db.insert_scores(df_scores)
                
                # Generate Excel report
                df_summary = pd.DataFrame(analysis_results)
                df_technical = pd.DataFrame(technical_data) if technical_data else None
                df_fundamental = pd.DataFrame(fundamental_data) if fundamental_data else None
                
                # Get news sentiment data for report
                # This would typically come from database - simplified for now
                df_sentiment = None
                
                report_path = self.excel_generator.generate_daily_report(
                    summary_data=df_summary,
                    technical_data=df_technical,
                    fundamental_data=df_fundamental,
                    sentiment_data=df_sentiment
                )
                
                logging.info(f"Daily analysis completed. Report saved: {report_path}")
                logging.info(f"Analyzed {len(analysis_results)} stocks")
                
                # Log top performers
                top_10 = df_summary.nlargest(10, 'OverallScore')[['symbol', 'OverallScore']]
                logging.info("Top 10 performers:")
                for _, row in top_10.iterrows():
                    logging.info(f"  {row['symbol']}: {row['OverallScore']}")
            
            else:
                logging.error("No analysis results generated")
                
        except Exception as e:
            logging.error(f"Error in daily analysis and report: {str(e)}")
    
    def weekly_fundamental_update(self):
        """Weekly update of fundamental data"""
        try:
            logging.info("Starting weekly fundamental update...")
            
            # Get extended list of stocks for fundamental update
            stocks = self.nse_scraper.get_top_stocks_list()[:200]  # Top 200 stocks
            
            fundamental_data = []
            for stock in stocks:
                symbol = stock['symbol']
                
                try:
                    stock_info = self.nse_scraper.get_stock_info(symbol)
                    fund_metrics = extract_fundamental_metrics(stock_info)
                    
                    if fund_metrics:
                        fundamental_record = {
                            'symbol': symbol,
                            'date': datetime.now().date(),
                            **fund_metrics
                        }
                        fundamental_data.append(fundamental_record)
                
                except Exception as e:
                    logging.error(f"Error updating fundamentals for {symbol}: {str(e)}")
                    continue
            
            if fundamental_data:
                df = pd.DataFrame(fundamental_data)
                self.db.insert_fundamentals(df)
                logging.info(f"Updated fundamental data for {len(fundamental_data)} stocks")
            else:
                logging.warning("No fundamental data to update")
                
        except Exception as e:
            logging.error(f"Error in weekly fundamental update: {str(e)}")
    
    def _get_recommendation(self, score):
        """Get recommendation based on overall score"""
        if score > 70:
            return 'BUY'
        elif score >= 40:
            return 'HOLD'
        else:
            return 'SELL'
    
    def start(self):
        """Start the scheduler"""
        self.setup_jobs()
        logging.info("Stock Analysis Scheduler started")
        self.scheduler.start()
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logging.info("Stock Analysis Scheduler stopped")
    
    def run_manual_analysis(self):
        """Run analysis manually (for testing)"""
        logging.info("Running manual analysis...")
        self.daily_analysis_and_report()

if __name__ == "__main__":
    scheduler = StockAnalysisScheduler()
    
    # For testing, run manual analysis
    try:
        scheduler.run_manual_analysis()
    except KeyboardInterrupt:
        logging.info("Manual analysis interrupted")
    except Exception as e:
        logging.error(f"Error in manual analysis: {str(e)}")
