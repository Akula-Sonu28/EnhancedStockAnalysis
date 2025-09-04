#!/usr/bin/env python3
"""
Generate Complete Excel Report for All 200 NSE Stocks
Ensures all data is properly saved to Excel with comprehensive analysis
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import all our analyzers
from fundamental_analyzer import get_comprehensive_stock_data
from technical_analyzer import get_short_term_technical_analysis, get_technical_analysis
from data_exporter import ExcelReportGenerator

class CompleteExcelGenerator:
    def __init__(self):
        self.logger = self.setup_logging()
        self.all_stocks_data = []
        self.excel_generator = ExcelReportGenerator()
        
        # NSE Top 200 stocks
        self.nse_stocks = [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", 
            "KOTAKBANK", "LT", "HCLTECH", "ASIANPAINT", "MARUTI", "BAJFINANCE", "AXISBANK",
            "SUNPHARMA", "DMART", "TITAN", "ULTRACEMCO", "NESTLEIND", "WIPRO", "BAJAJFINSV",
            "ONGC", "TECHM", "TATAMOTORS", "POWERGRID", "M&M", "NTPC", "JSWSTEEL", "DIVISLAB",
            "COALINDIA", "GRASIM", "ADANIPORTS", "HINDALCO", "BRITANNIA", "DRREDDY", "EICHERMOT",
            "BAJAJ-AUTO", "CIPLA", "SHREECEM", "UPL", "APOLLOHOSP", "INDUSINDBK", "HEROMOTOCO",
            "BPCL", "TATASTEEL", "HINDUNILVR", "PIDILITIND", "ADANIENT", "GODREJCP", "SBILIFE",
            "HDFCLIFE", "VEDL", "IOC", "GAIL", "BANKBARODA", "HAVELLS", "DABUR", "MARICO",
            "BIOCON", "LUPIN", "ICICIPRULI", "PNB", "MOTHERSUMI", "COLPAL", "BOSCHLTD",
            "BERGEPAINT", "SIEMENS", "BAJAJHLDNG", "AMARAJABAT", "AMBUJACEM", "PAGEIND",
            "TORNTPHARM", "CANBK", "AUROPHARMA", "CADILAHC", "ADANIPOWER", "BANDHANBNK",
            "IDFCFIRSTB", "FEDERALBNK", "RBLBANK", "YESBANK", "GMRINFRA", "DLF", "JUBLFOOD",
            "MINDTREE", "MPHASIS", "L&TFH", "LICHSGFIN", "CHOLAFIN", "PEL", "WHIRLPOOL",
            "CUMMINSIND", "ASHOKLEY", "VOLTAS", "NMDC", "SAIL", "JINDALSTEL", "HINDZINC",
            "NALCO", "MOIL", "NATIONALUM", "TATACHEM", "UBL", "GODREJIND", "TATACONSUM",
            "BATAINDIA", "RELAXO", "DIXON", "CROMPTON", "VGUARD", "ORIENTELEC", "SCHNEIDER",
            "ABB", "THERMAX", "BHARATFORG", "EXIDEIND", "BALKRISIND", "MRF", "APOLLOTYRE",
            "CEATLTD", "JKTYRE", "TVS", "ESCORTS", "MAHINDCIE", "MINDAIND", "SUNDRMFAST",
            "BHEL", "BEL", "HAL", "IRCTC", "CONCOR", "RAILTEL", "RVNL", "SJVN", "NHPC",
            "RECLTD", "PFC", "HUDCO", "CANFINHOME", "REPCO", "SHRIRAMFIN", "M&MFIN",
            "SRTRANSFIN", "CHOLAHLDNG", "IIFL", "MANAPPURAM", "MUTHOOTFIN", "CAPF", "CDSL",
            "CAMS", "BSLMF", "NIPPONLIFE", "MAXLIFE", "STARHEALTH", "NYKAA", "ZOMATO",
            "PAYTM", "POLICYBZR", "MAPMYINDIA", "EASEMYTRIP", "CARTRADE", "MEDPLUS",
            "TATACOFFEE", "JYOTHYLAB", "EMAMILTD", "VBL", "CCL", "RADICO", "MCDOWELL-N",
            "KINGFISHER", "GLOBALBEES", "AVENUE", "FINCABLES", "KEI", "POLYCAB", "REC",
            "IRFC", "GICRE", "NIACL", "UIICL", "ORIENTCEMT", "RAMCOCEM", "JKCEMENT",
            "HEIDELBERG", "DALMIA", "JK", "BIRLACEM", "PRISMCEM", "STARCEMENT", "SHREECEM",
            "JKLAKSHMI", "VINATIORGA", "ALKYLAMINE", "BALRAMCHIN", "DEEPAKFERT", "GSFC",
            "GNFC", "RCF", "NFL", "CHAMBAL", "COROMANDEL", "KRIBHCO", "MADRASFERT",
            "ZUARI", "FACT", "IPL", "AEGISCHEM", "CLEAN", "NOCIL", "FINEORG", "BASF",
            "CLARIANT", "SYNGENE", "HIKAL", "DISHMAN", "SUVEN", "STRIDES", "BLISSGVS",
            "LAURUS", "NATCOPHAR", "SEQUENT", "CAPLIN", "GRANULES", "AJANTA", "ALKEM"
        ]
    
    def setup_logging(self):
        """Setup logging configuration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"data/complete_excel_generation_{timestamp}.log"
        
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    def analyze_single_stock(self, symbol):
        """Analyze a single stock with comprehensive data collection"""
        try:
            self.logger.info(f"Starting analysis for {symbol}")
            
            # Get fundamental analysis
            fundamental_data = get_comprehensive_stock_data(symbol)
            if not fundamental_data or fundamental_data.get('symbol') == 'N/A':
                self.logger.warning(f"No fundamental data for {symbol}")
                return None
            
            # Get enhanced technical analysis
            try:
                enhanced_technical = get_short_term_technical_analysis(symbol)
            except Exception as e:
                self.logger.warning(f"Enhanced technical analysis failed for {symbol}: {e}")
                enhanced_technical = {}
            
            # Get legacy technical analysis
            try:
                legacy_technical = get_technical_analysis(symbol)
            except Exception as e:
                self.logger.warning(f"Legacy technical analysis failed for {symbol}: {e}")
                legacy_technical = {}
            
            # Combine all data
            combined_data = {
                **fundamental_data,
                **{f"enhanced_{k}": v for k, v in enhanced_technical.items()},
                **{f"legacy_{k}": v for k, v in legacy_technical.items()}
            }
            
            # Calculate composite scores
            fund_score = fundamental_data.get('fundamental_score', 0)
            enhanced_score = enhanced_technical.get('technical_score', 0)
            legacy_score = legacy_technical.get('technical_score', 0)
            
            # Multiple scoring approaches
            combined_data.update({
                'fundamental_weighted_score': fund_score,
                'enhanced_balanced_score': (fund_score * 0.6) + (enhanced_score * 0.4),
                'legacy_balanced_score': (fund_score * 0.5) + (legacy_score * 0.5),
                'triple_weighted_score': (fund_score * 0.5) + (enhanced_score * 0.3) + (legacy_score * 0.2)
            })
            
            self.logger.info(f"Successfully analyzed {symbol}")
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    def process_stocks_batch(self, batch_stocks):
        """Process a batch of stocks"""
        batch_results = []
        for symbol in batch_stocks:
            result = self.analyze_single_stock(symbol)
            if result:
                batch_results.append(result)
            time.sleep(1)  # Rate limiting
        return batch_results
    
    def run_complete_analysis(self):
        """Run complete analysis for all 200 stocks"""
        self.logger.info("Starting complete Excel generation for 200 NSE stocks")
        start_time = time.time()
        
        # Process in batches with threading
        batch_size = 5
        max_workers = 3
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create batches
            batches = [
                self.nse_stocks[i:i + batch_size] 
                for i in range(0, len(self.nse_stocks), batch_size)
            ]
            
            # Submit batch jobs
            future_to_batch = {
                executor.submit(self.process_stocks_batch, batch): batch 
                for batch in batches
            }
            
            # Collect results
            completed_batches = 0
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    batch_results = future.result()
                    self.all_stocks_data.extend(batch_results)
                    completed_batches += 1
                    
                    self.logger.info(f"Completed batch {completed_batches}/{len(batches)} "
                                   f"({len(batch)} stocks) - "
                                   f"Total stocks processed: {len(self.all_stocks_data)}")
                    
                    # Add pause between batches
                    time.sleep(5)
                    
                except Exception as e:
                    self.logger.error(f"Batch failed: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.logger.info(f"Analysis completed in {duration:.1f} seconds")
        self.logger.info(f"Successfully processed {len(self.all_stocks_data)}/{len(self.nse_stocks)} stocks")
        
        # Generate Excel report
        self.generate_excel_report()
    
    def generate_excel_report(self):
        """Generate comprehensive Excel report with all stock data"""
        if not self.all_stocks_data:
            self.logger.error("No data to export to Excel")
            return
        
        try:
            self.logger.info("Generating comprehensive Excel report...")
            
            # Create DataFrame
            df = pd.DataFrame(self.all_stocks_data)
            
            # Ensure reports directory exists
            os.makedirs("reports", exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            filename = f"reports/Complete_NSE_200_Analysis_{timestamp}.xlsx"
            
            # Use the corrected method name
            success = self.excel_generator.generate_daily_report(df, filename)
            
            if success:
                # Check file size
                file_size = os.path.getsize(filename)
                self.logger.info(f"Excel report generated successfully: {filename}")
                self.logger.info(f"File size: {file_size:,} bytes")
                self.logger.info(f"Total stocks in report: {len(df)}")
                self.logger.info(f"Total columns: {len(df.columns)}")
                
                print(f"\n🎉 COMPLETE EXCEL REPORT GENERATED!")
                print(f"📁 File: {filename}")
                print(f"📊 Stocks: {len(df)}")
                print(f"📈 Data Points: {len(df.columns)} columns per stock")
                print(f"💾 File Size: {file_size:,} bytes")
                
            else:
                self.logger.error("Failed to generate Excel report")
                
        except Exception as e:
            self.logger.error(f"Error generating Excel report: {e}")

def main():
    """Main execution function"""
    print("🚀 Starting Complete Excel Generation for 200 NSE Stocks...")
    print("=" * 70)
    
    generator = CompleteExcelGenerator()
    generator.run_complete_analysis()
    
    print("\n✅ Complete Excel generation finished!")

if __name__ == "__main__":
    main()
