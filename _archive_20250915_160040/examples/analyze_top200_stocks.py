#!/usr/bin/env python3
"""
Top 200 NSE Stocks Unified Analysis
Comprehensive analysis of top 200 NSE stocks using the unified analysis system
"""

import sys
sys.path.append('src')

import pandas as pd
import logging
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis
from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from excel_exporter import ExcelExporter
import yfinance as yf

class Top200StockAnalyzer:
    """Comprehensive analyzer for top 200 NSE stocks"""
    
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.setup_logging()
        self.results = []
        self.failed_stocks = []
        self.total_stocks = 0
        self.processed_stocks = 0
        
        # Top 200 NSE stocks (expanded list)
        self.top_200_stocks = [
            # NIFTY 50 core stocks
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC", 
            "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", 
            "ASIANPAINT", "MARUTI", "HCLTECH", "ULTRACEMCO", "SUNPHARMA", "WIPRO",
            "TITAN", "NESTLEIND", "TECHM", "BAJAJFINSV", "POWERGRID", "NTPC",
            "HDFCLIFE", "DIVISLAB", "TATACONSUM", "TATAMOTORS", "COALINDIA",
            
            # Large Cap (Next 50)
            "ADANIENT", "ADANIGREEN", "ADANIPORTS", "AMBUJACEM", "APOLLOHOSP",
            "AUROPHARMA", "BAJAJ-AUTO", "BANDHANBNK", "BANKBARODA", "BERGEPAINT",
            "BIOCON", "BOSCHLTD", "BPCL", "BRITANNIA", "CHOLAFIN", "CIPLA",
            "COLPAL", "DLF", "DABUR", "DMART", "DRREDDY", "EICHERMOT", "GAIL",
            "GLAND", "GODREJCP", "GRASIM", "HAVELLS", "HDFCAMC", "INDIGO",
            "HAL", "JINDALSTEL", "JUBLFOOD", "LICI", "LUPIN", "MUTHOOTFIN",
            
            # Mid Cap Leaders (Next 50)
            "NAUKRI", "NMDC", "ONGC", "PIDILITIND", "SAIL", "SBICARD", "SBILIFE",
            "SIEMENS", "TATACHEM", "TATAPOWER", "TORNTPHARM", "UPL", "FEDERALBNK",
            "IDFCFIRSTB", "INDUSINDBK", "CANBK", "INDIANB", "PNB", "UNIONBANK",
            "JSWSTEEL", "HINDALCO", "VEDL", "HEROMOTOCO", "BAJAJHLDNG", "SHREECEM",
            "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "SOBHA", "BRIGADE", "MINDTREE",
            "MPHASIS", "LTIM", "PERSISTENT", "COFORGE", "OFSS", "FSL", "IRCTC",
            
            # Emerging Large Cap (Next 70)
            "ZOMATO", "PAYTM", "POLICYBZR", "NYKAA", "CARTRADE", "EASEMYTRIP",
            "TATASTEEL", "JSWENERGY", "ADANIPOWER", "NTPC", "BHEL", "SJVN",
            "NHPC", "CONCOR", "IRFC", "IRCON", "RVNL", "RAILTEL", "RITES",
            "MAZDOCK", "GRSE", "COCHINSHIP", "BEML", "BEL", "MIDHANI", "MTAR",
            "DCMSHRIRAM", "DEEPAKNI", "GNFC", "GSFC", "FACT", "RCF", "NFL",
            "CHAMBLFERT", "COROMANDEL", "KRIBHCO", "MADHUCON", "GPIL", "SRF",
            "AAVAS", "HOMEFIRST", "CANFINHOME", "LICHSGFIN", "REPCO", "SHRIRAMFIN",
            "MMFIN", "SWANENERGY", "RPOWER", "SUZLON", "ORIENTELEC", "KEI",
            "POLYCAB", "HAVELLS", "CROMPTON", "VGUARD", "SYMPHONY", "BLUESTARCO",
            "VOLTAS", "WHIRLPOOL", "RAJESHEXPO", "KALPATPOWR", "THERMAX", "KIRLOSENG",
            "CUMMINSIND", "MAHINDCIE", "MOTHERSON", "RAMCOCEM", "AMBUJACEMENT",
            "JKCEMENT", "HEIDELBERG", "PRISMCEMENT", "ORIENTCEM", "DALMIACEMT",
            
            # Additional Quality Stocks (Remaining to reach 200)
            "PAGEIND", "MARICO", "GODREJIND", "VBL", "RADICO", "UBL", "MCDOWELL",
            "VSTIND", "GODFRYPHLP", "HONAUT", "ABBOTINDIA", "ASTRAZEN", "PFIZER",
            "NOVARTIS", "SANOFI", "GLAXO", "IPCA", "ALKEM", "LALPATHLAB", "METROPOLIS",
            "THYROCARE", "KRBL", "ANDHRSUGAR", "BALRAMCHIN", "BAJAJCON", "CENTURYTEXT",
            "RAYMOND", "ARVIND", "WELCORP", "TRIDENT", "RTNPOWER", "ADANIGAS",
            "GUJGASLTD", "IGL", "MGL", "PETRONET", "AEGISCHEM", "ATUL", "BALRAMCHIN",
            "CHEMCON", "CLEAN", "FINEORG", "GALAXY", "GHCL", "HATSUN", "HIMATSEIDE",
            "HINDCOPPER", "HINDZINC", "IOC", "JBCHEPHARM", "KANSAINER", "KARURVYSYA",
            "LAOPALA", "LINDEINDIA", "MAHLOG", "MANAPPURAM", "MOIL", "NATIONALUM",
            "NAVINFLUOR", "NHPC", "NLCINDIA", "ONGC", "ORIENTBANK", "PHILIPCARB",
            "PIIND", "PUNJLLOYD", "RAJRATAN", "RATNAMANI", "RELAXO", "SANOFI",
            "SCHAEFFLER", "SHANKARA", "SHILPAMED", "SOLARINDS", "SPARC", "STAR",
            "STLTECH", "SUBEXLTD", "SUPREMEIND", "SYNGENE", "TEAMLEASE", "THYROCARE",
            "TIINDIA", "TRENT", "TTKPRESTIG", "TVTODAY", "UJJIVAN", "UJJIVANSFB",
            "UNICHEMLAB", "UNIONBANK", "VIPIND", "VISAKAIND", "WABCOINDIA", "WELSPUNIND"
        ]
        
        # Take first 200 stocks
        self.top_200_stocks = self.top_200_stocks[:200]
        
    def setup_logging(self):
        """Setup comprehensive logging"""
        os.makedirs('data', exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        
        self.log_filename = f"data/top200_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_filename),
                logging.StreamHandler()
            ]
        )
        
        logging.info("Top 200 NSE Stock Analysis Initialized")
    
    def analyze_single_stock(self, symbol):
        """Analyze a single stock with comprehensive data"""
        try:
            start_time = time.time()
            
            # Initialize result dictionary
            stock_data = {
                'symbol': symbol,
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'processing'
            }
            
            # 1. Fundamental Analysis
            fund_data = get_comprehensive_stock_data(symbol)
            if fund_data:
                stock_data.update(fund_data)
                stock_data['fundamental_status'] = 'success'
                logging.info(f"Fundamental analysis completed for {symbol}: {len(fund_data)} fields")
            else:
                stock_data['fundamental_status'] = 'failed'
                logging.warning(f"Fundamental analysis failed for {symbol}")
            
            # 2. Enhanced Technical Analysis
            enhanced_tech_data = get_short_term_technical_analysis(symbol, period_days=90)
            if enhanced_tech_data:
                # Add with prefix to avoid conflicts
                for key, value in enhanced_tech_data.items():
                    if key not in stock_data:
                        stock_data[f"enhanced_{key}"] = value
                    else:
                        stock_data[f"enhanced_tech_{key}"] = value
                stock_data['enhanced_technical_status'] = 'success'
                logging.info(f"Enhanced technical analysis completed for {symbol}: {len(enhanced_tech_data)} fields")
            else:
                stock_data['enhanced_technical_status'] = 'failed'
                logging.warning(f"Enhanced technical analysis failed for {symbol}")
            
            # 3. Legacy Technical Analysis
            try:
                ticker = yf.Ticker(f"{symbol}.NS")
                hist = ticker.history(period="1y", interval="1d")
                
                if not hist.empty:
                    # Safe calculation of indicators with error handling
                    try:
                        indicators = calculate_indicators(hist)
                        if indicators:
                            # Safely convert lists to strings for JSON and Excel compatibility
                            for key, value in indicators.items():
                                if isinstance(value, list):
                                    indicators[key] = str(value)
                                    
                            tech_score, tech_analysis = compute_technical_score(indicators)
                            stock_data.update({
                                'legacy_technical_score': tech_score,
                                'legacy_technical_analysis': tech_analysis,
                                'legacy_rsi': indicators.get('rsi14', 0),
                                'legacy_macd': indicators.get('macd', 0),
                                'legacy_sma_20': indicators.get('sma20', 0),
                                'legacy_sma_50': indicators.get('sma50', 0),
                                'legacy_trend': indicators.get('trend', 'Unknown')
                            })
                            stock_data['legacy_technical_status'] = 'success'
                        else:
                            stock_data['legacy_technical_status'] = 'failed'
                    except Exception as ind_error:
                        logging.error(f"Error calculating indicators for {symbol}: {ind_error}")
                        stock_data['legacy_technical_status'] = f'indicator_error: {str(ind_error)}'
                else:
                    stock_data['legacy_technical_status'] = 'no_data'
            except Exception as e:
                stock_data['legacy_technical_status'] = f'error: {str(e)}'
                logging.error(f"Legacy technical analysis error for {symbol}: {e}")
            
            # 4. Calculate Comprehensive Scores
            fund_score = stock_data.get('fundamental_score', 50)
            enhanced_score = enhanced_tech_data.get('short_term_score', 50) if enhanced_tech_data else 50
            legacy_score = stock_data.get('legacy_technical_score', 50)
            
            # Multiple scoring approaches
            stock_data.update({
                'fundamental_score_final': fund_score,
                'enhanced_technical_score_final': enhanced_score,
                'legacy_technical_score_final': legacy_score,
                'overall_score_balanced': (fund_score * 0.6) + (enhanced_score * 0.4),
                'overall_score_triple': (fund_score * 0.5) + (enhanced_score * 0.3) + (legacy_score * 0.2),
                'analysis_duration_seconds': round(time.time() - start_time, 2),
                'status': 'completed'
            })
            
            # Generate recommendation
            best_score = stock_data['overall_score_triple']
            if best_score >= 70:
                recommendation = "🟢 STRONG BUY"
            elif best_score >= 60:
                recommendation = "🟢 BUY"
            elif best_score >= 50:
                recommendation = "🟡 HOLD"
            elif best_score >= 40:
                recommendation = "🟠 WEAK SELL"
            else:
                recommendation = "🔴 SELL"
            
            stock_data['final_recommendation'] = recommendation
            
            # Convert complex objects to strings for Excel compatibility
            for key, value in stock_data.items():
                if isinstance(value, (list, dict)):
                    try:
                        stock_data[key] = str(value)
                    except Exception:
                        # Handle conversion errors
                        stock_data[key] = f"[Error converting {key}]"
                elif pd.isna(value):
                    stock_data[key] = ''
                elif value is None:
                    stock_data[key] = ''
            
            # Remove emojis from logging to avoid encoding issues in Windows console
            clean_recommendation = recommendation
            for emoji in ['🔵', '🟢', '🟡', '🟠', '🔴']:
                if emoji in clean_recommendation:
                    clean_recommendation = clean_recommendation.replace(emoji, '')
            
            logging.info(f"Completed analysis for {symbol}: Score={best_score:.1f}, Recommendation={clean_recommendation.strip()}")
            return stock_data
            
        except Exception as e:
            error_data = {
                'symbol': symbol,
                'status': 'error',
                'error_message': str(e),
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            logging.error(f"Analysis failed for {symbol}: {e}")
            return error_data
    
    def analyze_batch(self, batch_size=10):
        """Analyze stocks in batches to avoid overwhelming the system"""
        total_stocks = len(self.top_200_stocks)
        self.total_stocks = total_stocks
        
        print(f"🚀 Starting Top 200 NSE Stock Analysis")
        print(f"📊 Total stocks to analyze: {total_stocks}")
        print(f"🔄 Batch size: {batch_size}")
        print(f"👥 Max workers: {self.max_workers}")
        print("=" * 80)
        
        logging.info(f"Starting batch analysis of {total_stocks} stocks")
        
        start_time = time.time()
        
        # Process in batches
        for batch_start in range(0, total_stocks, batch_size):
            batch_end = min(batch_start + batch_size, total_stocks)
            current_batch = self.top_200_stocks[batch_start:batch_end]
            
            print(f"\n📦 Processing Batch {(batch_start//batch_size)+1}: Stocks {batch_start+1}-{batch_end}")
            print("-" * 60)
            
            batch_results = []
            batch_start_time = time.time()
            
            # Use ThreadPoolExecutor for concurrent processing
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_stock = {
                    executor.submit(self.analyze_single_stock, stock): stock 
                    for stock in current_batch
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_stock):
                    stock = future_to_stock[future]
                    try:
                        result = future.result(timeout=120)  # 2 minute timeout per stock
                        if result:
                            batch_results.append(result)
                            self.processed_stocks += 1
                            
                            status = result.get('status', 'unknown')
                            score = result.get('overall_score_triple', 0)
                            recommendation = result.get('final_recommendation', 'N/A')
                            
                            print(f"   ✅ {stock:<12}: {status:<10} | Score: {score:5.1f} | {recommendation}")
                            
                            if status == 'error':
                                self.failed_stocks.append(stock)
                        else:
                            # Handle case where result is None
                            print(f"   ⚠️ {stock:<12}: no data returned")
                            self.failed_stocks.append(stock)
                            logging.warning(f"No data returned for {stock}")
                            self.processed_stocks += 1
                            
                    except Exception as e:
                        print(f"   ❌ {stock:<12}: timeout/error - {str(e)[:50]}")
                        self.failed_stocks.append(stock)
                        self.processed_stocks += 1
                        logging.error(f"Batch processing error for {stock}: {e}")
            
            # Add batch results to main results
            self.results.extend(batch_results)
            
            batch_duration = time.time() - batch_start_time
            progress = (self.processed_stocks / total_stocks) * 100
            
            print(f"\n   📊 Batch Summary:")
            print(f"      Processed: {len(batch_results)}/{len(current_batch)} stocks")
            print(f"      Duration: {batch_duration:.1f} seconds")
            print(f"      Overall Progress: {progress:.1f}% ({self.processed_stocks}/{total_stocks})")
            
            # Brief pause between batches
            if batch_end < total_stocks:
                print(f"      ⏳ Pausing 5 seconds before next batch...")
                time.sleep(5)
        
        total_duration = time.time() - start_time
        
        print(f"\n🎉 BATCH ANALYSIS COMPLETE!")
        print("=" * 50)
        print(f"   📊 Total processed: {len(self.results)}/{total_stocks}")
        print(f"   ✅ Successful: {len(self.results) - len(self.failed_stocks)}")
        print(f"   ❌ Failed: {len(self.failed_stocks)}")
        print(f"   ⏱️  Total duration: {total_duration/60:.1f} minutes")
        print(f"   📈 Average per stock: {total_duration/total_stocks:.1f} seconds")
        
        # Use emoji-free text for logging to avoid encoding issues
        logging.info(f"Batch analysis completed: {len(self.results)} results, {len(self.failed_stocks)} failures")
        
        return self.results
    
    def generate_comprehensive_report(self):
        """Generate comprehensive Excel report"""
        if not self.results:
            print("❌ No results to generate report")
            return None
        
        print(f"\n📊 GENERATING COMPREHENSIVE EXCEL REPORT")
        print("-" * 50)
        
        try:
            # Create DataFrame
            df = pd.DataFrame(self.results)
            
            # Sort by overall score
            df = df.sort_values('overall_score_triple', ascending=False, na_position='last')
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/Top200_NSE_Analysis_{timestamp}.xlsx"
            
            # Use ExcelReportGenerator with correct method name
            from src.excel_exporter import ExcelReportGenerator
            excel_generator = ExcelReportGenerator()
            filename = excel_generator.generate_daily_report(df)
            
            print(f"✅ Excel report saved: {filename}")
            
            # Check file size
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                print(f"   📁 File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
                logging.info(f"Excel report generated: {filename}, Size: {file_size} bytes")
            
            # Generate summary statistics
            self.generate_summary_stats(df)
            
            return filename
            
        except Exception as e:
            print(f"❌ Excel generation failed: {e}")
            logging.error(f"Excel generation failed: {e}")
            return None
    
    def generate_summary_stats(self, df):
        """Generate and display summary statistics"""
        print(f"\n📈 ANALYSIS SUMMARY STATISTICS")
        print("=" * 50)
        
        # Overall statistics
        total_stocks = len(df)
        successful_fundamental = len(df[df['fundamental_status'] == 'success'])
        successful_enhanced = len(df[df['enhanced_technical_status'] == 'success'])
        successful_legacy = len(df[df['legacy_technical_status'] == 'success'])
        
        print(f"📊 DATA COLLECTION SUCCESS RATES:")
        print(f"   Total Stocks Analyzed     : {total_stocks}")
        print(f"   Fundamental Analysis      : {successful_fundamental}/{total_stocks} ({successful_fundamental/total_stocks*100:.1f}%)")
        print(f"   Enhanced Technical        : {successful_enhanced}/{total_stocks} ({successful_enhanced/total_stocks*100:.1f}%)")
        print(f"   Legacy Technical          : {successful_legacy}/{total_stocks} ({successful_legacy/total_stocks*100:.1f}%)")
        
        # Score statistics
        if 'overall_score_triple' in df.columns:
            scores = df['overall_score_triple'].dropna()
            if len(scores) > 0:
                print(f"\n🎯 SCORE DISTRIBUTION:")
                print(f"   Average Score             : {scores.mean():.1f}")
                print(f"   Median Score              : {scores.median():.1f}")
                print(f"   Highest Score             : {scores.max():.1f}")
                print(f"   Lowest Score              : {scores.min():.1f}")
                print(f"   Standard Deviation        : {scores.std():.1f}")
        
        # Top performers
        if 'overall_score_triple' in df.columns and 'symbol' in df.columns:
            top_10 = df.nlargest(10, 'overall_score_triple')[['symbol', 'overall_score_triple', 'final_recommendation']]
            
            print(f"\n🏆 TOP 10 PERFORMERS:")
            print("-" * 40)
            for idx, (_, row) in enumerate(top_10.iterrows(), 1):
                symbol = row['symbol']
                score = row['overall_score_triple']
                rec = row['final_recommendation']
                print(f"   {idx:2d}. {symbol:<12}: {score:5.1f} - {rec}")
        
        # Recommendation distribution
        if 'final_recommendation' in df.columns:
            rec_counts = df['final_recommendation'].value_counts()
            print(f"\n📋 RECOMMENDATION DISTRIBUTION:")
            print("-" * 35)
            for rec, count in rec_counts.items():
                percentage = (count / total_stocks) * 100
                print(f"   {rec:<25}: {count:3d} ({percentage:4.1f}%)")
        
        # Failed stocks
        if self.failed_stocks:
            print(f"\n❌ FAILED ANALYSIS ({len(self.failed_stocks)} stocks):")
            print("-" * 30)
            for stock in self.failed_stocks[:10]:  # Show first 10
                print(f"   • {stock}")
            if len(self.failed_stocks) > 10:
                print(f"   ... and {len(self.failed_stocks) - 10} more")

def main():
    """Main execution function"""
    print("🎯 TOP 200 NSE STOCKS - UNIFIED COMPREHENSIVE ANALYSIS")
    print("=" * 80)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Analyze Top 200 NSE stocks')
    parser.add_argument('-w', '--workers', type=int, default=3, help='Max worker threads')
    parser.add_argument('-b', '--batch', type=int, default=5, help='Batch size')
    parser.add_argument('-s', '--symbol', type=str, help='Single stock symbol to analyze')
    parser.add_argument('-n', '--num', type=int, default=200, help='Number of stocks to analyze (max 200)')
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = Top200StockAnalyzer(max_workers=args.workers)  # User-specified worker count
    
    # Handle single stock analysis if requested
    if args.symbol:
        print(f"🔍 Single stock analysis mode: {args.symbol}")
        # Create a new list with just the requested symbol
        analyzer.top_200_stocks = [args.symbol]
    elif args.num < 200:
        # Limit the number of stocks
        analyzer.top_200_stocks = analyzer.top_200_stocks[:args.num]
        print(f"🔍 Limited to {args.num} stocks")
    
    # Run batch analysis
    results = analyzer.analyze_batch(batch_size=args.batch)
    
    if results:
        # Generate comprehensive report
        report_file = analyzer.generate_comprehensive_report()
        
        if report_file:
            print(f"\n🎉 ANALYSIS COMPLETED SUCCESSFULLY!")
            print(f"📊 Report file: {report_file}")
            print(f"📝 Log file: {analyzer.log_filename}")
        else:
            print(f"\n⚠️  Analysis completed but report generation failed")
    else:
        print(f"\n❌ Analysis failed - no results generated")

if __name__ == "__main__":
    main()
