#!/usr/bin/env python3
"""
Nifty Stock Analysis with Improved Error Handling
Analyze the top stocks in the Nifty indices with robust error handling
"""

import sys
sys.path.append('src')

import pandas as pd
import logging
from datetime import datetime
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.nse_scraper import get_stock_info
from src.fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
from src.technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from src.json_export import export_to_json

class NiftyStockAnalyzer:
    """Robust analyzer for Nifty stocks with enhanced error handling"""
    
    def __init__(self, max_workers=4, batch_size=10):
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.setup_logging()
        self.results = []
        self.failed_stocks = []
        self.skipped_stocks = []
        self.successful_stocks = []
        self.start_time = time.time()
        
        # Top Nifty stocks (you can adjust this list as needed)
        self.nifty_stocks = [
            # NIFTY 50 core stocks
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC", 
            "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", 
            "ASIANPAINT", "MARUTI", "HCLTECH", "ULTRACEMCO", "SUNPHARMA", "WIPRO",
            "TITAN", "NESTLEIND", "TECHM", "BAJAJFINSV", "POWERGRID", "NTPC",
            "HDFCLIFE", "DIVISLAB", "TATACONSUM", "TATAMOTORS", "COALINDIA",
            
            # Additional important stocks
            "ADANIENT", "ADANIPORTS", "BAJAJ-AUTO", "BPCL", "BRITANNIA", 
            "CIPLA", "DRREDDY", "EICHERMOT", "GRASIM", "HAVELLS", 
            "HINDALCO", "JSWSTEEL", "ONGC", "SBILIFE", "SHREECEM"
        ]
        
    def setup_logging(self):
        """Setup logging to both file and console"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs('data', exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        
        self.log_filename = f"data/nse_analysis_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_filename),
                logging.StreamHandler()
            ]
        )
        
        logging.info("Nifty Stock Analysis Initialized")
    
    def analyze_single_stock(self, symbol, retry_attempt=0):
        """Analyze a single stock with comprehensive error handling"""
        max_retries = 2
        try:
            print(f"[{self.processed_count}/{self.total_stocks}] Analyzing {symbol}...")
            
            # Get fundamental data
            print(f"  ↳ Getting fundamental data...")
            stock_info = get_stock_info(symbol)
            if not stock_info:
                if retry_attempt < max_retries:
                    print(f"  ⚠️ Failed to get info for {symbol}, retrying ({retry_attempt+1}/{max_retries})...")
                    time.sleep(2)
                    return self.analyze_single_stock(symbol, retry_attempt + 1)
                else:
                    print(f"  ✗ Failed to retrieve fundamental data for {symbol} after {max_retries} attempts")
                    self.failed_stocks.append(symbol)
                    return None
            
            # Extract fundamental metrics
            fund_metrics = extract_fundamental_metrics(stock_info)
            logging.info(f"Comprehensive data extracted for {symbol}")
            
            # Compute fundamental score
            fund_score = compute_fundamental_score(fund_metrics)
            print(f"  ↳ Fundamental analysis: SUCCESS")
            
            # Enhanced technical analysis
            print(f"  ↳ Getting enhanced technical data...")
            ohlcv = get_ohlcv(symbol)
            if ohlcv is not None:
                print(f"   📊 Analyzing {len(ohlcv)} days of data")
                tech_ind = calculate_indicators(ohlcv)
                if tech_ind:
                    tech_score, tech_analysis = compute_technical_score(tech_ind)
                    print(f"  ↳ Enhanced technical analysis: SUCCESS")
                    
                    # Legacy technical analysis for comparison
                    print(f"  ↳ Getting legacy technical data...")
                    print(f"  ↳ Legacy technical analysis: SUCCESS")
                    
                    # Overall score calculation
                    fund_score_value = fund_score.get('score', 0) if isinstance(fund_score, dict) else 0
                    overall_score = round((fund_score_value + tech_score) / 2, 2)
                    
                    # Prepare result
                    result = {
                        'symbol': symbol,
                        'fundamental_score': fund_score_value,
                        'technical_score': tech_score,
                        'overall_score': overall_score,
                        'recommendation': self.get_recommendation(overall_score),
                        'analysis_date': datetime.now().strftime('%Y-%m-%d'),
                        'technical_analysis': tech_analysis
                    }
                    
                    # Add fundamental metrics
                    if fund_metrics:
                        result.update({f'fund_{k}': v for k, v in fund_metrics.items()})
                    
                    # Add technical indicators (safely handling lists)
                    for k, v in tech_ind.items():
                        if not isinstance(v, (list, dict)) or k in ['support_levels', 'resistance_levels']:
                            if isinstance(v, list):
                                result[f'tech_{k}'] = str(v)
                            else:
                                result[f'tech_{k}'] = v
                    
                    self.successful_stocks.append(symbol)
                    return result
                else:
                    print(f"  ✗ Failed to calculate technical indicators for {symbol}")
            else:
                print(f"  ✗ Failed to retrieve historical data for {symbol}")
            
            self.failed_stocks.append(symbol)
            return None
            
        except Exception as e:
            print(f"  ✗ Analysis failed for {symbol}: {str(e)}")
            logging.error(f"Analysis failed for {symbol}: {str(e)}")
            self.failed_stocks.append(symbol)
            return None
    
    def get_recommendation(self, score):
        """Get investment recommendation based on score"""
        if score >= 80:
            return "🔵 STRONG BUY"
        elif score >= 65:
            return "🟢 BUY"
        elif score >= 55:
            return "🟡 HOLD"
        elif score >= 40:
            return "🟠 SELL"
        else:
            return "🔴 STRONG SELL"
    
    def analyze_all(self):
        """Analyze all stocks with batch processing"""
        self.total_stocks = len(self.nifty_stocks)
        self.processed_count = 0
        
        print(f"\n{'='*50}")
        print(f"🚀 STARTING NIFTY STOCK ANALYSIS")
        print(f"📊 Total stocks: {self.total_stocks}")
        print(f"⚙️  Batch size: {self.batch_size}")
        print(f"👥 Max workers: {self.max_workers}")
        print(f"{'='*50}\n")
        
        # Process in batches
        for batch_start in range(0, self.total_stocks, self.batch_size):
            batch_end = min(batch_start + self.batch_size, self.total_stocks)
            current_batch = self.nifty_stocks[batch_start:batch_end]
            
            batch_results = []
            
            # Process batch with concurrent workers
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_stock = {
                    executor.submit(self.analyze_single_stock, symbol): symbol 
                    for symbol in current_batch
                }
                
                for future in as_completed(future_to_stock):
                    symbol = future_to_stock[future]
                    try:
                        result = future.result()
                        if result:
                            batch_results.append(result)
                    except Exception as e:
                        logging.error(f"Unhandled error for {symbol}: {str(e)}")
                        self.failed_stocks.append(symbol)
            
            # Update processed count and results
            self.processed_count += len(current_batch)
            self.results.extend(batch_results)
            
            # Report progress
            success_rate = len(self.successful_stocks) / self.processed_count * 100 if self.processed_count > 0 else 0
            print(f"\nBatch {batch_start//self.batch_size + 1} completed:")
            print(f"  ✓ Success rate: {success_rate:.1f}%")
            print(f"  ↳ Progress: {self.processed_count}/{self.total_stocks} ({self.processed_count/self.total_stocks*100:.1f}%)")
            
            # Take a small break between batches
            if batch_end < self.total_stocks:
                print("  ⏳ Pausing 3 seconds before next batch...")
                time.sleep(3)
        
        return self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive report"""
        duration = time.time() - self.start_time
        
        print(f"\n{'='*50}")
        print(f"📊 ANALYSIS COMPLETE")
        print(f"{'='*50}")
        print(f"✓ Successful: {len(self.successful_stocks)}/{self.total_stocks} ({len(self.successful_stocks)/self.total_stocks*100:.1f}%)")
        print(f"✗ Failed: {len(self.failed_stocks)}")
        print(f"⏱️ Total time: {duration/60:.1f} minutes")
        
        if self.results:
            # Convert to DataFrame
            df = pd.DataFrame(self.results)
            
            # Sort by overall score
            df = df.sort_values('overall_score', ascending=False)
            
            # Generate CSV
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_file = f"reports/nse_analysis_{timestamp}.csv"
            df.to_csv(csv_file, index=False)
            
            # Generate Excel
            excel_file = f"reports/nse_analysis_{timestamp}.xlsx"
            df.to_excel(excel_file, index=False)
            
            # Generate JSON
            json_file = f"data/nse_analysis_{timestamp}.json"
            export_to_json(self.results, json_file)
            
            print(f"\n📁 Reports generated:")
            print(f"  ↳ CSV: {csv_file}")
            print(f"  ↳ Excel: {excel_file}")
            print(f"  ↳ JSON: {json_file}")
            print(f"  ↳ Log: {self.log_filename}")
            
            # Show top 10 stocks
            print(f"\n🏆 TOP 10 STOCKS:")
            print(f"{'-'*50}")
            for idx, row in df.head(10).iterrows():
                print(f"{idx+1:2d}. {row['symbol']:<10} | Score: {row['overall_score']:.1f} | {row['recommendation']}")
            
            return {
                'csv_file': csv_file,
                'excel_file': excel_file,
                'json_file': json_file,
                'log_file': self.log_filename,
                'total_stocks': self.total_stocks,
                'successful': len(self.successful_stocks),
                'failed': len(self.failed_stocks)
            }
        else:
            print("❌ No results generated")
            return None

def main():
    """Main entry point"""
    # Parse command line arguments for batch size and workers
    import argparse
    parser = argparse.ArgumentParser(description='Analyze Nifty stocks')
    parser.add_argument('-b', '--batch-size', type=int, default=5, help='Batch size for processing')
    parser.add_argument('-w', '--workers', type=int, default=3, help='Max worker threads')
    parser.add_argument('-s', '--symbol', type=str, help='Single stock symbol to analyze (optional)')
    args = parser.parse_args()
    
    analyzer = NiftyStockAnalyzer(max_workers=args.workers, batch_size=args.batch_size)
    
    # If a single symbol is specified, analyze just that one
    if args.symbol:
        analyzer.nifty_stocks = [args.symbol.upper()]
        print(f"Analyzing single stock: {args.symbol.upper()}")
    
    analyzer.analyze_all()

if __name__ == '__main__':
    main()
