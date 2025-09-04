#!/usr/bin/env python3
"""
Nifty 200 Stocks Analysis
Using the official Nifty 200 list as the source of stocks to analyze
"""

import sys
import os
import pandas as pd
import logging
from datetime import datetime
import time

# Add the src directory to the path
sys.path.append('src')

# Try to import required modules
try:
    from excel_exporter import ExcelReportGenerator
    from enhanced_fundamental_analyzer import get_comprehensive_stock_data
    from enhanced_technical_analyzer import get_short_term_technical_analysis
    from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
except ImportError as e:
    print(f"Could not import required modules: {e}")
    print("Make sure you are running this script from the Stock_Analysis directory")
    sys.exit(1)

class Nifty200Analyzer:
    def __init__(self, csv_file, max_workers=3):
        self.csv_file = csv_file
        self.max_workers = max_workers
        self.nifty200_stocks = self.load_nifty200_stocks()
        self.setup_logging()
        self.results = []
        self.failed_stocks = []
        
    def setup_logging(self):
        """Setup logging for the analysis"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"data/nifty200_analysis_{timestamp}.log"
        
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.log_filename = log_filename
        
    def load_nifty200_stocks(self):
        """Load Nifty 200 stocks from CSV file"""
        try:
            print(f"Loading Nifty 200 stocks from {self.csv_file}...")
            df = pd.read_csv(self.csv_file)
            
            # Check if required columns exist
            if 'Symbol' not in df.columns:
                print("Error: CSV file doesn't contain the 'Symbol' column")
                return []
                
            # Extract stock symbols
            nifty200_symbols = df['Symbol'].tolist()
            
            # Clean up symbols (remove any whitespace)
            nifty200_symbols = [symbol.strip() for symbol in nifty200_symbols]
            
            print(f"Successfully loaded {len(nifty200_symbols)} stocks from Nifty 200 list")
            return nifty200_symbols
            
        except Exception as e:
            print(f"Error loading Nifty 200 stocks: {e}")
            return []
    
    def analyze_stocks(self):
        """Run analysis for all Nifty 200 stocks"""
        if not self.nifty200_stocks:
            print("No stocks to analyze. Please check the CSV file.")
            return False
            
        print(f"\n🔍 STARTING NIFTY 200 STOCKS ANALYSIS")
        print("=" * 80)
        print(f"Total stocks to analyze: {len(self.nifty200_stocks)}")
        
        start_time = time.time()
        
        # Process each stock
        for idx, symbol in enumerate(self.nifty200_stocks):
            try:
                print(f"\n[{idx+1}/{len(self.nifty200_stocks)}] Analyzing {symbol}...")
                
                # Get fundamental data
                print(f"  ↳ Getting fundamental data...")
                try:
                    fundamental_data = get_comprehensive_stock_data(symbol)
                    fundamental_status = 'success' if fundamental_data else 'failed'
                    print(f"  ↳ Fundamental analysis: {fundamental_status.upper()}")
                except Exception as e:
                    print(f"  ✗ Fundamental analysis failed: {e}")
                    fundamental_data = {}
                    fundamental_status = 'failed'
                
                # Get enhanced technical data
                print(f"  ↳ Getting enhanced technical data...")
                try:
                    enhanced_technical = get_short_term_technical_analysis(symbol)
                    enhanced_status = 'success' if enhanced_technical else 'failed'
                    print(f"  ↳ Enhanced technical analysis: {enhanced_status.upper()}")
                except Exception as e:
                    print(f"  ✗ Enhanced technical analysis failed: {e}")
                    enhanced_technical = {}
                    enhanced_status = 'failed'
                
                # Get legacy technical data
                print(f"  ↳ Getting legacy technical data...")
                try:
                    # First get the OHLCV data
                    ohlcv_data = get_ohlcv(symbol, period="1y")
                    # Calculate technical indicators
                    indicators = calculate_indicators(ohlcv_data)
                    # Compute technical score
                    technical_score = compute_technical_score(indicators)
                    
                    # Create technical analysis result
                    legacy_technical = {
                        'technical_score': technical_score,
                        **indicators
                    }
                    legacy_status = 'success'
                    print(f"  ↳ Legacy technical analysis: {legacy_status.upper()}")
                except Exception as e:
                    print(f"  ✗ Legacy technical analysis failed: {e}")
                    legacy_technical = {}
                    legacy_status = 'failed'
                
                # Combine all data
                stock_data = {
                    'symbol': symbol,
                    'fundamental_status': fundamental_status,
                    'enhanced_technical_status': enhanced_status,
                    'legacy_technical_status': legacy_status,
                }
                
                # Add fundamental data
                if fundamental_data:
                    stock_data.update(fundamental_data)
                
                # Add enhanced technical data with prefix
                if enhanced_technical:
                    stock_data.update({f'enhanced_{k}': v for k, v in enhanced_technical.items()})
                
                # Add legacy technical data with prefix
                if legacy_technical:
                    stock_data.update({f'legacy_{k}': v for k, v in legacy_technical.items()})
                
                # Calculate composite scores
                fund_score = fundamental_data.get('fundamental_score', 0)
                enhanced_score = enhanced_technical.get('technical_score', 0)
                legacy_score = legacy_technical.get('technical_score', 0)
                
                # Multiple scoring approaches
                stock_data.update({
                    'overall_score_fundamental': fund_score,
                    'overall_score_enhanced': (fund_score * 0.6) + (enhanced_score * 0.4),
                    'overall_score_legacy': (fund_score * 0.5) + (legacy_score * 0.5),
                    'overall_score_triple': (fund_score * 0.5) + (enhanced_score * 0.3) + (legacy_score * 0.2)
                })
                
                # Determine final recommendation based on triple weighted score
                triple_score = stock_data['overall_score_triple']
                if triple_score >= 70:
                    recommendation = 'STRONG BUY'
                elif triple_score >= 60:
                    recommendation = 'BUY'
                elif triple_score >= 50:
                    recommendation = 'HOLD'
                elif triple_score >= 40:
                    recommendation = 'WEAK SELL'
                else:
                    recommendation = 'SELL'
                
                stock_data['final_recommendation'] = recommendation
                
                # Add to results
                self.results.append(stock_data)
                print(f"  ✓ {symbol} analysis complete: Score {triple_score:.1f}, {recommendation}")
                
                # Log success
                self.logger.info(f"Analysis complete for {symbol}: Score {triple_score:.1f}, {recommendation}")
                
                # Add brief pause between stocks to avoid rate limiting
                if idx < len(self.nifty200_stocks) - 1:
                    time.sleep(1)
                
            except Exception as e:
                print(f"  ✗ Analysis failed for {symbol}: {e}")
                self.failed_stocks.append(symbol)
                self.logger.error(f"Analysis failed for {symbol}: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Print summary
        print("\n📊 NIFTY 200 ANALYSIS SUMMARY")
        print("=" * 80)
        print(f"Total stocks analyzed: {len(self.results)}/{len(self.nifty200_stocks)}")
        print(f"Failed analyses: {len(self.failed_stocks)}")
        print(f"Total duration: {duration/60:.1f} minutes")
        print(f"Average time per stock: {duration/len(self.nifty200_stocks):.1f} seconds")
        
        # Log summary
        self.logger.info(f"Analysis complete: {len(self.results)} successful, {len(self.failed_stocks)} failed")
        self.logger.info(f"Duration: {duration/60:.1f} minutes")
        
        return True
    
    def generate_excel_report(self):
        """Generate Excel report with all results"""
        if not self.results:
            print("No results to export to Excel")
            return False
            
        print("\n📊 GENERATING EXCEL REPORT")
        print("=" * 80)
        
        try:
            # Create DataFrame
            df = pd.DataFrame(self.results)
            
            # Sort by triple weighted score
            df = df.sort_values('overall_score_triple', ascending=False)
            
            # Generate Excel filename with timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d')
            filename = f"reports/Nifty200_Analysis_{timestamp}.xlsx"
            
            # Generate Excel report
            excel_generator = ExcelReportGenerator()
            report_path = excel_generator.generate_daily_report(df, filename)
            
            print(f"\n✅ Excel report generated: {report_path}")
            print(f"   📊 Contains analysis for {len(df)} Nifty 200 stocks")
            
            # Check file size
            file_size = os.path.getsize(report_path)
            print(f"   📁 File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
            
            # Log success
            self.logger.info(f"Excel report generated: {report_path}")
            self.logger.info(f"File size: {file_size:,} bytes")
            
            return True
            
        except Exception as e:
            print(f"❌ Error generating Excel report: {e}")
            self.logger.error(f"Error generating Excel report: {e}")
            return False
    
    def generate_summary_stats(self):
        """Generate and display summary statistics"""
        if not self.results:
            print("No results to generate statistics")
            return
            
        print("\n📈 NIFTY 200 ANALYSIS STATISTICS")
        print("=" * 80)
        
        try:
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(self.results)
            
            # Top performers
            if 'overall_score_triple' in df.columns and 'symbol' in df.columns:
                print("\n🏆 TOP 20 NIFTY 200 STOCKS:")
                print("-" * 70)
                print(f"{'Rank':^5} {'Symbol':^12} {'Score':^8} {'Recommendation':^15} {'Sector':^20}")
                print("-" * 70)
                
                top_20 = df.nlargest(20, 'overall_score_triple')
                for idx, (_, row) in enumerate(top_20.iterrows(), 1):
                    symbol = row['symbol']
                    score = row['overall_score_triple']
                    rec = row['final_recommendation']
                    sector = row.get('sector', 'Unknown')
                    print(f"{idx:^5} {symbol:^12} {score:^8.1f} {rec:^15} {sector:^20}")
            
            # Recommendation distribution
            if 'final_recommendation' in df.columns:
                print("\n📊 RECOMMENDATION DISTRIBUTION:")
                print("-" * 50)
                rec_counts = df['final_recommendation'].value_counts()
                total = len(df)
                
                for rec, count in rec_counts.items():
                    percentage = (count / total) * 100
                    print(f"{rec:^15}: {count:3d} stocks ({percentage:5.1f}%)")
            
            # Sector distribution
            if 'sector' in df.columns:
                print("\n🔍 SECTOR ANALYSIS:")
                print("-" * 70)
                print(f"{'Sector':^20} {'Count':^8} {'Percentage':^12} {'Avg Score':^10}")
                print("-" * 70)
                
                sector_counts = df['sector'].value_counts()
                total = len(df)
                
                # Get average score by sector
                sector_scores = df.groupby('sector')['overall_score_triple'].mean()
                
                for sector, count in sector_counts.items():
                    percentage = (count / total) * 100
                    avg_score = sector_scores[sector]
                    print(f"{sector:^20} {count:^8d} {percentage:^12.1f}% {avg_score:^10.1f}")
            
            print("\n📝 ANALYSIS COMPLETE - NIFTY 200 STOCKS EVALUATED")
            
        except Exception as e:
            print(f"❌ Error generating statistics: {e}")

def main():
    """Main execution function"""
    print("🚀 NIFTY 200 STOCKS ANALYSIS")
    print("=" * 80)
    
    # Define the path to the Nifty 200 CSV file
    nifty200_csv = "ind_nifty200list (2).csv"
    
    if not os.path.exists(nifty200_csv):
        print(f"Error: Could not find the Nifty 200 CSV file at {nifty200_csv}")
        return
    
    # Create analyzer
    analyzer = Nifty200Analyzer(nifty200_csv, max_workers=3)
    
    # Run analysis
    success = analyzer.analyze_stocks()
    
    if success:
        # Generate Excel report
        analyzer.generate_excel_report()
        
        # Generate statistics
        analyzer.generate_summary_stats()
        
        print(f"\n✅ NIFTY 200 ANALYSIS COMPLETE")
        print(f"📝 Log file: {analyzer.log_filename}")
    else:
        print(f"\n❌ NIFTY 200 ANALYSIS FAILED")

if __name__ == "__main__":
    main()
